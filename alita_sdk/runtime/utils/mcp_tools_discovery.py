"""
MCP Tools Discovery Utility.
Provides a standalone function to discover tools from remote MCP servers.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..models.mcp_models import McpConnectionConfig
from .mcp_oauth import McpAuthorizationRequired

logger = logging.getLogger(__name__)


def discover_mcp_tools(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Discover available tools from a remote MCP server.
    
    This function connects to a remote MCP server via SSE (Server-Sent Events)
    and retrieves the list of available tools using the MCP protocol.
    
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
    # Build connection config
    connection_config = McpConnectionConfig(
        url=url,
        headers=headers or {},
        session_id=session_id
    )
    
    logger.info(f"[MCP Discovery] Starting tool discovery from {url}")
    
    try:
        # Run the async discovery in a new event loop
        tools_list = asyncio.run(
            _discover_tools_async(connection_config, timeout)
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
    connection_config: McpConnectionConfig,
    timeout: int
) -> List[Dict[str, Any]]:
    """
    Async implementation of tool discovery using SSE client.
    
    Args:
        connection_config: MCP connection configuration
        timeout: Request timeout in seconds
        
    Returns:
        List of tool definitions
    """
    import uuid
    from .mcp_sse_client import McpSseClient
    
    all_tools = []
    session_id = connection_config.session_id
    
    # Generate temporary session_id if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.debug(f"[MCP Discovery] Generated session_id: {session_id}")
    
    logger.debug(f"[MCP Discovery] Connecting to {connection_config.url}")
    
    # Prepare headers
    headers = {}
    if connection_config.headers:
        headers.update(connection_config.headers)
    
    # Create SSE client
    client = McpSseClient(
        url=connection_config.url,
        session_id=session_id,
        headers=headers,
        timeout=timeout
    )
    
    try:
        async with client:
            # Initialize MCP protocol session
            logger.debug("[MCP Discovery] Initializing MCP session...")
            await client.initialize()
            
            # Request tool list
            logger.debug("[MCP Discovery] Requesting tools/list...")
            response = await client.send_request("tools/list", {})
            
            tools = response.get('result', {}).get('tools', [])
            logger.debug(f"[MCP Discovery] Received {len(tools)} tools")
            
            # Convert tools to standard format
            for tool in tools:
                tool_def = {
                    'name': tool.get('name'),
                    'description': tool.get('description', ''),
                    'inputSchema': tool.get('inputSchema', {}),
                }
                all_tools.append(tool_def)
    except McpAuthorizationRequired:
        raise
    
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
    connection_config = McpConnectionConfig(
        url=url,
        headers=headers or {},
        session_id=session_id
    )
    
    return await _discover_tools_async(connection_config, timeout)
