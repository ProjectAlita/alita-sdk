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
    
    # For OAuth 2.1 / OpenID Connect, try standard well-known endpoints
    # These are the most common discovery endpoints
    if realm and realm.lower() == "oauth":
        # Standard OAuth 2.0 / 2.1 discovery endpoints
        authorization_servers.append(f"{base_url}/.well-known/oauth-authorization-server")
        authorization_servers.append(f"{base_url}/.well-known/openid-configuration")
    else:
        # If no realm or different realm, still try standard endpoints
        authorization_servers.append(f"{base_url}/.well-known/oauth-authorization-server")
        authorization_servers.append(f"{base_url}/.well-known/openid-configuration")
    
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
