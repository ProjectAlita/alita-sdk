import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from traceback import format_exc

import requests
from langchain_core.tools import ToolException
from pydantic import Field, model_validator, create_model, SecretStr

from ..elitea_base import BaseToolApiWrapper
from .postman_analysis import PostmanAnalyzer

logger = logging.getLogger(__name__)

# Pydantic models for request schemas
PostmanGetCollections = create_model(
    "PostmanGetCollections"
)

PostmanGetCollection = create_model(
    "PostmanGetCollection"
)

PostmanGetCollectionFlat = create_model(
    "PostmanGetCollectionFlat"
)

PostmanGetFolderFlat = create_model(
    "PostmanGetFolderFlat",
    folder_path=(str, Field(
        description="The path to the folder to parse (e.g., 'API/Users' for nested folders)"))
)

PostmanGetFolder = create_model(
    "PostmanGetFolder",
    folder_path=(str, Field(
        description="The path to the folder (e.g., 'API/Users' for nested folders)"))
)

PostmanGetFolderRequests = create_model(
    "PostmanGetFolderRequests",
    folder_path=(str, Field(description="The path to the folder")),
    include_details=(bool, Field(
        description="Include detailed request information", default=False))
)

PostmanSearchRequests = create_model(
    "PostmanSearchRequests",
    query=(str, Field(description="The search query")),
    search_in=(str, Field(
        description="Where to search: name, url, description, all", default="all")),
    method=(Optional[str], Field(
        description="Optional HTTP method filter", default=None))
)

PostmanAnalyze = create_model(
    "PostmanAnalyze",
    scope=(str, Field(
        description="The scope of analysis: 'collection', 'folder', or 'request'", 
        default="collection")),
    target_path=(Optional[str], Field(
        description="The path to the folder or request to analyze (required for folder/request scope)", 
        default=None)),
    include_improvements=(bool, Field(
        description="Include improvement suggestions in the analysis", 
        default=False))
)

PostmanCreateCollection = create_model(
    "PostmanCreateCollection",
    name=(str, Field(description="The name of the new collection")),
    description=(Optional[str], Field(
        description="Optional description for the collection", default=None)),
    variables=(Optional[List[Dict]], Field(
        description="Optional collection variables", default=None)),
    auth=(Optional[Dict], Field(
        description="Optional default authentication", default=None))
)

PostmanUpdateCollectionName = create_model(
    "PostmanUpdateCollectionName",
    name=(str, Field(description="New name for the collection"))
)

PostmanUpdateCollectionDescription = create_model(
    "PostmanUpdateCollectionDescription",
    description=(str, Field(description="New description for the collection"))
)

PostmanUpdateCollectionVariables = create_model(
    "PostmanUpdateCollectionVariables",
    variables=(Optional[List[Dict[str, Any]]], Field(default=None,
        description="List of collection variables objects. "
                    "Example: [{'key': 'project_id', 'type': 'string', 'value': '15', 'enabled': true}]"))
)

PostmanUpdateCollectionAuth = create_model(
    "PostmanUpdateCollectionAuth",
    auth=(Optional[Dict[str, Any]], Field(default=None,
         description="Updated authentication settings. Example: {'type': 'bearer',token '': 'your_token'}"
     ))
)

PostmanDeleteCollection = create_model(
    "PostmanDeleteCollection"
)

PostmanDuplicateCollection = create_model(
    "PostmanDuplicateCollection",
    new_name=(str, Field(description="Name for the new collection copy"))
)

PostmanCreateFolder = create_model(
    "PostmanCreateFolder",
    name=(str, Field(description="Name of the new folder")),
    description=(Optional[str], Field(
        description="Optional description for the folder", default=None)),
    parent_path=(Optional[str], Field(
        description="Optional parent folder path", default=None)),
    auth=(Optional[Dict], Field(
        description="Optional folder-level authentication", default=None))
)

PostmanUpdateFolder = create_model(
    "PostmanUpdateFolder",
    folder_path=(str, Field(description="Path to the folder to update")),
    name=(Optional[str], Field(
        description="New name for the folder", default=None)),
    description=(Optional[str], Field(
        description="New description for the folder", default=None)),
    auth=(Optional[Dict], Field(
        description="Updated authentication settings", default=None))
)

PostmanDeleteFolder = create_model(
    "PostmanDeleteFolder",
    folder_path=(str, Field(description="Path to the folder to delete"))
)

PostmanMoveFolder = create_model(
    "PostmanMoveFolder",
    source_path=(str, Field(description="Current path of the folder to move")),
    target_path=(Optional[str], Field(
        description="New parent folder path", default=None))
)

PostmanCreateRequest = create_model(
    "PostmanCreateRequest",
    folder_path=(Optional[str], Field(
        description="Path to the folder", default=None)),
    name=(str, Field(description="Name of the new request")),
    method=(str, Field(description="HTTP method for the request")),
    url=(str, Field(description="URL for the request")),
    description=(Optional[str], Field(
        description="Optional description for the request", default=None)),
    headers=(Optional[List[Dict]], Field(
        description="Optional request headers", default=None)),
    body=(Optional[Dict], Field(
        description="Optional request body", default=None)),
    auth=(Optional[Dict], Field(
        description="Optional request authentication", default=None)),
    tests=(Optional[str], Field(
        description="Optional test script code", default=None)),
    pre_request_script=(Optional[str], Field(
        description="Optional pre-request script code", default=None))
)

PostmanUpdateRequestName = create_model(
    "PostmanUpdateRequestName",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    name=(str, Field(description="New name for the request"))
)

PostmanUpdateRequestMethod = create_model(
    "PostmanUpdateRequestMethod",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    method=(str, Field(description="HTTP method for the request"))
)

PostmanUpdateRequestUrl = create_model(
    "PostmanUpdateRequestUrl",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    url=(str, Field(description="URL for the request"))
)

PostmanUpdateRequestDescription = create_model(
    "PostmanUpdateRequestDescription",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    description=(str, Field(description="Description for the request"))
)

PostmanUpdateRequestHeaders = create_model(
    "PostmanUpdateRequestHeaders",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    headers=(str, Field(description="String containing HTTP headers, separated by newline characters. "
                                    "Each header should be in the format: \"Header-Name: value\". "
                                    "Example: \"Content-Type: application/json\\nAuthorization: Bearer token123\". "))
)

PostmanUpdateRequestBody = create_model(
    "PostmanUpdateRequestBody",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    body=(Optional[Dict[str, Any]], Field(default=None, description="Request body."))
)

PostmanUpdateRequestAuth = create_model(
    "PostmanUpdateRequestAuth",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    auth=(Optional[Dict[str, Any]], Field(default=None,
        description=(
            "An object. "
            "For API key authentication, use: {\"type\": \"apikey\", \"apikey\": [{\"key\": \"key\", \"value\": \"api-key\"}, {\"key\": \"value\", \"value\": \"XXX\"}]}. "
            "For bearer authentication, use: {\"type\": \"bearer\", \"bearer\": [{\"key\": \"token\", \"value\": \"XXX\", \"type\": \"string\"}]}. "
            "For basic authentication, use: {\"type\": \"basic\", \"basic\": [{\"key\": \"username\", \"value\": \"user\"}, {\"key\": \"password\", \"value\": \"pass\"}]}. "
            "`type`: Authentication type (e.g., \"apikey\", \"bearer\", \"basic\"). "
            "`apikey`, `bearer`, `basic`: List of key-value pairs for configuration."
            "Other types can be added as needed, following the same structure."
        )))
)

