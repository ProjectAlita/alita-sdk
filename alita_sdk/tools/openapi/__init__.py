from __future__ import annotations

import base64
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, ConfigDict, Field, create_model
import requests
import yaml

from .api_wrapper import _get_base_url_from_spec, build_wrapper
from .tool import OpenApiAction
from ..elitea_base import filter_missconfigured_index_tools
from ...configurations.openapi import OpenApiConfiguration
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

logger = logging.getLogger(__name__)

name = 'openapi'

# Module-level token cache: {cache_key: (access_token, expires_at_timestamp)}
# Protected by _oauth_token_cache_lock for thread-safe access
_oauth_token_cache: Dict[str, Tuple[str, float]] = {}
_oauth_token_cache_lock = threading.Lock()

# Token expiry buffer in seconds (refresh 60 seconds before actual expiry)
_TOKEN_EXPIRY_BUFFER = 60


def _get_oauth_cache_key(client_id: str, token_url: str, scope: Optional[str]) -> str:
    """Generate a cache key for OAuth tokens."""
    return f"{client_id}:{token_url}:{scope or ''}"


def _get_cached_token(cache_key: str) -> Optional[str]:
    """Get a cached token if it exists and is not expired. Thread-safe."""
    with _oauth_token_cache_lock:
        if cache_key not in _oauth_token_cache:
            return None
        token, expires_at = _oauth_token_cache[cache_key]
        if time.time() >= expires_at - _TOKEN_EXPIRY_BUFFER:
            # Token expired or about to expire
            del _oauth_token_cache[cache_key]
            return None
        return token


def _cache_token(cache_key: str, token: str, expires_in: Optional[int]) -> None:
    """Cache a token with its expiry time. Thread-safe."""
    # Default to 1 hour if expires_in not provided
    expires_in = expires_in or 3600
    expires_at = time.time() + expires_in
    with _oauth_token_cache_lock:
        _oauth_token_cache[cache_key] = (token, expires_at)


def _obtain_oauth_token(
    client_id: str,
    client_secret: str,
    token_url: str,
    scope: Optional[str] = None,
    method: str = 'default',
    timeout: int = 30,
) -> Tuple[str, Optional[str]]:
    """
    Obtain an OAuth2 access token using client credentials flow.
    
    Args:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint URL
        scope: Optional OAuth scope(s), space-separated if multiple
        method: Token exchange method - 'default' (POST body) or 'Basic' (Basic auth header)
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (access_token, error_message)
        On success: (token, None)
        On failure: (None, error_message)
    """
    try:
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }
        
        # Build form data
        data: Dict[str, str] = {
            'grant_type': 'client_credentials',
        }
        
        if method == 'Basic':
            # Use Basic auth header for client credentials
            credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
            headers['Authorization'] = f'Basic {encoded_credentials}'
        else:
            # Default: include credentials in POST body
            data['client_id'] = client_id
            data['client_secret'] = client_secret
        
        if scope:
            data['scope'] = scope
        
        # Log only the domain to avoid exposing sensitive path parameters (e.g., tenant IDs)
        token_domain = urlparse(token_url).netloc or 'unknown'
        logger.debug(f"OAuth token request to {token_domain} using method '{method}'")
        
        response = requests.post(
            token_url,
            headers=headers,
            data=data,
            timeout=timeout,
        )
        
        if response.status_code == 200:
            try:
                token_data = response.json()
                access_token = token_data.get('access_token')
                if not access_token:
                    return None, "OAuth response did not contain 'access_token'"
                
                # Cache the token
                cache_key = _get_oauth_cache_key(client_id, token_url, scope)
                expires_in = token_data.get('expires_in')
                _cache_token(cache_key, access_token, expires_in)
                
                logger.debug(f"OAuth token obtained successfully (expires_in: {expires_in})")
                return access_token, None
            except json.JSONDecodeError as e:
                return None, f"Failed to parse OAuth token response as JSON: {e}"
        
        # Handle error responses
        error_msg = f"OAuth token request failed with status {response.status_code}"
        try:
            error_data = response.json()
            if 'error' in error_data:
                error_msg = f"{error_msg}: {error_data.get('error')}"
                if 'error_description' in error_data:
                    error_msg = f"{error_msg} - {error_data.get('error_description')}"
        except Exception:
            if response.text:
                error_msg = f"{error_msg}: {response.text[:500]}"
        
        return None, error_msg
        
    except requests.exceptions.Timeout:
        return None, f"OAuth token request to {token_url} timed out"
    except requests.exceptions.ConnectionError as e:
        return None, f"Failed to connect to OAuth token endpoint {token_url}: {e}"
    except requests.exceptions.RequestException as e:
        return None, f"OAuth token request failed: {e}"
    except Exception as e:
        return None, f"Unexpected error during OAuth token exchange: {e}"


