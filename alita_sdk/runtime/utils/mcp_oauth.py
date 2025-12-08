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


def fetch_oauth_authorization_server_metadata(base_url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """
    Fetch OAuth authorization server metadata from well-known endpoints.
    Tries both oauth-authorization-server and openid-configuration discovery endpoints.
    """
    discovery_endpoints = [
        f"{base_url}/.well-known/oauth-authorization-server",
        f"{base_url}/.well-known/openid-configuration",
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


def exchange_oauth_token(
    token_endpoint: str,
    code: str,
    redirect_uri: str,
    client_id: str,
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
        client_id: OAuth client ID
        client_secret: OAuth client secret (optional for public clients)
        code_verifier: PKCE code verifier (optional)
        scope: OAuth scope (optional)
        timeout: Request timeout in seconds
        
    Returns:
        Token response from OAuth provider containing access_token, etc.
        
    Raises:
        requests.RequestException: If the HTTP request fails
        ValueError: If the token exchange fails
    """
    # Build the token request body
    token_body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
    }
    
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

