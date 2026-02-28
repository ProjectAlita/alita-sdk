import json
import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from langchain_core.tools import ToolException

logger = logging.getLogger(__name__)


class McpAuthorizationRequired(ToolException):
    """Raised when an MCP server requires OAuth authorization before use."""

    def __init__(
        self,
        message: str,
        server_url: str,
        resource_metadata_url: Optional[str] = None,
        www_authenticate: Optional[str] = None,
        resource_metadata: Optional[Dict[str, Any]] = None,
        status: Optional[int] = None,
        tool_name: Optional[str] = None,
    ):
        super().__init__(message)
        self.server_url = server_url
        self.resource_metadata_url = resource_metadata_url
        self.www_authenticate = www_authenticate
        self.resource_metadata = resource_metadata
        self.status = status
        self.tool_name = tool_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": str(self),
            "server_url": self.server_url,
            "resource_metadata_url": self.resource_metadata_url,
            "www_authenticate": self.www_authenticate,
            "resource_metadata": self.resource_metadata,
            "status": self.status,
            "tool_name": self.tool_name,
        }


def extract_authorization_uri(www_authenticate: Optional[str]) -> Optional[str]:
    """
    Extract authorization_uri from WWW-Authenticate header.
    This points directly to the OAuth authorization server metadata URL.
    Should be used before falling back to resource_metadata.
    """
    if not www_authenticate:
        return None
    
    # Look for authorization_uri="<url>" in the header
    match = re.search(r'authorization_uri\s*=\s*\"?([^\", ]+)\"?', www_authenticate)
    if match:
        return match.group(1)
    
    return None


def extract_resource_metadata_url(www_authenticate: Optional[str], server_url: Optional[str] = None) -> Optional[str]:
    """
    Pull the resource_metadata URL from a WWW-Authenticate header if present.
    If not found and server_url is provided, try to construct resource metadata URLs.
    """
    if not www_authenticate and not server_url:
        return None

    # RFC9728 returns `resource_metadata="<url>"` inside the header value
    if www_authenticate:
        match = re.search(r'resource_metadata\s*=\s*\"?([^\", ]+)\"?', www_authenticate)
        if match:
            return match.group(1)
    
    # For servers that don't provide resource_metadata in WWW-Authenticate,
    # we'll return None and rely on inferring authorization servers from the realm
    # or using well-known OAuth discovery endpoints directly
    return None

