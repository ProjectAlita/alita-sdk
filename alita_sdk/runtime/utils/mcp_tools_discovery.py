"""
MCP Tools Discovery Utility.
Provides a standalone function to discover tools from remote MCP servers.
Supports both SSE (Server-Sent Events) and Streamable HTTP transports with auto-detection.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .mcp_oauth import McpAuthorizationRequired
from .mcp_client import McpClient

logger = logging.getLogger(__name__)


def discover_mcp_tools(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Discover available tools from a remote MCP server.
    
    This function connects to a remote MCP server and retrieves the list of 
    available tools using the MCP protocol. Automatically detects and uses
    the appropriate transport (SSE or Streamable HTTP).
    
    Args:
        url: MCP server HTTP URL (http:// or https://)
        headers: Optional HTTP headers for authentication
        timeout: Request timeout in seconds (default: 60)
        session_id: Optional session ID for stateful connections
        
    Returns:
        List of tool definitions, each containing:
        - name: Tool name
        - description: Tool description
        - inputSchema: JSON schema for tool input parameters
        
    Raises:
        McpAuthorizationRequired: If the server requires OAuth authorization (401)
        Exception: For other connection or protocol errors
        
    Example:
        >>> tools = discover_mcp_tools(
        ...     url="https://mcp.example.com/sse",
        ...     headers={"Authorization": "Bearer token123"}
        ... )
        >>> print(f"Found {len(tools)} tools")
    """
    logger.info(f"[MCP Discovery] Starting tool discovery from {url}")
    
    try:
        # Run the async discovery in a new event loop
        tools_list = asyncio.run(
            _discover_tools_async(url, headers, timeout, session_id)
        )
        logger.info(f"[MCP Discovery] Successfully discovered {len(tools_list)} tools from {url}")
        return tools_list
        
    except McpAuthorizationRequired:
        # Re-raise auth exceptions directly
        logger.info(f"[MCP Discovery] Authorization required for {url}")
        raise
        
    except Exception as e:
        logger.error(f"[MCP Discovery] Failed to discover tools from {url}: {e}")
        raise


async def _discover_tools_async(
    url: str,
    headers: Optional[Dict[str, str]],
    timeout: int,
    session_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Async implementation of tool discovery using unified MCP client.
    """
    all_tools = []
    
    # Create unified MCP client (auto-detects transport)
    client = McpClient(
        url=url,
        session_id=session_id,
        headers=headers,
        timeout=timeout
    )
    
    async with client:
        # Initialize MCP session
        await client.initialize()
        logger.debug(f"[MCP Discovery] Session initialized (transport={client.detected_transport})")
        
        # Get tools list
        tools = await client.list_tools()
        logger.debug(f"[MCP Discovery] Received {len(tools)} tools")
        
        # Convert tools to standard format
        for tool in tools:
            tool_def = {
                'name': tool.get('name'),
                'description': tool.get('description', ''),
                'inputSchema': tool.get('inputSchema', {}),
            }
            all_tools.append(tool_def)
    
    return all_tools


async def discover_mcp_tools_async(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Async version of discover_mcp_tools.
    
    See discover_mcp_tools for full documentation.
    """
    return await _discover_tools_async(url, headers, timeout, session_id)