PostmanUpdateRequestTests = create_model(
    "PostmanUpdateRequestTests",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    tests=(str, Field(description="Test script code"))
)

PostmanUpdateRequestPreScript = create_model(
    "PostmanUpdateRequestPreScript",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    pre_request_script=(str, Field(description="Pre-request script code"))
)

PostmanDeleteRequest = create_model(
    "PostmanDeleteRequest",
    request_path=(str, Field(description="Path to the request to delete"))
)

PostmanDuplicateRequest = create_model(
    "PostmanDuplicateRequest",
    source_path=(str, Field(description="Path to the request to duplicate")),
    new_name=(str, Field(description="Name for the duplicated request")),
    target_path=(Optional[str], Field(
        description="Target folder path", default=None))
)

PostmanMoveRequest = create_model(
    "PostmanMoveRequest",
    source_path=(str, Field(
        description="Current path of the request to move")),
    target_path=(Optional[str], Field(
        description="New folder path", default=None))
)

PostmanGetRequestByPath = create_model(
    "PostmanGetRequestByPath",
    request_path=(str, Field(
        description="The path to the request (e.g., 'API/Users/Get User' or 'applications/recommendations')"))
)

PostmanGetRequestById = create_model(
    "PostmanGetRequestById",
    request_id=(str, Field(
        description="The unique ID of the request"))
)

PostmanGetRequestScript = create_model(
    "PostmanGetRequestScript",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    script_type=(str, Field(description="The type of script to retrieve: 'test' or 'prerequest'", default="prerequest"))
)

PostmanExecuteRequest = create_model(
    "PostmanExecuteRequest",
    request_path=(str, Field(description="The path to the request in the collection (e.g., 'API/Users/Get User')")),
    override_variables=(Optional[Dict[str, Any]], Field(description="Optional variables to override environment/collection variables", default=None))
)


