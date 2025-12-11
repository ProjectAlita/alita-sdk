"""
MCP Remote Tool for direct HTTP/SSE invocation.
This tool is used for remote MCP servers accessed via HTTP/SSE.
"""

import asyncio
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from .mcp_server_tool import McpServerTool
from pydantic import Field
from ..utils.mcp_oauth import (
    McpAuthorizationRequired,
    canonical_resource,
    extract_resource_metadata_url,
    fetch_resource_metadata_async,
    infer_authorization_servers_from_realm,
)
from ..utils.mcp_client import McpClient

logger = logging.getLogger(__name__)

# Global registry to store MCP tool session metadata by tool name
# This is used to pass session info to callbacks since LangChain's serialization doesn't include all fields
MCP_TOOL_SESSION_REGISTRY: Dict[str, Dict[str, Any]] = {}


class McpRemoteTool(McpServerTool):
    """
    Tool for invoking remote MCP server tools via HTTP/SSE.
    Extends McpServerTool and overrides _run to use direct HTTP calls instead of client.mcp_tool_call.
    """
    
    # Remote MCP connection details
    server_url: str = Field(..., description="URL of the remote MCP server")
    server_headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers for authentication")
    original_tool_name: Optional[str] = Field(default=None, description="Original tool name from MCP server (before optimization)")
    is_prompt: bool = False  # Flag to indicate if this is a prompt tool
    prompt_name: Optional[str] = None  # Original prompt name if this is a prompt
    session_id: Optional[str] = Field(default=None, description="MCP session ID for stateful SSE servers")
    
    def model_post_init(self, __context: Any) -> None:
        """Update metadata with session info after model initialization."""
        super().model_post_init(__context)
        self._update_metadata_with_session()
        self._register_session_metadata()
    
    def _update_metadata_with_session(self):
        """Update the metadata dict with current session information."""
        if self.session_id:
            if self.metadata is None:
                self.metadata = {}
            self.metadata.update({
                'mcp_session_id': self.session_id,
                'mcp_server_url': canonical_resource(self.server_url)
            })
    
    def _register_session_metadata(self):
        """Register session metadata in global registry for callback access."""
        if self.session_id and self.server_url:
            MCP_TOOL_SESSION_REGISTRY[self.name] = {
                'mcp_session_id': self.session_id,
                'mcp_server_url': canonical_resource(self.server_url)
            }
            logger.debug(f"[MCP] Registered session metadata for tool '{self.name}': session={self.session_id}")
    
    def __getstate__(self):
        """Custom serialization for pickle compatibility."""
        state = super().__getstate__()
        # Ensure headers are serializable
        if 'server_headers' in state and state['server_headers'] is not None:
            state['server_headers'] = dict(state['server_headers'])
        return state

    def _run(self, *args, **kwargs):
        """
        Execute the MCP tool via direct HTTP/SSE call to the remote server.
        Overrides the parent method to avoid using client.mcp_tool_call.
        """
        try:
            # Always create a new event loop for sync context
            with ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_in_new_loop, kwargs)
                return future.result(timeout=self.tool_timeout_sec)
        except McpAuthorizationRequired:
            # Bubble up so LangChain can surface a tool error with useful metadata
            raise
        except Exception as e:
            logger.error(f"Error executing remote MCP tool '{self.name}': {e}")
            return f"Error executing tool: {e}"

    def _run_in_new_loop(self, kwargs: Dict[str, Any]) -> str:
        """Run the async tool invocation in a new event loop."""
        return asyncio.run(self._execute_remote_tool(kwargs))

    async def _execute_remote_tool(self, kwargs: Dict[str, Any]) -> str:
        """Execute the actual remote MCP tool call using SSE client."""
        
        # Check for session_id requirement
        if not self.session_id:
            logger.error(f"[MCP Session] Missing session_id for tool '{self.name}'")
            raise Exception("sessionId required. Frontend must generate UUID and send with mcp_tokens.")
        
        # Use the original tool name from discovery for MCP server invocation
        tool_name_for_server = self.original_tool_name
        if not tool_name_for_server:
            tool_name_for_server = self.name
            logger.warning(f"original_tool_name not set for '{self.name}', using: {tool_name_for_server}")
        
        logger.info(f"[MCP] Executing tool '{tool_name_for_server}' with session {self.session_id}")
        
        try:
            # Prepare headers
            headers = {}
            if self.server_headers:
                headers.update(self.server_headers)
            
            # Create unified MCP client (auto-detects transport)
            client = McpClient(
                url=self.server_url,
                session_id=self.session_id,
                headers=headers,
                timeout=self.tool_timeout_sec
            )
            
            # Execute tool call (client auto-detects SSE vs Streamable HTTP)
            async with client:
                await client.initialize()
                result = await client.call_tool(tool_name_for_server, kwargs)
            
            # Format the result
            if isinstance(result, dict):
                # Check for content array (common in MCP responses)
                if "content" in result:
                    content_items = result["content"]
                    if isinstance(content_items, list):
                        # Extract text from content items
                        text_parts = []
                        for item in content_items:
                            if isinstance(item, dict):
                                if item.get("type") == "text" and "text" in item:
                                    text_parts.append(item["text"])
                                elif "text" in item:
                                    text_parts.append(item["text"])
                                else:
                                    text_parts.append(json.dumps(item))
                            else:
                                text_parts.append(str(item))
                        return "\n".join(text_parts)
                
                # Return formatted JSON if no content field
                return json.dumps(result, indent=2)
            
            # Return as string for other types
            return str(result)
            
        except Exception as e:
            logger.error(f"[MCP] Tool execution failed: {e}", exc_info=True)
            raise

    def _parse_sse(self, text: str) -> Dict[str, Any]:
        """Parse Server-Sent Events (SSE) format response."""
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('data:'):
                json_str = line[5:].strip()
                return json.loads(json_str)
        raise ValueError("No data found in SSE response")
    
    def get_session_metadata(self) -> dict:
        """Return session metadata to be included in tool responses."""
        if self.session_id:
            return {
                'mcp_session_id': self.session_id,
                'mcp_server_url': canonical_resource(self.server_url)
            }
        return {}