def fetch_oauth_authorization_server_metadata(url: str, timeout: int = 10, extra_endpoints: Optional[list] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch OAuth authorization server metadata from well-known endpoints.
    
    Args:
        url: Either a full well-known URL (e.g., https://api.figma.com/.well-known/oauth-authorization-server)
             or a base URL (e.g., https://api.figma.com) where we'll try discovery endpoints.
        timeout: Request timeout in seconds.
        extra_endpoints: Additional well-known URLs to try before the standard ones.
            Useful for providers that use non-standard discovery paths, e.g. Azure AD v2.0:
            ``["{base}/v2.0/.well-known/openid-configuration"]``.
            Only used when *url* does not already contain ``/.well-known/``.

    Returns:
        OAuth authorization server metadata dict, or None if not found.
    """
    # If the URL is already a .well-known endpoint, try it directly first
    if '/.well-known/' in url:
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            logger.debug(f"Failed to fetch OAuth metadata from {url}: {exc}")
        # If direct fetch failed, don't try other endpoints
        return None
    
    # Otherwise, try extra endpoints first, then standard discovery endpoints
    discovery_endpoints = list(extra_endpoints or []) + [
        f"{url}/.well-known/oauth-authorization-server",
        f"{url}/.well-known/openid-configuration",
    ]
    
    for endpoint in discovery_endpoints:
        try:
            resp = requests.get(endpoint, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            logger.debug(f"Failed to fetch OAuth metadata from {endpoint}: {exc}")
            continue
    
    return None


def infer_authorization_servers_from_realm(www_authenticate: Optional[str], server_url: str) -> Optional[list]:
    """
    Infer authorization server URLs from WWW-Authenticate realm or server URL.
    This is used when the server doesn't provide resource_metadata endpoint.
    """
    if not www_authenticate and not server_url:
        return None
    
    authorization_servers = []
    
    # Try to extract realm from WWW-Authenticate header
    realm = None
    if www_authenticate:
        realm_match = re.search(r'realm\s*=\s*\"([^\"]+)\"', www_authenticate)
        if realm_match:
            realm = realm_match.group(1)
    
    # Parse the server URL to get base domain
    parsed = urlparse(server_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Return the base authorization server URL (not the discovery endpoint)
    # The client will append .well-known paths when fetching metadata
    authorization_servers.append(base_url)
    
    return authorization_servers if authorization_servers else None


def fetch_resource_metadata(resource_metadata_url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """Fetch and parse the protected resource metadata document."""
    try:
        resp = requests.get(resource_metadata_url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # broad catch – we want to surface auth requirement even if this fails
        logger.warning("Failed to fetch resource metadata from %s: %s", resource_metadata_url, exc)
        return None


async def fetch_resource_metadata_async(resource_metadata_url: str, session=None, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """Async variant for fetching protected resource metadata."""
    try:
        import aiohttp

        client_timeout = aiohttp.ClientTimeout(total=timeout)
        if session:
            async with session.get(resource_metadata_url, timeout=client_timeout) as resp:
                text = await resp.text()
        else:
            async with aiohttp.ClientSession(timeout=client_timeout) as local_session:
                async with local_session.get(resource_metadata_url) as resp:
                    text = await resp.text()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Resource metadata at %s is not valid JSON: %s", resource_metadata_url, text[:200])
            return None
    except Exception as exc:
        logger.warning("Failed to fetch resource metadata from %s: %s", resource_metadata_url, exc)
        return None


def canonical_resource(server_url: str) -> str:
    """Produce a canonical resource identifier for the MCP server."""
    parsed = urlparse(server_url)
    # Normalize scheme/host casing per RFC guidance
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
    )
    resource = normalized.geturl()

    # Prefer form without trailing slash unless path is meaningful
    if resource.endswith("/") and parsed.path in ("", "/"):
        resource = resource[:-1]
    return resource


def substitute_mcp_placeholders(value: Any, user_config: Dict[str, Any], client=None) -> Any:
    """
    Substitute placeholders with values from user_config or secrets store.

    Supports two placeholder patterns:
    - {param}: Replaced with value from user_config
    - {{secret.name}}: Replaced with value from secrets store via client.unsecret()

    Examples:
        # Simple parameter from user_config
        "https://api.example.com/{environment}" -> "https://api.example.com/production"

        # Secret from secrets store
        "Bearer {{secret.github_pat}}" -> "Bearer ghp_abc123..."
        "Bearer {{secret.api-token-v2}}" -> "Bearer sk-xyz789..."

    Supported secret name patterns:
        - Alphanumeric: {{secret.token}}
        - Underscore: {{secret.github_pat}}
        - Dash: {{secret.api-token}}
        - Dot: {{secret.api.key}}
        - Mixed: {{secret.my-api_key.v2}}

    Args:
        value: Value to process (string, dict, list, or other)
        user_config: Dictionary containing user-provided configuration values
        client: Optional AlitaClient instance for fetching secrets

    Returns:
        Value with placeholders replaced. If client is None or secret not found,
        original placeholder is preserved.
    """
    if isinstance(value, str):
        original_value = value

        # Handle {{secret.name}} pattern first (more specific)
        def secret_replacer(match):
            placeholder = match.group(0)  # Full match: {{secret.name}}
            secret_name = match.group(1)  # Captured group: name

            logger.debug(f"[MCP] Processing secret placeholder: {placeholder}, secret_name: {secret_name}")

            # First, check if secret was pre-resolved in user_config (e.g., by pylon_main.unsecret())
            # This allows check_connection to work even without a client
            if secret_name in user_config:
                secret_value = user_config[secret_name]
                if secret_value is not None and secret_value != '':
                    logger.debug(f"[MCP] Found pre-resolved secret '{secret_name}' in user_config")
                    return str(secret_value)

            # If not pre-resolved, try using client.unsecret()
            if not client:
                logger.warning(f"[MCP] No client available to fetch secret '{secret_name}', and not found in user_config. Keeping placeholder: {placeholder}")
                return placeholder

            if not hasattr(client, 'unsecret'):
                logger.error(f"[MCP] Client does not have 'unsecret' method, keeping placeholder: {placeholder}")
                return placeholder

            try:
                secret_value = client.unsecret(secret_name)
                if secret_value is not None:
                    logger.debug(f"[MCP] Successfully replaced {{{{secret.{secret_name}}}}} with secret value from client")
                    return str(secret_value)
                else:
                    logger.warning(f"[MCP] Secret '{secret_name}' not found in secrets store, keeping placeholder: {placeholder}")
                    return placeholder
            except Exception as e:
                logger.error(f"[MCP] Failed to fetch secret '{secret_name}': {e}", exc_info=True)
                return placeholder

        # Handle {param} pattern (simpler placeholder)
        def param_replacer(match):
            placeholder = match.group(0)  # Full match: {param}
            key = match.group(1)  # Captured group: param

            # Check if this looks like it should be a secret pattern (has 'secret.' in it)
            # This catches malformed patterns like {secret.name} instead of {{secret.name}}
            if 'secret.' in key:
                secret_key = key.split('.')[-1] if '.' in key else key
                # Use double braces in message to show literal braces
                logger.warning(f"[MCP] Found malformed secret placeholder '{placeholder}' - should use double braces: {{{{secret.{secret_key}}}}}")

            value = user_config.get(key)
            if value is not None:
                logger.debug(f"[MCP] Replaced {{{key}}} with value from user_config")
                return str(value)
            else:
                logger.debug(f"[MCP] Key '{key}' not found in user_config, keeping placeholder: {placeholder}")
                return placeholder

        # Apply secret pattern substitution first
        # Pattern: {{secret.([\w.\-]+)}} - captures alphanumeric, underscore, dot, dash
        # Supports secret names like: github_pat, my-secret, api.key, github-token-v2
        result = re.sub(r'\{\{secret\.([\w.\-]+)\}\}', secret_replacer, value)

        # Then apply simple parameter substitution
        # Pattern: {(\w+)} - but NOT if preceded by another {
        # Use negative lookbehind to avoid matching {{...}}
        result = re.sub(r'(?<!\{)\{(\w+)\}(?!\})', param_replacer, result)

        if result != original_value:
            logger.debug(f"[MCP] Placeholder substitution: '{original_value}' -> '{result}'")

        return result
    elif isinstance(value, dict):
        return {k: substitute_mcp_placeholders(v, user_config, client) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_mcp_placeholders(v, user_config, client) for v in value]
    return value


def exchange_oauth_token(
    token_endpoint: str,
    code: str,
    redirect_uri: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    code_verifier: Optional[str] = None,
    scope: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Exchange an OAuth authorization code for access tokens.
    
    This function performs the OAuth token exchange on the server side,
    avoiding CORS issues that would occur if done from a browser.
    
    Args:
        token_endpoint: OAuth token endpoint URL
        code: Authorization code from OAuth provider
        redirect_uri: Redirect URI used in authorization request
        client_id: OAuth client ID (optional for DCR/public clients)
        client_secret: OAuth client secret (optional for public clients)
        code_verifier: PKCE code verifier (optional)
        scope: OAuth scope (optional)
        timeout: Request timeout in seconds
        
    Returns:
        Token response from OAuth provider containing access_token, etc.
        
    Raises:
        requests.RequestException: If the HTTP request fails
        ValueError: If the token exchange fails
    
    Note:
        client_id may be optional for:
        - Dynamic Client Registration (DCR): client_id may be in the code
        - OIDC public clients: some providers don't require it
        - Some MCP servers handle auth differently
    """
    # Build the token request body
    token_body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    
    if client_id:
        token_body["client_id"] = client_id
    if client_secret:
        token_body["client_secret"] = client_secret
    if code_verifier:
        token_body["code_verifier"] = code_verifier
    if scope:
        token_body["scope"] = scope

    logger.info(f"MCP OAuth: exchanging code at {token_endpoint}")
    
    # Make the token exchange request
    response = requests.post(
        token_endpoint,
        data=token_body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=timeout
    )
    
    # Try to parse as JSON
    try:
        token_data = response.json()
    except Exception:
        # Some providers return URL-encoded response
        from urllib.parse import parse_qs
        token_data = {k: v[0] if len(v) == 1 else v 
                     for k, v in parse_qs(response.text).items()}
    
    if response.ok:
        logger.info("MCP OAuth: token exchange successful")
        return token_data
    else:
        error_msg = token_data.get("error_description") or token_data.get("error") or response.text
        logger.error(f"MCP OAuth: token exchange failed - {response.status_code}: {error_msg}")
        raise ValueError(f"Token exchange failed: {error_msg}")


def extract_user_friendly_mcp_error(exception: Exception, headers: Optional[Dict[str, Any]] = None) -> str:
    """
    Extract a user-friendly error message from MCP-related exceptions.

    MCP (Model Context Protocol) uses JSON-RPC 2.0 for communication.
    This function handles:
    - JSON-RPC 2.0 error codes (-32700 to -32603)
    - MCP protocol-specific errors
    - HTTP status codes (401, 403, 404, 429, 500, etc.)
    - Network/connection errors
    - OAuth/authentication errors

    Args:
        exception: The exception that was raised
        headers: Optional headers dict to check for authentication

    Returns:
        A user-friendly error message string

    Reference:
        - MCP Specification: https://modelcontextprotocol.io/specification/2024-11-05
        - JSON-RPC 2.0: https://www.jsonrpc.org/specification
    """
    # Check if it's an MCP authorization exception
    if isinstance(exception, McpAuthorizationRequired):
        return "MCP server requires authorization. Please authenticate to continue."

    # Convert to string and lowercase once for consistent checking
    error_msg = str(exception)
    error_lower = error_msg.lower()

    # Check if auth was provided (used by multiple conditions)
    has_auth = bool(headers and any(k.lower() == 'authorization' for k in headers))

    # Try to parse as JSON-RPC error response if it looks like JSON
    if error_msg.strip().startswith('{') or '"error"' in error_msg:
        try:
            error_data = json.loads(error_msg) if error_msg.strip().startswith('{') else {}
            if not error_data and '"error"' in error_msg:
                # Try to extract JSON from error message
                import re
                json_match = re.search(r'\{.*"error".*\}', error_msg, re.DOTALL)
                if json_match:
                    error_data = json.loads(json_match.group(0))

            if 'error' in error_data:
                error_obj = error_data['error']
                error_code = error_obj.get('code')
                error_message = error_obj.get('message', '')
                error_data_field = error_obj.get('data', '')

                # Helper to format error with optional data field
                def format_error_with_data(base_msg: str) -> str:
                    if error_data_field and isinstance(error_data_field, str):
                        return f"{base_msg} Details: {error_data_field}"
                    return base_msg

                # Handle JSON-RPC 2.0 standard error codes
                if error_code == -32700:
                    return format_error_with_data("Parse error: The MCP server could not parse the request. This may be a bug in the client.")
                elif error_code == -32600:
                    return format_error_with_data("Invalid request: The request sent to the MCP server was malformed.")
                elif error_code == -32601:
                    return format_error_with_data(f"Method not found: The MCP server doesn't support the requested operation. {error_message}")
                elif error_code == -32602:
                    return format_error_with_data(f"Invalid parameters: The request parameters are incorrect. {error_message}")
                elif error_code == -32603:
                    return format_error_with_data(f"Internal error: The MCP server encountered an internal error. {error_message}")
                elif error_code and -32099 <= error_code <= -32000:
                    # Server error (implementation-defined)
                    return format_error_with_data(f"MCP server error ({error_code}): {error_message or 'The server encountered an error processing the request.'}")
                elif error_code:
                    # Other error codes
                    return format_error_with_data(f"MCP error ({error_code}): {error_message or 'Unknown error occurred.'}")
                elif error_message:
                    # No error code but has message
                    return format_error_with_data(f"MCP error: {error_message}")
        except (json.JSONDecodeError, KeyError, TypeError):
            # Not a valid JSON-RPC error, continue with other checks
            pass

    # Priority 1: Specific timeout errors (more specific than general connection)
    if any(keyword in error_lower for keyword in ["timeout", "timed out", "time out"]):
        if "read" in error_lower:
            return "Server read timeout. The MCP server is taking too long to respond."
        if "connect" in error_lower:
            return "Connection timeout. Unable to reach the MCP server within the timeout period."
        return "Connection to MCP server timed out. The server may be slow or unavailable."

    # Priority 2: Connection-specific errors (before generic connection)
    if "connection refused" in error_lower or "errno 61" in error_lower:
        return "Connection refused by MCP server. Please verify the server is running and the port is correct."

    if "connection reset" in error_lower or "errno 54" in error_lower:
        return "Connection reset by MCP server. The server may have crashed or rejected the request."

    if any(keyword in error_lower for keyword in ["name or service not known", "nodename nor servname", "errno -2", "errno -3"]):
        return "DNS resolution failed. Please check the server hostname in the URL."

    if "no route to host" in error_lower or "errno 113" in error_lower:
        return "No route to host. The MCP server address is unreachable from your network."

    if any(keyword in error_lower for keyword in ["connection", "connect", "network"]):
        return "Unable to connect to MCP server. Please check the server URL and network connectivity."

    # Priority 3: Rate limiting
    if "429" in error_msg or "rate limit" in error_lower or "too many requests" in error_lower:
        return "Rate limit exceeded. Please wait a moment and try again."

    # Priority 4: Authentication errors (with context-aware messages)
    if any(keyword in error_lower for keyword in ["unauthorized", "401"]):
        if has_auth:
            return "Authentication failed. Your credentials or API token may be invalid or expired."
        else:
            return "Authentication required. Please provide valid credentials in the MCP server configuration."

    if any(keyword in error_lower for keyword in ["forbidden", "403"]):
        if has_auth:
            return "Access forbidden. Your credentials don't have permission to access this MCP server or resource."
        else:
            return "Access forbidden. Authentication may be required to access this MCP server."

    # Priority 5: SSL/certificate errors (with specific guidance)
    if "certificate verify failed" in error_lower or "ssl: certificate_verify_failed" in error_lower:
        return "SSL certificate verification failed. Try disabling SSL verification in the server settings or update your certificates."

    if any(keyword in error_lower for keyword in ["ssl", "certificate", "cert", "handshake"]):
        return "SSL/TLS error. There may be a problem with the server's security certificate."

    # Priority 6: URL/endpoint errors
    if "invalid url" in error_lower or "invalid hostname" in error_lower:
        return "Invalid MCP server URL. Please check the URL format (should start with http:// or https://)."

    if "malformed" in error_lower:
        return "Malformed request or URL. Please check the MCP server configuration."

    # Priority 7: HTTP status errors
    if "404" in error_msg:
        return "MCP server endpoint not found (404). Please verify the server URL is correct."

    if "405" in error_msg or "method not allowed" in error_lower:
        return "Method not allowed (405). The MCP server may not support the requested operation."

    if "400" in error_msg or "bad request" in error_lower:
        return "Bad request (400). The request to the MCP server was malformed."

    if "500" in error_msg or "internal server error" in error_lower:
        return "Internal server error (500). The MCP server encountered an error processing the request."

    if "502" in error_msg or "bad gateway" in error_lower:
        return "Bad gateway (502). The MCP server or proxy is unavailable or misconfigured."

    if "503" in error_msg or "service unavailable" in error_lower:
        return "Service unavailable (503). The MCP server is temporarily down for maintenance."

    if "504" in error_msg or "gateway timeout" in error_lower:
        return "Gateway timeout (504). The MCP server took too long to respond."

    # Priority 8: JSON/parsing errors
    if "json" in error_lower and any(keyword in error_lower for keyword in ["decode", "parse", "invalid"]):
        return "Failed to parse MCP server response. The server may not be a valid MCP endpoint or returned invalid data."

    # Priority 9: MCP-specific protocol errors
    if "mcp" in error_lower or "model context protocol" in error_lower:
        if "protocol" in error_lower or "specification" in error_lower:
            return "MCP protocol error. The server may not be implementing the MCP specification correctly."
        if "version" in error_lower or "protocol version" in error_lower:
            return "MCP version mismatch. The server may be using an incompatible MCP protocol version (expected 2024-11-05)."
        if "transport" in error_lower:
            return "MCP transport error. There may be an issue with the connection transport type (SSE, HTTP, etc.)."

    # Priority 10: Token/OAuth errors
    if any(keyword in error_lower for keyword in ["token", "bearer", "oauth", "access_token"]):
        if "expired" in error_lower:
            return "OAuth token expired. Please re-authenticate to get a new access token."
        if "invalid" in error_lower:
            return "OAuth token invalid. Please check your authentication configuration."
        return "OAuth/token error. Your access token may be invalid, expired, or incorrectly formatted."

    # Priority 11: Import/dependency errors
    if ("import" in error_lower or "module" in error_lower) and ("error" in error_lower or "not found" in error_lower):
        if "langchain" in error_lower or "mcp" in error_lower:
            return "Missing MCP dependency. Please install required packages: pip install langchain-mcp-adapters mcp"
        return "Missing dependency. Please ensure all required packages are installed for MCP functionality."

    # Priority 12: Tool/method-specific errors
    if "tool" in error_lower and "not found" in error_lower:
        return "Tool not found. The requested MCP tool doesn't exist on the server or has been removed."

    # Fallback: Try to extract most specific error from nested messages
    if ": " in error_msg:
        # Split by ": " and take the last meaningful part (skip empty/short parts)
        parts = [p.strip() for p in error_msg.split(": ") if p.strip()]
        if parts:
            # Take the last substantial part (more than 10 chars, or the only part)
            for part in reversed(parts):
                if len(part) > 10 or len(parts) == 1:
                    # Clean up common prefixes
                    part = part.replace("Error: ", "").replace("Exception: ", "")
                    return part[:200] if len(part) > 200 else part

    # Final fallback: Return truncated original error
    return error_msg[:200] if len(error_msg) > 200 else error_msg


def refresh_oauth_token(
    token_endpoint: str,
    refresh_token: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    scope: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Refresh an OAuth access token using a refresh token.
    
    Args:
        token_endpoint: OAuth token endpoint URL
        refresh_token: Refresh token from previous authorization
        client_id: OAuth client ID (optional for DCR/public clients)
        client_secret: OAuth client secret (optional for public clients)
        scope: OAuth scope (optional)
        timeout: Request timeout in seconds
        
    Returns:
        Token response from OAuth provider containing access_token, etc.
        May also include a new refresh_token depending on the provider.
        
    Raises:
        requests.RequestException: If the HTTP request fails
        ValueError: If the token refresh fails
    
    Note:
        client_id may be optional for:
        - Dynamic Client Registration (DCR): client_id embedded in refresh_token
        - OIDC public clients: some providers don't require it
        - Some MCP servers handle auth differently
    """
    token_body = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    
    if client_id:
        token_body["client_id"] = client_id
    if client_secret:
        token_body["client_secret"] = client_secret
    if scope:
        token_body["scope"] = scope

    logger.info(f"MCP OAuth: refreshing token at {token_endpoint}")
    
    response = requests.post(
        token_endpoint,
        data=token_body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=timeout
    )
    
    # Try to parse as JSON
    try:
        token_data = response.json()
    except Exception:
        # Some providers return URL-encoded response
        from urllib.parse import parse_qs
        token_data = {k: v[0] if len(v) == 1 else v 
                     for k, v in parse_qs(response.text).items()}
    
    if response.ok:
        logger.info("MCP OAuth: token refresh successful")
        return token_data
    else:
        error_msg = token_data.get("error_description") or token_data.get("error") or response.text
        logger.error(f"MCP OAuth: token refresh failed - {response.status_code}: {error_msg}")
        raise ValueError(f"Token refresh failed: {error_msg}")