class PostmanApiWrapper(BaseToolApiWrapper):
    """Wrapper for Postman API."""

    api_key: SecretStr
    base_url: str = "https://api.getpostman.com"
    collection_id: Optional[str] = None
    workspace_id: Optional[str] = None
    environment_config: dict = {}
    timeout: int = 30
    session: Any = None
    analyzer: PostmanAnalyzer = None

    model_config = {
        "arbitrary_types_allowed": True
    }

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        try:
            import requests  # noqa: F401
        except ImportError:
            raise ImportError(
                "`requests` package not found, please run "
                "`pip install requests`"
            )
        values["session"] = requests.Session()
        values["session"].headers.update({
            'X-API-Key': values.get('api_key'),
            'Content-Type': 'application/json'
        })
        values["analyzer"] = PostmanAnalyzer()
        return values


    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Postman API."""
        url = f"{self.base_url.rstrip('/')}{endpoint}"

        try:
            logger.info(f"Making {method.upper()} request to {url}")
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()

            if response.content:
                return response.json()
            return {}

        except requests.exceptions.RequestException as e:
            error_details = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = f" Response content: {e.response.text}"
                except:
                    error_details = f" Response status: {e.response.status_code}"
            logger.error(f"Request failed: {e}{error_details}")
            raise ToolException(f"Postman API request failed: {str(e)}{error_details}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response: {e}")
            raise ToolException(
                f"Invalid JSON response from Postman API: {str(e)}")

    def _apply_authentication(self, headers, params, all_variables, resolve_variables):
        """Apply authentication based on environment_config auth settings.
        
        Supports multiple authentication types:
        - bearer: Bearer token in Authorization header
        - basic: Basic authentication in Authorization header  
        - api_key: API key in header, query parameter, or cookie
        - oauth2: OAuth2 access token in Authorization header
        - custom: Custom headers, cookies, or query parameters
        
        Required format:
        environment_config = {
            "auth": {
                "type": "bearer|basic|api_key|oauth2|custom",
                "params": {
                    # type-specific parameters
                }
            }
        }
        """
        import base64
        
        # Handle structured auth configuration only - no backward compatibility
        auth_config = self.environment_config.get('auth')
        if auth_config and isinstance(auth_config, dict):
            auth_type = auth_config.get('type', '').lower()
            auth_params = auth_config.get('params', {})
            
            if auth_type == 'bearer':
                # Bearer token authentication
                token = resolve_variables(str(auth_params.get('token', '')))
                if token:
                    headers['Authorization'] = f'Bearer {token}'
                    
            elif auth_type == 'basic':
                # Basic authentication
                username = resolve_variables(str(auth_params.get('username', '')))
                password = resolve_variables(str(auth_params.get('password', '')))
                if username and password:
                    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                    headers['Authorization'] = f'Basic {credentials}'
                    
            elif auth_type == 'api_key':
                # API key authentication
                key_name = resolve_variables(str(auth_params.get('key', '')))
                key_value = resolve_variables(str(auth_params.get('value', '')))
                key_location = auth_params.get('in', 'header').lower()
                
                if key_name and key_value:
                    if key_location == 'header':
                        headers[key_name] = key_value
                    elif key_location == 'query':
                        params[key_name] = key_value
                    elif key_location == 'cookie':
                        # Add to Cookie header
                        existing_cookies = headers.get('Cookie', '')
                        new_cookie = f"{key_name}={key_value}"
                        if existing_cookies:
                            headers['Cookie'] = f"{existing_cookies}; {new_cookie}"
                        else:
                            headers['Cookie'] = new_cookie
                            
            elif auth_type == 'oauth2':
                # OAuth2 access token
                access_token = resolve_variables(str(auth_params.get('access_token', '')))
                if access_token:
                    headers['Authorization'] = f'Bearer {access_token}'
                    
            elif auth_type == 'custom':
                # Custom authentication - allows full control
                custom_headers = auth_params.get('headers', {})
                custom_cookies = auth_params.get('cookies', {})
                custom_query = auth_params.get('query', {})
                
                # Add custom headers
                for key, value in custom_headers.items():
                    resolved_key = resolve_variables(str(key))
                    resolved_value = resolve_variables(str(value))
                    headers[resolved_key] = resolved_value
                
                # Add custom query parameters
                for key, value in custom_query.items():
                    resolved_key = resolve_variables(str(key))
                    resolved_value = resolve_variables(str(value))
                    params[resolved_key] = resolved_value
                
                # Add custom cookies
                if custom_cookies:
                    cookie_parts = []
                    for key, value in custom_cookies.items():
                        resolved_key = resolve_variables(str(key))
                        resolved_value = resolve_variables(str(value))
                        cookie_parts.append(f"{resolved_key}={resolved_value}")
                    
                    existing_cookies = headers.get('Cookie', '')
                    new_cookies = "; ".join(cookie_parts)
                    if existing_cookies:
                        headers['Cookie'] = f"{existing_cookies}; {new_cookies}"
                    else:
                        headers['Cookie'] = new_cookies


    def get_available_tools(self):
        """Return list of available tools with their configurations."""
        return [
            {
                "name": "get_collections",
                "mode": "get_collections",
                "description": "Get all Postman collections accessible to the user",
                "args_schema": PostmanGetCollections,
                "ref": self.get_collections
            },
            # {
            #     "name": "get_collection",
            #     "mode": "get_collection",
            #     "description": "Get a specific Postman collection by ID",
            #     "args_schema": PostmanGetCollection,
            #     "ref": self.get_collection
            # },
            {
                "name": "get_collection",
                "mode": "get_collection",
                "description": "Get a specific Postman collection in flattened format with path-based structure",
                "args_schema": PostmanGetCollectionFlat,
                "ref": self.get_collection_flat
            },
            {
                "name": "get_folder",
                "mode": "get_folder",
                "description": "Get a specific folder in flattened format with path-based structure",
                "args_schema": PostmanGetFolderFlat,
                "ref": self.get_folder_flat
            },
            # {
            #     "name": "get_folder",
            #     "mode": "get_folder",
            #     "description": "Get folders from a collection by path (supports nested paths like 'API/Users')",
            #     "args_schema": PostmanGetFolder,
            #     "ref": self.get_folder
            # },
            # {
            #     "name": "get_folder_requests",
            #     "mode": "get_folder_requests",
            #     "description": "Get detailed information about all requests in a folder",
            #     "args_schema": PostmanGetFolderRequests,
            #     "ref": self.get_folder_requests
            # },
            {
                "name": "get_request_by_path",
                "mode": "get_request_by_path",
                "description": "Get a specific request by path",
                "args_schema": PostmanGetRequestByPath,
                "ref": self.get_request_by_path
            },
            {
                "name": "get_request_by_id",
                "mode": "get_request_by_id",
                "description": "Get a specific request by ID",
                "args_schema": PostmanGetRequestById,
                "ref": self.get_request_by_id
            },
            {
                "name": "get_request_script",
                "mode": "get_request_script",
                "description": "Get the test or pre-request script content for a specific request",
                "args_schema": PostmanGetRequestScript,
                "ref": self.get_request_script
            },
            {
                "name": "search_requests",
                "mode": "search_requests",
                "description": "Search for requests across the collection",
                "args_schema": PostmanSearchRequests,
                "ref": self.search_requests
            },
            {
                "name": "analyze",
                "mode": "analyze",
                "description": "Analyze collection, folder, or request for API quality, best practices, and issues",
                "args_schema": PostmanAnalyze,
                "ref": self.analyze
            },
            {
                "name": "execute_request",
                "mode": "execute_request",
                "description": "Execute a Postman request with environment variables and custom configuration",
                "args_schema": PostmanExecuteRequest,
                "ref": self.execute_request
            },
            # {
            #     "name": "create_collection",
            #     "mode": "create_collection",
            #     "description": "Create a new Postman collection",
            #     "args_schema": PostmanCreateCollection,
            #     "ref": self.create_collection
            # },
            # {
            #     "name": "update_collection_name",
            #     "mode": "update_collection_name",
            #     "description": "Update collection name",
            #     "args_schema": PostmanUpdateCollectionName,
            #     "ref": self.update_collection_name
            # },
            {
                "name": "update_collection_description",
                "mode": "update_collection_description",
                "description": "Update collection description",
                "args_schema": PostmanUpdateCollectionDescription,
                "ref": self.update_collection_description
            },
            {
                "name": "update_collection_variables",
                "mode": "update_collection_variables",
                "description": "Update collection variables",
                "args_schema": PostmanUpdateCollectionVariables,
                "ref": self.update_collection_variables
            },
            {
                "name": "update_collection_auth",
                "mode": "update_collection_auth",
                "description": "Update collection authentication settings",
                "args_schema": PostmanUpdateCollectionAuth,
                "ref": self.update_collection_auth
            },
            # {
            #     "name": "delete_collection",
            #     "mode": "delete_collection",
            #     "description": "Delete a collection permanently",
            #     "args_schema": PostmanDeleteCollection,
            #     "ref": self.delete_collection
            # },
            {
                "name": "duplicate_collection",
                "mode": "duplicate_collection",
                "description": "Create a copy of an existing collection",
                "args_schema": PostmanDuplicateCollection,
                "ref": self.duplicate_collection
            },

            {
                "name": "create_folder",
                "mode": "create_folder",
                "description": "Create a new folder in a collection",
                "args_schema": PostmanCreateFolder,
                "ref": self.create_folder
            },
            {
                "name": "update_folder",
                "mode": "update_folder",
                "description": "Update folder properties (name, description, auth)",
                "args_schema": PostmanUpdateFolder,
                "ref": self.update_folder
            },
            # {
            #     "name": "delete_folder",
            #     "mode": "delete_folder",
            #     "description": "Delete a folder and all its contents permanently",
            #     "args_schema": PostmanDeleteFolder,
            #     "ref": self.delete_folder
            # },
            {
                "name": "move_folder",
                "mode": "move_folder",
                "description": "Move a folder to a different location within the collection",
                "args_schema": PostmanMoveFolder,
                "ref": self.move_folder
            },
            {
                "name": "create_request",
                "mode": "create_request",
                "description": "Create a new API request in a folder",
                "args_schema": PostmanCreateRequest,
                "ref": self.create_request
            },
            {
                "name": "update_request_name",
                "mode": "update_request_name",
                "description": "Update request name",
                "args_schema": PostmanUpdateRequestName,
                "ref": self.update_request_name
            },
            {
                "name": "update_request_method",
                "mode": "update_request_method",
                "description": "Update request HTTP method",
                "args_schema": PostmanUpdateRequestMethod,
                "ref": self.update_request_method
            },
            {
                "name": "update_request_url",
                "mode": "update_request_url",
                "description": "Update request URL",
                "args_schema": PostmanUpdateRequestUrl,
                "ref": self.update_request_url
            },
            {
                "name": "update_request_description",
                "mode": "update_request_description",
                "description": "Update request description",
                "args_schema": PostmanUpdateRequestDescription,
                "ref": self.update_request_description
            },
            {
                "name": "update_request_headers",
                "mode": "update_request_headers",
                "description": "Update request headers",
                "args_schema": PostmanUpdateRequestHeaders,
                "ref": self.update_request_headers
            },
            {
                "name": "update_request_body",
                "mode": "update_request_body",
                "description": "Update request body",
                "args_schema": PostmanUpdateRequestBody,
                "ref": self.update_request_body
            },
            {
                "name": "update_request_auth",
                "mode": "update_request_auth",
                "description": "Update request authentication",
                "args_schema": PostmanUpdateRequestAuth,
                "ref": self.update_request_auth
            },
            {
                "name": "update_request_tests",
                "mode": "update_request_tests",
                "description": "Update request test scripts",
                "args_schema": PostmanUpdateRequestTests,
                "ref": self.update_request_tests
            },
            {
                "name": "update_request_pre_script",
                "mode": "update_request_pre_script",
                "description": "Update request pre-request scripts",
                "args_schema": PostmanUpdateRequestPreScript,
                "ref": self.update_request_pre_script
            },
            # {
            #     "name": "delete_request",
            #     "mode": "delete_request",
            #     "description": "Delete an API request permanently",
            #     "args_schema": PostmanDeleteRequest,
            #     "ref": self.delete_request
            # },
            {
                "name": "duplicate_request",
                "mode": "duplicate_request",
                "description": "Create a copy of an existing API request",
                "args_schema": PostmanDuplicateRequest,
                "ref": self.duplicate_request
            },
            {
                "name": "move_request",
                "mode": "move_request",
                "description": "Move an API request to a different folder",
                "args_schema": PostmanMoveRequest,
                "ref": self.move_request
            }
        ]

    # =================================================================
    # ANALYSIS AND READ-ONLY METHODS
    # =================================================================

    def get_collections(self, **kwargs) -> str:
        """Get all Postman collections accessible to the user."""
        try:
            response = self._make_request('GET', f'/collections?workspace={self.workspace_id}')
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when getting collections: {stacktrace}")
            raise ToolException(f"Unable to get collections: {str(e)}")

    def execute_request(self, request_path: str, override_variables: Dict = None, **kwargs) -> str:
        """Execute a Postman request with environment variables and custom configuration.
        
        This method uses the environment_config to make actual HTTP requests 
        using the requests library with structured authentication.
        
        Args:
            request_path: The path to the request in the collection
            override_variables: Optional variables to override environment/collection variables
        
        Returns:
            JSON string with comprehensive response data
        """
        try:
            import time
            from urllib.parse import urlencode, parse_qs, urlparse
            
            # Get the request from the collection
            request_item, _, collection_data = self._get_request_item_and_id(request_path)
            request_data = request_item.get('request', {})
            
            # Gather all variables from different sources
            all_variables = {}
            
            # 1. Start with environment_config variables (lowest priority)
            all_variables.update(self.environment_config)
            
            # 2. Add collection variables
            collection_variables = collection_data.get('variable', [])
            for var in collection_variables:
                if isinstance(var, dict) and 'key' in var:
                    all_variables[var['key']] = var.get('value', '')
            
            # 3. Add override variables (highest priority)
            if override_variables:
                all_variables.update(override_variables)
            
            # Helper function to resolve variables in strings
            def resolve_variables(text):
                if not isinstance(text, str):
                    return text
                
                # Replace {{variable}} patterns
                import re
                def replace_var(match):
                    var_name = match.group(1)
                    return str(all_variables.get(var_name, match.group(0)))
                
                return re.sub(r'\{\{([^}]+)\}\}', replace_var, text)
            
            # Prepare the request
            method = request_data.get('method', 'GET').upper()
            
            # Handle URL
            url_data = request_data.get('url', '')
            if isinstance(url_data, str):
                url = resolve_variables(url_data)
                params = {}
            else:
                # URL is an object
                raw_url = resolve_variables(url_data.get('raw', ''))
                url = raw_url
                
                # Extract query parameters
                params = {}
                query_params = url_data.get('query', [])
                for param in query_params:
                    if isinstance(param, dict) and not param.get('disabled', False):
                        key = resolve_variables(param.get('key', ''))
                        value = resolve_variables(param.get('value', ''))
                        if key:
                            params[key] = value
            
            # Prepare headers
            headers = {}
            
            # Handle authentication from environment_config
            self._apply_authentication(headers, params, all_variables, resolve_variables)
            
            # Add headers from request
            request_headers = request_data.get('header', [])
            for header in request_headers:
                if isinstance(header, dict) and not header.get('disabled', False):
                    key = resolve_variables(header.get('key', ''))
                    value = resolve_variables(header.get('value', ''))
                    if key:
                        headers[key] = value
            
            # Prepare body
            body = None
            content_type = headers.get('Content-Type', '').lower()
            
            request_body = request_data.get('body', {})
            if request_body:
                body_mode = request_body.get('mode', '')
                
                if body_mode == 'raw':
                    raw_body = request_body.get('raw', '')
                    body = resolve_variables(raw_body)
                    
                    # Auto-detect JSON content and set Content-Type if not already set
                    if not content_type and body.strip():
                        # Try to parse as JSON to detect if it's JSON content
                        try:
                            # Remove JavaScript-style comments before JSON parsing
                            import re
                            clean_body = re.sub(r'//.*?(?=\n|$)', '', body, flags=re.MULTILINE)
                            json.loads(clean_body)
                            headers['Content-Type'] = 'application/json'
                            content_type = 'application/json'
                            # Update body to cleaned version without comments
                            body = clean_body
                        except json.JSONDecodeError:
                            # Not JSON, leave as is
                            pass
                    
                    # Try to parse as JSON if content type suggests it
                    if 'application/json' in content_type:
                        try:
                            # Remove comments and validate JSON
                            import re
                            clean_body = re.sub(r'//.*?(?=\n|$)', '', body, flags=re.MULTILINE)
                            json.loads(clean_body)
                            body = clean_body  # Use cleaned version
                        except json.JSONDecodeError:
                            logger.warning("Body is not valid JSON despite Content-Type")
                    
                elif body_mode == 'formdata':
                    # Handle form data
                    form_data = {}
                    formdata_items = request_body.get('formdata', [])
                    for item in formdata_items:
                        if isinstance(item, dict) and not item.get('disabled', False):
                            key = resolve_variables(item.get('key', ''))
                            value = resolve_variables(item.get('value', ''))
                            if key:
                                form_data[key] = value
                    body = form_data
                    
                elif body_mode == 'urlencoded':
                    # Handle URL encoded data
                    urlencoded_data = {}
                    urlencoded_items = request_body.get('urlencoded', [])
                    for item in urlencoded_items:
                        if isinstance(item, dict) and not item.get('disabled', False):
                            key = resolve_variables(item.get('key', ''))
                            value = resolve_variables(item.get('value', ''))
                            if key:
                                urlencoded_data[key] = value
                    body = urlencode(urlencoded_data)
                    if 'content-type' not in [h.lower() for h in headers.keys()]:
                        headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            # Execute the request
            start_time = time.time()
            
            logger.info(f"Executing {method} request to {url}")
            
            # Create a new session for this request (separate from Postman API session)
            exec_session = requests.Session()
            
            # Prepare request kwargs
            request_kwargs = {
                'timeout': self.timeout,
                'params': params if params else None,
                'headers': headers if headers else None
            }
            
            # Add body based on content type and method
            if body is not None and method in ['POST', 'PUT', 'PATCH']:
                if isinstance(body, dict):
                    # Form data
                    request_kwargs['data'] = body
                elif isinstance(body, str):
                    if 'application/json' in content_type:
                        # For JSON content, parse and use json parameter for proper handling
                        try:
                            request_kwargs['json'] = json.loads(body) if body.strip() else {}
                        except json.JSONDecodeError:
                            # Fallback to raw data if JSON parsing fails
                            request_kwargs['data'] = body
                    else:
                        request_kwargs['data'] = body
                else:
                    request_kwargs['data'] = body
            
            # Execute the request
            response = exec_session.request(method, url, **request_kwargs)
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # Parse response
            response_data = {
                "request": {
                    "path": request_path,
                    "method": method,
                    "url": url,
                    "headers": dict(headers) if headers else {},
                    "params": dict(params) if params else {},
                    "body": body if body is not None else None
                },
                "response": {
                    "status_code": response.status_code,
                    "status_text": response.reason,
                    "headers": dict(response.headers),
                    "elapsed_time_seconds": round(elapsed_time, 3),
                    "size_bytes": len(response.content)
                },
                "variables_used": dict(all_variables),
                "success": response.ok
            }
            
            # Add response body
            try:
                # Try to parse as JSON
                response_data["response"]["body"] = response.json()
                response_data["response"]["content_type"] = "application/json"
            except json.JSONDecodeError:
                # Fall back to text
                try:
                    response_data["response"]["body"] = response.text
                    response_data["response"]["content_type"] = "text/plain"
                except UnicodeDecodeError:
                    # Binary content
                    response_data["response"]["body"] = f"<binary content: {len(response.content)} bytes>"
                    response_data["response"]["content_type"] = "binary"
            
            # Add error details if request failed
            if not response.ok:
                response_data["error"] = {
                    "message": f"HTTP {response.status_code}: {response.reason}",
                    "status_code": response.status_code
                }
            
            return json.dumps(response_data, indent=2)
            
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when executing request: {stacktrace}")
            raise ToolException(f"Unable to execute request '{request_path}': {str(e)}")

    def get_collection(self, **kwargs) -> str:
        """Get a specific collection by ID."""
        try:
            response = self._make_request('GET', f'/collections/{self.collection_id}')
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting collection {self.collection_id}: {stacktrace}")
            raise ToolException(
                f"Unable to get collection {self.collection_id}: {str(e)}")

    def get_collection_flat(self, **kwargs) -> str:
        """Get a specific collection by ID in flattened format."""
        try:
            response = self._make_request('GET', f'/collections/{self.collection_id}')
            flattened = self.parse_collection_to_flat_structure(response)
            return json.dumps(flattened, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting flattened collection {self.collection_id}: {stacktrace}")
            raise ToolException(
                f"Unable to get flattened collection {self.collection_id}: {str(e)}")

    def get_folder(self, folder_path: str, **kwargs) -> str:
        """Get folders from a collection by path."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            folders = self.analyzer.find_folders_by_path(
                collection['collection']['item'], folder_path)
            return json.dumps(folders, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting folder {folder_path}: {stacktrace}")
            raise ToolException(
                f"Unable to get folder {folder_path} from collection {self.collection_id}: {str(e)}")

    def get_folder_flat(self, folder_path: str, **kwargs) -> str:
        """Get a specific folder in flattened format with path-based structure."""
        try:
            response = self._make_request('GET', f'/collections/{self.collection_id}')
            flattened = self.parse_collection_to_flat_structure(response, folder_path)
            return json.dumps(flattened, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting flattened folder {folder_path}: {stacktrace}")
            raise ToolException(
                f"Unable to get flattened folder {folder_path}: {str(e)}")

    def get_folder_requests(self, folder_path: str, include_details: bool = False, **kwargs) -> str:
        """Get detailed information about all requests in a folder."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            folders = self.analyzer.find_folders_by_path(
                collection['collection']['item'], folder_path)

            if not folders:
                raise ToolException(f"Folder '{folder_path}' not found in collection '{self.collection_id}'.")

            folder = folders[0]
            requests = self.analyzer.extract_requests_from_items(
                folder.get('item', []), include_details)

            result = {
                "folder_name": folder['name'],
                "folder_path": folder_path,
                "request_count": len(requests),
                "requests": requests
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting folder requests: {stacktrace}")
            raise ToolException(
                f"Unable to get requests from folder {folder_path}: {str(e)}")

    def search_requests(self, query: str, search_in: str = "all", method: str = None, **kwargs) -> str:
        """Search for requests across the collection and return results in flattened structure."""
        try:
            collection_response = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            
            # Get the collection in flattened structure
            flattened = self.parse_collection_to_flat_structure(collection_response)
            
            # Filter only requests that match the search criteria
            matching_requests = {}
            
            for path, item in flattened['items'].items():
                if item.get('type') != 'request':
                    continue
                
                # Apply method filter if specified
                if method and item.get('method', '').upper() != method.upper():
                    continue
                
                # Apply search criteria
                match_found = False
                query_lower = query.lower()
                
                if search_in == "all" or search_in == "name":
                    # Extract request name from path (last part after /)
                    request_name = path.split('/')[-1] if '/' in path else path
                    if query_lower in request_name.lower():
                        match_found = True
                
                if not match_found and (search_in == "all" or search_in == "url"):
                    url = item.get('request_url', '') or item.get('url', '')
                    if query_lower in url.lower():
                        match_found = True
                
                if not match_found and (search_in == "all" or search_in == "description"):
                    description = item.get('description', '')
                    if isinstance(description, str) and query_lower in description.lower():
                        match_found = True
                
                if match_found:
                    matching_requests[path] = item
            
            # Create result structure similar to flattened format
            result = {
                "query": query,
                "search_in": search_in,
                "method_filter": method,
                "results_count": len(matching_requests),
                "items": matching_requests
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when searching requests: {stacktrace}")
            raise ToolException(
                f"Unable to search requests in collection {self.collection_id}: {str(e)}")

    def analyze(self, scope: str = "collection", target_path: str = None, include_improvements: bool = False, **kwargs) -> str:
        """Unified analysis method for collection, folder, or request analysis.
        
        Args:
            scope: The scope of analysis ('collection', 'folder', or 'request')
            target_path: The path to the folder or request (required for folder/request scope)
            include_improvements: Whether to include improvement suggestions
        """
        try:
            # Validate parameters
            if scope not in ["collection", "folder", "request"]:
                raise ToolException(f"Invalid scope '{scope}'. Must be 'collection', 'folder', or 'request'")
            
            if scope in ["folder", "request"] and not target_path:
                raise ToolException(f"target_path is required when scope is '{scope}'")
            
            # Get collection data
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            
            if scope == "collection":
                # Analyze entire collection
                analysis = self.analyzer.perform_collection_analysis(collection)
                
                if include_improvements:
                    improvements = self.analyzer.generate_improvements(analysis)
                    analysis["improvements"] = improvements
                    analysis["improvement_count"] = len(improvements)
                
                return json.dumps(analysis, indent=2)
                
            elif scope == "folder":
                # Analyze specific folder
                folders = self.analyzer.find_folders_by_path(
                    collection['collection']['item'], target_path)

                if not folders:
                    return json.dumps({"error": f"Folder '{target_path}' not found"}, indent=2)

                folder_analyses = []
                for folder in folders:
                    analysis = self.analyzer.perform_folder_analysis(folder, target_path)
                    
                    if include_improvements:
                        improvements = self.analyzer.generate_folder_improvements(analysis)
                        analysis["improvements"] = improvements
                        analysis["improvement_count"] = len(improvements)
                    
                    folder_analyses.append(analysis)

                return json.dumps(folder_analyses, indent=2)
                
            elif scope == "request":
                # Analyze specific request
                collection_data = collection["collection"]

                # Find the request
                request_item = self.analyzer.find_request_by_path(
                    collection_data["item"], target_path)
                if not request_item:
                    raise ToolException(f"Request '{target_path}' not found")

                # Perform request analysis
                analysis = self.analyzer.perform_request_analysis(request_item)
                analysis["request_path"] = target_path
                analysis["collection_id"] = self.collection_id
                
                if include_improvements:
                    improvements = self.analyzer.generate_request_improvements(analysis)
                    analysis["improvements"] = improvements
                    analysis["improvement_count"] = len(improvements)

                return json.dumps(analysis, indent=2)
                
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when analyzing {scope}: {stacktrace}")
            raise ToolException(
                f"Unable to analyze {scope} {target_path or self.collection_id}: {str(e)}")

    # =================================================================
    # COLLECTION MANAGEMENT METHODS
    # =================================================================

    def create_collection(self, name: str, description: str = None, variables: List[Dict] = None, auth: Dict = None, **kwargs) -> str:
        """Create a new Postman collection."""
        try:
            collection_data = {
                "collection": {
                    "info": {
                        "name": name,
                        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
                    },
                    "item": []
                }
            }

            if description:
                collection_data["collection"]["info"]["description"] = description

            if variables:
                collection_data["collection"]["variable"] = variables

            if auth:
                collection_data["collection"]["auth"] = auth

            response = self._make_request(
                'POST', '/collections', json=collection_data)
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when creating collection: {stacktrace}")
            raise ToolException(
                f"Unable to create collection '{name}': {str(e)}")

    def update_collection_name(self, name: str, **kwargs) -> str:
        """Update collection name."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = current["collection"]

            # Update name
            collection_data["info"]["name"] = name

            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection name: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {self.collection_id} name: {str(e)}")

    def update_collection_description(self, description: str, **kwargs) -> str:
        """Update collection description."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = current["collection"]

            # Update description
            collection_data["info"]["description"] = description

            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection description: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {self.collection_id} description: {str(e)}")

    def update_collection_variables(self, variables: List[Dict[str, Any]], **kwargs) -> str:
        """Update collection variables."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = current["collection"]

            # Update variables
            collection_data["variable"] = variables

            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection variables: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {self.collection_id} variables: {str(e)}")

    def update_collection_auth(self, auth: Dict[str, Any], **kwargs) -> str:
        """Update collection authentication settings."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = current["collection"]

            # Update auth
            collection_data["auth"] = auth

            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection auth: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {self.collection_id} auth: {str(e)}")

    def delete_collection(self, **kwargs) -> str:
        """Delete a collection permanently."""
        try:
            response = self._make_request(
                'DELETE', f'/collections/{self.collection_id}')
            return json.dumps({"message": f"Collection {self.collection_id} deleted successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting collection: {stacktrace}")
            raise ToolException(
                f"Unable to delete collection {self.collection_id}: {str(e)}")

    def duplicate_collection(self, new_name: str, **kwargs) -> str:
        """Create a copy of an existing collection."""
        try:
            # Get the original collection
            original = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = original["collection"]

            # Update the name and remove IDs to create a new collection
            collection_data["info"]["name"] = new_name
            if "_postman_id" in collection_data["info"]:
                del collection_data["info"]["_postman_id"]

            # Remove item IDs recursively
            self.analyzer.remove_item_ids(collection_data.get("item", []))

            response = self._make_request(
                'POST', f'/collections?workspace={self.workspace_id}', json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when duplicating collection: {stacktrace}")
            raise ToolException(
                f"Unable to duplicate collection {self.collection_id}: {str(e)}")

    # =================================================================
    # FOLDER MANAGEMENT METHODS
    # =================================================================

    def create_folder(self, name: str, description: str = None,
                      parent_path: str = None, auth: Dict = None, **kwargs) -> str:
        """Create a new folder in a collection."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Create folder item
            folder_item = {
                "name": name,
                "item": []
            }

            if description:
                folder_item["description"] = description
            if auth:
                folder_item["auth"] = auth

            # Add folder to appropriate location
            if parent_path:
                parent_folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], parent_path)
                if not parent_folders:
                    raise ToolException(
                        f"Parent folder '{parent_path}' not found")
                parent_folders[0]["item"].append(folder_item)
            else:
                collection_data["item"].append(folder_item)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Folder '{name}' created successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when creating folder: {stacktrace}")
            raise ToolException(f"Unable to create folder '{name}': {str(e)}")

    def _get_folder_id(self, folder_path: str) -> str:
        """Helper method to get folder ID by path."""
        collection = self._make_request(
            'GET', f'/collections/{self.collection_id}')
        collection_data = collection["collection"]

        # Find the folder
        folders = self.analyzer.find_folders_by_path(
            collection_data["item"], folder_path)
        if not folders:
            raise ToolException(f"Folder '{folder_path}' not found")

        folder = folders[0]

        # Get the folder ID
        folder_id = folder.get("id")
        if not folder_id:
            # If ID is not available directly, try to use the item ID
            if "_postman_id" in folder:
                folder_id = folder["_postman_id"]
            else:
                raise ToolException(f"Folder ID not found for '{folder_path}'")

        return folder_id

    def update_folder(self, folder_path: str, name: str = None,
                      description: str = None, auth: Dict = None, **kwargs) -> str:
        """Update folder properties using the direct folder endpoint."""
        try:
            # Get the folder ID
            folder_id = self._get_folder_id(folder_path)
            
            # Create update payload
            folder_update = {}
            if name:
                folder_update["name"] = name
            if description is not None:
                folder_update["description"] = description
            if auth is not None:
                folder_update["auth"] = auth
                
            # Only update if we have properties to change
            if folder_update:
                # Update folder using the direct API endpoint
                response = self._make_request('PUT', f'/collections/{self.collection_id}/folders/{folder_id}',
                                            json=folder_update)
                return json.dumps({"success": True, "message": f"Folder '{folder_path}' updated successfully"}, indent=2)
            else:
                return json.dumps({"success": True, "message": f"No changes requested for folder '{folder_path}'"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating folder: {stacktrace}")
            raise ToolException(
                f"Unable to update folder '{folder_path}': {str(e)}")
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating folder: {stacktrace}")
            raise ToolException(
                f"Unable to update folder '{folder_path}': {str(e)}")

    def delete_folder(self, folder_path: str, **kwargs) -> str:
        """Delete a folder and all its contents permanently."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find and remove the folder
            if self.analyzer.remove_folder_by_path(collection_data["item"], folder_path):
                # Update collection
                response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                              json={"collection": collection_data})
                return json.dumps({"message": f"Folder '{folder_path}' deleted successfully"}, indent=2)
            else:
                raise ToolException(f"Folder '{folder_path}' not found")
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting folder: {stacktrace}")
            raise ToolException(
                f"Unable to delete folder '{folder_path}': {str(e)}")

    def move_folder(self, source_path: str, target_path: str = None, **kwargs) -> str:
        """Move a folder to a different location within the collection."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find source folder
            source_folder = self.analyzer.find_folders_by_path(
                collection_data["item"], source_path)
            if not source_folder:
                raise ToolException(f"Source folder '{source_path}' not found")

            folder_data = source_folder[0].copy()

            # Remove from source location
            self.analyzer.remove_folder_by_path(collection_data["item"], source_path)

            # Add to target location
            if target_path:
                target_folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], target_path)
                if not target_folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                target_folders[0]["item"].append(folder_data)
            else:
                collection_data["item"].append(folder_data)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Folder moved from '{source_path}' to '{target_path or 'root'}'"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when moving folder: {stacktrace}")
            raise ToolException(
                f"Unable to move folder from '{source_path}': {str(e)}")

    # =================================================================
    # REQUEST MANAGEMENT METHODS
    # =================================================================

    def create_request(self, name: str, method: str, url: str,
                       folder_path: str = None, description: str = None, headers: List[Dict] = None,
                       body: Dict = None, auth: Dict = None, tests: str = None,
                       pre_request_script: str = None, **kwargs) -> str:
        """Create a new API request in a folder."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Create request item
            request_item = {
                "name": name,
                "request": {
                    "method": method.upper(),
                    "header": headers or [],
                    "url": url
                }
            }

            if description:
                request_item["request"]["description"] = description
            if body:
                request_item["request"]["body"] = body
            if auth:
                request_item["request"]["auth"] = auth

            # Add events if provided
            events = []
            if pre_request_script:
                events.append({
                    "listen": "prerequest",
                    "script": {
                        "exec": pre_request_script.split('\n'),
                        "type": "text/javascript"
                    }
                })
            if tests:
                events.append({
                    "listen": "test",
                    "script": {
                        "exec": tests.split('\n'),
                        "type": "text/javascript"
                    }
                })
            if events:
                request_item["event"] = events

            # Add request to appropriate location
            if folder_path:
                folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], folder_path)
                if not folders:
                    raise ToolException(f"Folder '{folder_path}' not found")
                folders[0]["item"].append(request_item)
            else:
                collection_data["item"].append(request_item)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{name}' created successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when creating request: {stacktrace}")
            raise ToolException(f"Unable to create request '{name}': {str(e)}")

    def update_request_name(self, request_path: str, name: str, **kwargs) -> str:
        """Update request name."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Create update payload
            request_update = {
                "name": name
            }

            # Update the name field
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' name updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request name: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' name: {str(e)}")

    def update_request_method(self, request_path: str, method: str, **kwargs) -> str:
        """Update request HTTP method."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Create update payload
            request_update = {
                "method": method.upper()
            }

            # Update the method field
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' method updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request method: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' method: {str(e)}")

    def update_request_url(self, request_path: str, url: str, **kwargs) -> str:
        """Update request URL."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Create update payload
            request_update = {
                "url": url
            }

            # Update the URL field
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' URL updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request URL: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' URL: {str(e)}")

    def _get_request_item_and_id(self, request_path: str) -> Tuple[Dict, str, Dict]:
        """Helper method to get request item and ID by path. Returns (request_item, request_id, collection_data)."""
        collection = self._make_request(
            'GET', f'/collections/{self.collection_id}')
        collection_data = collection["collection"]

        # Find the request
        request_item = self.analyzer.find_request_by_path(
            collection_data["item"], request_path)
        if not request_item:
            raise ToolException(f"Request '{request_path}' not found")

        # Get the request ID
        request_id = request_item.get("id")
        if not request_id:
            # If ID is not available directly, try to use the full item ID path
            if "_postman_id" in request_item:
                request_id = request_item["_postman_id"]
            else:
                raise ToolException(f"Request ID not found for '{request_path}'")

        return request_item, request_id, collection_data
        
    def update_request_description(self, request_path: str, description: str, **kwargs) -> str:
        """Update request description."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # For description update, we need to properly format the payload
            # according to Postman API requirements
            request_update = {
                "description": description
            }

            # Update only the description field
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' description updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request description: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' description: {str(e)}")

    def update_request_headers(self, request_path: str, headers: str, **kwargs) -> str:
        """Update request headers."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Create update payload
            request_update = {
                "headers": headers
            }

            # Update the headers field
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' headers updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request headers: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' headers: {str(e)}")

    def update_request_body(self, request_path: str, body: Dict[str, Any], **kwargs) -> str:
        """Update request body."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Create update payload
            request_update = body

            # Update the body field
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' body updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request body: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' body: {str(e)}")

    def update_request_auth(self, request_path: str, auth: Dict[str, Any], **kwargs) -> str:
        """Update request authentication."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Create update payload
            request_update = {
                "auth": auth
            }

            # Update the auth field
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' auth updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request auth: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' auth: {str(e)}")

    def update_request_tests(self, request_path: str, tests: str, **kwargs) -> str:
        """Update request test scripts."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Get existing events and preserve non-test events
            existing_events = request_item.get("event", [])
            events = [event for event in existing_events if event.get("listen") != "test"]
            
            # Add the new test script using the official API format
            events.append({
                "listen": "test",
                "script": {
                    "exec": tests.strip().split('\n'),
                    "type": "text/javascript"
                }
            })
            
            # Create update payload using the events array format from official spec
            request_update = {
                "events": events
            }

            # Update using the individual request endpoint with proper events format
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' tests updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request tests: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' tests: {str(e)}")

    def update_request_pre_script(self, request_path: str, pre_request_script: str, **kwargs) -> str:
        """Update request pre-request scripts."""
        try:
            # Get request item and ID
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Get existing events and preserve non-prerequest events
            existing_events = request_item.get("event", [])
            events = [event for event in existing_events if event.get("listen") != "prerequest"]
            
            # Add the new prerequest script using the official API format
            events.append({
                "listen": "prerequest",
                "script": {
                    "exec": pre_request_script.strip().split('\n'),
                    "type": "text/javascript"
                }
            })
            
            # Create update payload using the events array format from official spec
            request_update = {
                "events": events
            }

            # Update using the individual request endpoint with proper events format
            response = self._make_request('PUT', f'/collections/{self.collection_id}/requests/{request_id}',
                                          json=request_update)
            return json.dumps({"success": True, "message": f"Request '{request_path}' pre-script updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request pre-script: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' pre-script: {str(e)}")

    def delete_request(self, request_path: str, **kwargs) -> str:
        """Delete an API request permanently."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find and remove the request
            if self.analyzer.remove_request_by_path(collection_data["item"], request_path):
                # Update collection
                response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                              json={"collection": collection_data})
                return json.dumps({"message": f"Request '{request_path}' deleted successfully"}, indent=2)
            else:
                raise ToolException(f"Request '{request_path}' not found")
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting request: {stacktrace}")
            raise ToolException(
                f"Unable to delete request '{request_path}': {str(e)}")

    def duplicate_request(self, source_path: str, new_name: str,
                          target_path: str = None, **kwargs) -> str:
        """Create a copy of an existing API request."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find source request
            source_request = self.analyzer.find_request_by_path(
                collection_data["item"], source_path)
            if not source_request:
                raise ToolException(
                    f"Source request '{source_path}' not found")

            # Create copy
            request_copy = json.loads(json.dumps(source_request))  # Deep copy
            request_copy["name"] = new_name

            # Remove IDs if present
            if "id" in request_copy:
                del request_copy["id"]

            # Add to target location
            if target_path:
                folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], target_path)
                if not folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                folders[0]["item"].append(request_copy)
            else:
                # Add to same location as source
                source_folder_path = "/".join(source_path.split("/")[:-1])
                if source_folder_path:
                    folders = self.analyzer.find_folders_by_path(
                        collection_data["item"], source_folder_path)
                    folders[0]["item"].append(request_copy)
                else:
                    collection_data["item"].append(request_copy)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request duplicated as '{new_name}'"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when duplicating request: {stacktrace}")
            raise ToolException(
                f"Unable to duplicate request '{source_path}': {str(e)}")

    def move_request(self, source_path: str, target_path: str = None, **kwargs) -> str:
        """Move an API request to a different folder."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find source request
            source_request = self.analyzer.find_request_by_path(
                collection_data["item"], source_path)
            if not source_request:
                raise ToolException(
                    f"Source request '{source_path}' not found")

            request_data = json.loads(json.dumps(source_request))  # Deep copy

            # Remove from source location
            self.analyzer.remove_request_by_path(collection_data["item"], source_path)

            # Add to target location
            if target_path:
                folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], target_path)
                if not folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                folders[0]["item"].append(request_data)
            else:
                collection_data["item"].append(request_data)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request moved from '{source_path}' to '{target_path or 'root'}'"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when moving request: {stacktrace}")
            raise ToolException(
                f"Unable to move request '{source_path}': {str(e)}")
                
    # =================================================================
    # HELPER METHODS
    # =================================================================

    def get_request_by_path(self, request_path: str, **kwargs) -> str:
        """Get a specific request by path.
        
        Uses the _get_request_item_and_id helper to find the request and then fetches complete
        information using the Postman API endpoint for individual requests.
        """
        try:
            # Get request item and ID
            _, request_id, _ = self._get_request_item_and_id(request_path)
            
            # Fetch the complete request information from the API
            response = self._make_request(
                'GET', f'/collections/{self.collection_id}/requests/{request_id}'
            )
            
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when getting request by path: {stacktrace}")
            raise ToolException(
                f"Unable to get request '{request_path}': {str(e)}")

    def get_request_by_id(self, request_id: str, **kwargs) -> str:
        """Get a specific request by ID.
        
        Directly fetches the request using its unique ID from the Postman API.
        """
        try:
            # Fetch the complete request information from the API using the ID
            response = self._make_request(
                'GET', f'/collections/{self.collection_id}/requests/{request_id}'
            )
            
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when getting request by ID: {stacktrace}")
            raise ToolException(
                f"Unable to get request with ID '{request_id}': {str(e)}")

    def get_request_script(self, request_path: str, script_type: str = "prerequest", **kwargs) -> str:
        """
        Get the script (pre-request or test) for a request by path.
        
        Args:
            request_path: Path to the request within the collection
            script_type: The type of script to retrieve ("prerequest" or "test")
            
        Returns:
            The script content as JSON string, or an error message if the script doesn't exist
        """
        try:
            # Get the request item from the collection and also try individual endpoint
            request_item, request_id, _ = self._get_request_item_and_id(request_path)
            
            script_content = None
            
            # Method 1: Check events array (modern format)
            events = request_item.get("event", [])
            for event in events:
                if event.get("listen") == script_type:
                    script = event.get("script", {})
                    exec_content = script.get("exec", [])
                    if isinstance(exec_content, list):
                        script_content = "\n".join(exec_content)
                    else:
                        script_content = str(exec_content)
                    break
            
            # Method 2: If not found in events, try individual request endpoint for direct fields
            if script_content is None:
                try:
                    individual_request = self._make_request('GET', f'/collections/{self.collection_id}/requests/{request_id}')
                    if script_type == "test":
                        script_content = individual_request.get("tests", "")
                    elif script_type == "prerequest":
                        script_content = individual_request.get("preRequestScript", "")
                except:
                    # If individual endpoint fails, that's okay, we'll fall back to not found
                    pass
            
            if not script_content or script_content.strip() == "":
                return json.dumps({"success": False, "message": f"No {script_type} script found for request '{request_path}'"}, indent=2)
            
            return json.dumps({
                "success": True,
                "script_type": script_type, 
                "script_content": script_content.strip(), 
                "request_path": request_path
            }, indent=2)
                
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when getting request {script_type} script: {stacktrace}")
            raise ToolException(f"Unable to get {script_type} script for request '{request_path}': {str(e)}")

    def parse_collection_to_flat_structure(self, collection_response: Dict[str, Any], folder_path: str = None) -> Dict[str, Any]:
        """Parse collection response into a flattened structure with path-based keys.
        
        Args:
            collection_response: The Postman collection response JSON
            folder_path: Optional folder path to filter results. If provided, only items
                        within this folder will be included in the output, and collection
                        metadata will be excluded.
        """
        collection = collection_response.get('collection', {})
        info = collection.get('info', {})
        
        # If folder_path is specified, return minimal structure focused on the folder
        if folder_path is not None:
            result = {
                "folder_path": folder_path,
                "items": {}
            }
        else:
            # Full collection structure with metadata
            result = {
                "collection_postman_id": info.get('_postman_id'),
                "name": info.get('name'),
                "updatedAt": info.get('updatedAt'),
                "createdAt": info.get('createdAt'),
                "lastUpdatedBy": info.get('lastUpdatedBy'),
                "uid": info.get('uid'),
                "items": {}
            }
        
        def parse_items(items, parent_path=""):
            """Recursively parse items into flat structure."""
            for item in items:
                item_name = item.get('name', '')
                current_path = f"{parent_path}/{item_name}" if parent_path else item_name
                
                # If folder_path is specified, check if we should include this item
                if folder_path is not None:
                    # Check if current path is within the specified folder
                    if not (current_path == folder_path or current_path.startswith(folder_path + "/")):
                        # If this is a folder, we need to check if it contains the target folder
                        if 'item' in item and folder_path.startswith(current_path + "/"):
                            # This folder is an ancestor of the target folder, continue traversing
                            parse_items(item['item'], current_path)
                        continue
                
                # Check if this is a folder (has 'item' property) or a request
                if 'item' in item:
                    # This is a folder
                   
                    result['items'][current_path] = {
                        "type": "folder",
                        "id": item.get('id'),
                        "uid": item.get('uid')
                    }
                    # Recursively parse nested items
                    parse_items(item['item'], current_path)
                else:
                    # This is a request
                    request_info = item.get('request', {})
                    
                    # Parse URL
                    url_info = request_info.get('url', {})
                    if isinstance(url_info, str):
                        url = url_info
                    else:
                        # URL is an object with raw property
                        url = url_info.get('raw', '')
                    
                    # Parse headers
                    headers = request_info.get('header', [])
                    
                    # Parse body
                    body_info = None
                    body = request_info.get('body', {})
                    if body:
                        body_mode = body.get('mode', '')
                        if body_mode == 'raw':
                            try:
                                raw_data = body.get('raw', '')
                                if raw_data:
                                    body_info = {
                                        "type": "json",
                                        "data": json.loads(raw_data) if raw_data.strip() else {}
                                    }
                            except json.JSONDecodeError:
                                body_info = {
                                    "type": "raw",
                                    "data": body.get('raw', '')
                                }
                        elif body_mode == 'formdata':
                            body_info = {
                                "type": "formdata",
                                "data": body.get('formdata', [])
                            }
                        elif body_mode == 'urlencoded':
                            body_info = {
                                "type": "urlencoded",
                                "data": body.get('urlencoded', [])
                            }
                    
                    # Parse URL parameters
                    params = []
                    if isinstance(url_info, dict):
                        query = url_info.get('query', [])
                        for param in query:
                            if isinstance(param, dict):
                                params.append({
                                    "key": param.get('key', ''),
                                    "value": param.get('value', ''),
                                    "disabled": param.get('disabled', False)
                                })
                    
                    request_data = {
                        "id": item.get('id'),
                        "uid": item.get('uid'),
                        "full_postman_path": current_path,
                        "type": "request",
                        "method": request_info.get('method', 'GET'),
                        "request_url": url,
                        "headers": headers,
                        "params": params
                    }
                    
                    # Add body if present
                    if body_info:
                        request_data["body"] = body_info
                    
                    # Add description if present
                    description = request_info.get('description')
                    if description:
                        request_data["description"] = description
                    
                    result['items'][current_path] = request_data
        
        # Parse the top-level items
        items = collection.get('item', [])
        parse_items(items)
        
        return result
