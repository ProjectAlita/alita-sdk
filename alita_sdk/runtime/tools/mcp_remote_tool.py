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

logger = logging.getLogger(__name__)


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
        """Execute the actual remote MCP tool call."""
        import aiohttp
        from ...tools.utils import TOOLKIT_SPLITTER
        
        # Use the original tool name from discovery for MCP server invocation
        # The MCP server doesn't know about our optimized names
        tool_name_for_server = self.original_tool_name
        
        # Fallback: extract from optimized name if original not stored (backwards compatibility)
        if not tool_name_for_server:
            tool_name_for_server = self.name.rsplit(TOOLKIT_SPLITTER, 1)[-1] if TOOLKIT_SPLITTER in self.name else self.name
            logger.warning(f"original_tool_name not set for '{self.name}', using extracted name: {tool_name_for_server}")
        
        # Build the MCP request based on whether this is a prompt or tool
        if self.is_prompt:
            # For prompts, use prompts/get endpoint
            mcp_request = {
                "jsonrpc": "2.0",
                "id": f"prompt_get_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                "method": "prompts/get",
                "params": {
                    "name": self.prompt_name or tool_name_for_server.replace("prompt_", ""),
                    "arguments": kwargs.get("arguments", kwargs)
                }
            }
        else:
            # For regular tools, use tools/call endpoint
            mcp_request = {
                "jsonrpc": "2.0",
                "id": f"tool_call_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                "method": "tools/call",
                "params": {
                    "name": tool_name_for_server,
                    "arguments": kwargs
                }
            }

        # Set up headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.server_headers:
            headers.update(self.server_headers)

        # Execute the HTTP request
        timeout = aiohttp.ClientTimeout(total=self.tool_timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                logger.debug(f"Calling remote MCP tool '{tool_name_for_server}' (optimized name: '{self.name}') at {self.server_url}")
                logger.debug(f"Request: {json.dumps(mcp_request, indent=2)}")
                
                async with session.post(self.server_url, json=mcp_request, headers=headers) as response:
                    auth_header = response.headers.get('WWW-Authenticate') or response.headers.get('Www-Authenticate')
                    if response.status == 401:
                        resource_metadata_url = extract_resource_metadata_url(auth_header, self.server_url)
                        metadata = None
                        if resource_metadata_url:
                            metadata = await fetch_resource_metadata_async(
                                resource_metadata_url,
                                session=session,
                                timeout=self.tool_timeout_sec,
                            )
                        
                        # If we couldn't get metadata from the resource_metadata endpoint,
                        # infer authorization servers from the WWW-Authenticate header and server URL
                        if not metadata or not metadata.get('authorization_servers'):
                            inferred_servers = infer_authorization_servers_from_realm(auth_header, self.server_url)
                            if inferred_servers:
                                if not metadata:
                                    metadata = {}
                                metadata['authorization_servers'] = inferred_servers
                                logger.info(f"Inferred authorization servers for {self.server_url}: {inferred_servers}")
                                
                                # Fetch OAuth authorization server metadata from the inferred server
                                # This avoids CORS issues in the frontend
                                from alita_sdk.runtime.utils.mcp_oauth import fetch_oauth_authorization_server_metadata
                                auth_server_metadata = fetch_oauth_authorization_server_metadata(inferred_servers[0], timeout=self.tool_timeout_sec)
                                if auth_server_metadata:
                                    metadata['oauth_authorization_server'] = auth_server_metadata
                                    logger.info(f"Fetched OAuth metadata for {inferred_servers[0]}")
                        
                        raise McpAuthorizationRequired(
                            message=f"MCP server {self.server_url} requires OAuth authorization",
                            server_url=canonical_resource(self.server_url),
                            resource_metadata_url=resource_metadata_url,
                            www_authenticate=auth_header,
                            resource_metadata=metadata,
                            status=response.status,
                            tool_name=self.name,
                        )

                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")

                    # Handle both JSON and SSE responses
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/event-stream' in content_type:
                        # Parse SSE format
                        text = await response.text()
                        data = self._parse_sse(text)
                    else:
                        # Parse regular JSON
                        data = await response.json()

                    logger.debug(f"Response: {json.dumps(data, indent=2)}")

                    # Check for MCP error
                    if "error" in data:
                        error = data["error"]
                        error_msg = error.get("message", str(error))
                        raise Exception(f"MCP Error: {error_msg}")

                    # Extract result
                    result = data.get("result", {})
                    
                    # Format the result based on content type
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

            except asyncio.TimeoutError:
                raise Exception(f"Tool execution timed out after {self.tool_timeout_sec}s")
            except Exception as e:
                logger.error(f"Error calling remote MCP tool '{tool_name_for_server}': {e}", exc_info=True)
                raise

    def _parse_sse(self, text: str) -> Dict[str, Any]:
        """Parse Server-Sent Events (SSE) format response."""
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('data:'):
                json_str = line[5:].strip()
                return json.loads(json_str)
        raise ValueError("No data found in SSE response")