def _secret_to_str(value: Any) -> Optional[str]:
    """Convert a secret value to string, handling SecretStr and other types."""
    if value is None:
        return None
    if hasattr(value, 'get_secret_value'):
        try:
            value = value.get_secret_value()
        except Exception:
            pass
    if isinstance(value, str):
        return value
    return str(value)


def _get_oauth_access_token(settings: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Get an OAuth access token from settings, using cache if available.
    
    Args:
        settings: Dictionary containing OAuth configuration
    
    Returns:
        Tuple of (access_token, error_message)
        On success: (token, None)
        On failure: (None, error_message)
        If OAuth not configured: (None, None)
    """
    client_id = settings.get('client_id')
    client_secret = _secret_to_str(settings.get('client_secret'))
    token_url = settings.get('token_url')
    
    # Check if OAuth is configured
    if not client_id or not client_secret or not token_url:
        return None, None  # OAuth not configured
    
    scope = settings.get('scope')
    method = settings.get('method', 'default') or 'default'
    
    # Try to get cached token
    cache_key = _get_oauth_cache_key(client_id, token_url, scope)
    cached_token = _get_cached_token(cache_key)
    if cached_token:
        logger.debug("Using cached OAuth token")
        return cached_token, None
    
    # Obtain new token
    return _obtain_oauth_token(
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
        scope=scope,
        method=method,
    )


def get_toolkit(tool) -> BaseToolkit:
    settings = tool.get('settings', {}) or {}
    # Extract selected_tools separately to avoid duplicate keyword argument when unpacking **settings
    selected_tools = settings.get('selected_tools', [])
    # Filter out selected_tools from settings to prevent "got multiple values for keyword argument"
    filtered_settings = {k: v for k, v in settings.items() if k != 'selected_tools'}
    return AlitaOpenAPIToolkit.get_toolkit(
        selected_tools=selected_tools,
        toolkit_name=tool.get('toolkit_name'),
        **filtered_settings,
    )


def get_tools(tool):
    return get_toolkit(tool).get_tools()


def get_toolkit_available_tools(settings: dict) -> dict:
    """Return instance-dependent tool list + per-tool args JSON schemas.

    This is used by backend services when the UI needs spec-derived tool names
    and input schemas (one tool per operationId). It must be JSON-serializable.
    """
    if not isinstance(settings, dict):
        settings = {}

    # Extract and merge openapi_configuration if present (same pattern as get_toolkit)
    openapi_configuration = settings.get('openapi_configuration') or {}
    if hasattr(openapi_configuration, 'model_dump'):
        openapi_configuration = openapi_configuration.model_dump(mode='json')
    if not isinstance(openapi_configuration, dict):
        openapi_configuration = {}

    # Merge settings with openapi_configuration so api_key, auth_type etc. are at root level
    merged_settings: Dict[str, Any] = {
        **settings,
        **openapi_configuration,
    }

    spec = merged_settings.get('spec') or merged_settings.get('schema_settings') or merged_settings.get('openapi_spec')
    base_url_override = merged_settings.get('base_url') or merged_settings.get('base_url_override')

    if not spec or not isinstance(spec, (str, dict)):
        return {"tools": [], "args_schemas": {}, "error": "OpenAPI spec is missing"}

    try:
        headers = _build_headers_from_settings(merged_settings)
        api_wrapper = build_wrapper(
            openapi_spec=spec,
            base_headers=headers,
            base_url_override=base_url_override,
        )

        tool_defs = api_wrapper.get_available_tools(selected_tools=None)

        tools = []
        args_schemas = {}

        for tool_def in tool_defs:
            name_val = tool_def.get('name')
            if not isinstance(name_val, str) or not name_val:
                continue

            desc_val = tool_def.get('description')
            if not isinstance(desc_val, str):
                desc_val = ''

            tools.append({"name": name_val, "description": desc_val})

            args_schema = tool_def.get('args_schema')
            if args_schema is None:
                args_schemas[name_val] = {"type": "object", "properties": {}, "required": []}
                continue

            try:
                if hasattr(args_schema, 'model_json_schema'):
                    args_schemas[name_val] = args_schema.model_json_schema()
                elif hasattr(args_schema, 'schema'):
                    args_schemas[name_val] = args_schema.schema()
                else:
                    args_schemas[name_val] = {"type": "object", "properties": {}, "required": []}
            except Exception:
                args_schemas[name_val] = {"type": "object", "properties": {}, "required": []}

        # Ensure stable JSON-serializability.
        try:
            json.dumps({"tools": tools, "args_schemas": args_schemas})
        except Exception:
            return {"tools": tools, "args_schemas": {}}

        return {"tools": tools, "args_schemas": args_schemas}

    except Exception as e:  # pylint: disable=W0718
        return {"tools": [], "args_schemas": {}, "error": str(e)}

class AlitaOpenAPIToolkit(BaseToolkit):
    request_session: Any  #: :meta private:
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        # OpenAPI tool names + per-tool args schemas depend on the user-provided spec,
        # so `selected_tools` cannot be an enum here (unlike most toolkits).

        model = create_model(
            name,
            __config__=ConfigDict(
                extra='ignore',
                json_schema_extra={
                    'metadata': {
                        'label': 'OpenAPI',
                        'icon_url': 'openapi.svg',
                        'categories': ['integrations'],
                        'extra_categories': ['api', 'openapi', 'swagger'],
                    }
                }
            ),
            openapi_configuration=(
                OpenApiConfiguration,
                Field(
                    description='OpenAPI credentials configuration',
                    json_schema_extra={'configuration_types': ['openapi']},
                ),
            ),
            base_url=(
                Optional[str],
                Field(
                    default=None,
                    description=(
                        "Optional base URL override (absolute, starting with http:// or https://). "
                        "Use this when your OpenAPI spec has no `servers` entry, or when `servers[0].url` "
                        "is not absolute (e.g. '/api/v3'). Example: 'https://petstore3.swagger.io'."
                    ),
                ),
            ),
            spec=(
                str,
                Field(
                    description=(
                        'OpenAPI specification (URL or raw JSON/YAML text). '
                        'Used to generate per-operation tools (one tool per operationId).'
                    ),
                    json_schema_extra={'ui_component': 'openapi_spec'},
                ),
            ),
            selected_tools=(
                List[str],
                Field(
                    default=[],
                    description='Optional list of operationIds to enable. If empty, all operations are enabled.',
                    json_schema_extra={'args_schemas': {}},
                ),
            ),
        )
        return model

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(
        cls,
        selected_tools: list[str] | None = None,
        toolkit_name: Optional[str] = None,
        **kwargs,
    ):
        if selected_tools is None:
            selected_tools = []

        tool_names = _coerce_selected_tool_names(selected_tools)

        openapi_configuration = kwargs.get('openapi_configuration') or {}
        if hasattr(openapi_configuration, 'model_dump'):
            openapi_configuration = openapi_configuration.model_dump(mode='json')
        if not isinstance(openapi_configuration, dict):
            openapi_configuration = {}

        merged_settings: Dict[str, Any] = {
            **kwargs,
            **openapi_configuration,
        }

        openapi_spec = merged_settings.get('spec') or merged_settings.get('schema_settings') or merged_settings.get('openapi_spec')
        base_url_override = merged_settings.get('base_url') or merged_settings.get('base_url_override')
        headers = _build_headers_from_settings(merged_settings)

        api_wrapper = build_wrapper(
            openapi_spec=openapi_spec,
            base_headers=headers,
            base_url_override=base_url_override,
        )
        base_url = _get_base_url_from_spec(api_wrapper.spec)

        tools: List[BaseTool] = []
        for tool_def in api_wrapper.get_available_tools(selected_tools=tool_names):
            description = tool_def.get('description') or ''
            if toolkit_name:
                description = f"{description}\nToolkit: {toolkit_name}"
            if base_url:
                description = f"{description}\nBase URL: {base_url}"
            description = description[:1000]

            tools.append(
                OpenApiAction(
                    api_wrapper=api_wrapper,
                    name=tool_def['name'],
                    description=description,
                    args_schema=tool_def.get('args_schema'),
                    metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool_def["name"]} if toolkit_name else {TOOL_NAME_META: tool_def["name"]},
                )
            )

        return cls(request_session=api_wrapper, tools=tools)

    def get_tools(self):
        return self.tools


def _coerce_selected_tool_names(selected_tools: Any) -> list[str]:
    if not selected_tools:
        return []

    if isinstance(selected_tools, list):
        tool_names: List[str] = []
        for item in selected_tools:
            if isinstance(item, str):
                tool_names.append(item)
            elif isinstance(item, dict):
                name_val = item.get('name')
                if isinstance(name_val, str) and name_val.strip():
                    tool_names.append(name_val)
        return [t for t in tool_names if t]

    return []


def _build_headers_from_settings(settings: Dict[str, Any]) -> Dict[str, str]:
    """
    Build HTTP headers from settings, supporting API key and OAuth authentication.
    
    Authentication priority:
    1. OAuth (client credentials flow) - if client_id, client_secret, and token_url are provided
    2. API Key - if api_key is provided
    3. Legacy authentication structure (for backward compatibility)
    
    Args:
        settings: Dictionary containing authentication settings
        
    Returns:
        Dictionary of HTTP headers to include in requests
    """
    headers: Dict[str, str] = {}

    # First, try OAuth authentication (client credentials flow)
    # This takes priority because it's more secure and commonly used with modern APIs
    oauth_token, oauth_error = _get_oauth_access_token(settings)
    if oauth_token:
        headers['Authorization'] = f'Bearer {oauth_token}'
        logger.debug("Using OAuth Bearer token for authentication")
        return headers
    elif oauth_error:
        # OAuth was configured but failed - log the error
        # We'll still try API key auth as fallback
        logger.warning(f"OAuth token exchange failed: {oauth_error}")

    # Legacy structure used by the custom OpenAPI UI
    auth = settings.get('authentication')
    if isinstance(auth, dict) and auth.get('type') == 'api_key':
        auth_settings = auth.get('settings') or {}
        if isinstance(auth_settings, dict):
            auth_type = str(auth_settings.get('auth_type', '')).strip().lower()
            api_key = _secret_to_str(auth_settings.get('api_key'))
            if api_key:
                if auth_type == 'bearer':
                    headers['Authorization'] = f'Bearer {api_key}'
                elif auth_type == 'basic':
                    headers['Authorization'] = f'Basic {api_key}'
                elif auth_type == 'custom':
                    header_name = auth_settings.get('custom_header_name')
                    if header_name:
                        headers[str(header_name)] = f'{api_key}'

    # New regular-schema structure (GitHub-style sections) uses flattened fields
    if not headers:
        api_key = _secret_to_str(settings.get('api_key'))
        if api_key:
            auth_type = str(settings.get('auth_type', 'Bearer'))
            auth_type_norm = auth_type.strip().lower()
            if auth_type_norm == 'bearer':
                headers['Authorization'] = f'Bearer {api_key}'
            elif auth_type_norm == 'basic':
                headers['Authorization'] = f'Basic {api_key}'
            elif auth_type_norm == 'custom':
                header_name = settings.get('custom_header_name')
                if header_name:
                    headers[str(header_name)] = f'{api_key}'

    return headers
