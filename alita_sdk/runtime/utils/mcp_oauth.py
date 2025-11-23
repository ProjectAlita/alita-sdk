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
    ):
        super().__init__(message)
        self.server_url = server_url
        self.resource_metadata_url = resource_metadata_url
        self.www_authenticate = www_authenticate
        self.resource_metadata = resource_metadata
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": str(self),
            "server_url": self.server_url,
            "resource_metadata_url": self.resource_metadata_url,
            "www_authenticate": self.www_authenticate,
            "resource_metadata": self.resource_metadata,
            "status": self.status,
        }


def extract_resource_metadata_url(www_authenticate: Optional[str]) -> Optional[str]:
    """Pull the resource_metadata URL from a WWW-Authenticate header if present."""
    if not www_authenticate:
        return None

    # RFC9728 returns `resource_metadata="<url>"` inside the header value
    match = re.search(r'resource_metadata\s*=\s*\"?([^\", ]+)\"?', www_authenticate)
    if match:
        return match.group(1)
    return None


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
