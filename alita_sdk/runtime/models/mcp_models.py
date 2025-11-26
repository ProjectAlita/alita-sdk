"""
Models for MCP (Model Context Protocol) configuration.
Following MCP specification for remote HTTP servers only.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from urllib.parse import urlparse


class McpConnectionConfig(BaseModel):
    """
    MCP connection configuration for remote HTTP servers.
    Based on https://modelcontextprotocol.io/specification/2025-06-18
    """

    url: str = Field(description="MCP server HTTP URL (http:// or https://)")
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="HTTP headers for the connection (JSON object)"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="MCP session ID for stateful SSE servers (managed by client)"
    )

    @validator('url')
    def validate_url(cls, v):
        """Validate URL is HTTP/HTTPS."""
        if not v:
            raise ValueError("URL cannot be empty")

        parsed = urlparse(v)
        if parsed.scheme not in ['http', 'https']:
            raise ValueError("URL must use http:// or https:// scheme for remote MCP servers")

        if not parsed.netloc:
            raise ValueError("URL must include host and port")

        return v


class McpToolkitConfig(BaseModel):
    """Configuration for a single remote MCP server toolkit."""

    server_name: str = Field(description="MCP server name/identifier")
    connection: McpConnectionConfig = Field(description="MCP connection configuration")
    timeout: int = Field(default=60, description="Request timeout in seconds", ge=1, le=3600)
    selected_tools: List[str] = Field(default_factory=list, description="Specific tools to enable (empty = all)")
    enable_caching: bool = Field(default=True, description="Enable tool schema caching")
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds", ge=60, le=3600)


class McpToolMetadata(BaseModel):
    """Metadata about an MCP tool."""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    server: str = Field(description="Source server name")
    input_schema: Dict[str, Any] = Field(description="Tool input schema")
    enabled: bool = Field(default=True, description="Whether tool is enabled")