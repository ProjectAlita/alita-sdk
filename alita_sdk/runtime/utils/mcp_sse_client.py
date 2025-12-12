"""
MCP SSE (Server-Sent Events) Client
Handles persistent SSE connections for MCP servers like Atlassian
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncIterator
import aiohttp

logger = logging.getLogger(__name__)


class McpSseClient:
    """
    Client for MCP servers using SSE (Server-Sent Events) transport.
    
    For Atlassian-style SSE (dual-connection model):
    - GET request opens persistent SSE stream for receiving events
    - POST requests send commands (return 202 Accepted immediately)
    - Responses come via the GET stream
    
    This client handles:
    - Opening persistent SSE connection via GET
    - Sending JSON-RPC requests via POST
    - Reading SSE event streams
    - Matching responses to requests by ID
    """
    
    def __init__(self, url: str, session_id: str, headers: Optional[Dict[str, str]] = None, timeout: int = 300):
        """
        Initialize SSE client.
        
        Args:
            url: Base URL of the MCP SSE server
            session_id: Client-generated UUID for session
            headers: Additional headers (e.g., Authorization)
            timeout: Request timeout in seconds
        """
        self.url = url
        self.session_id = session_id
        self.headers = headers or {}
        self.timeout = timeout
        self.url_with_session = f"{url}?sessionId={session_id}"
        self._stream_task = None
        self._pending_requests = {}  # request_id -> asyncio.Future
        self._stream_session = None
        self._stream_response = None
        self._endpoint_ready = asyncio.Event()  # Signal when endpoint is received
        
        logger.info(f"[MCP SSE Client] Initialized for {url} with session {session_id}")
    
    async def _ensure_stream_connected(self):
        """Ensure the GET stream is connected and reading events."""
        if self._stream_task is None or self._stream_task.done():
            logger.info(f"[MCP SSE Client] Opening persistent SSE stream...")
            self._stream_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None))
            
            headers = {
                "Accept": "text/event-stream",
                **self.headers
            }
            
            self._stream_response = await self._stream_session.get(self.url_with_session, headers=headers)
            
            logger.info(f"[MCP SSE Client] Stream opened: status={self._stream_response.status}")
            
            # Handle 401 Unauthorized - need OAuth
            if self._stream_response.status == 401:
                from ..utils.mcp_oauth import (
                    McpAuthorizationRequired,
                    canonical_resource,
                    extract_resource_metadata_url,
                    extract_authorization_uri,
                    fetch_resource_metadata_async,
                    infer_authorization_servers_from_realm,
                    fetch_oauth_authorization_server_metadata
                )
                
                auth_header = self._stream_response.headers.get('WWW-Authenticate', '')
                resource_metadata_url = extract_resource_metadata_url(auth_header, self.url)
                
                # First, try authorization_uri from WWW-Authenticate header (preferred)
                authorization_uri = extract_authorization_uri(auth_header)
                
                metadata = None
                if authorization_uri:
                    # Fetch OAuth metadata directly from authorization_uri
                    auth_server_metadata = fetch_oauth_authorization_server_metadata(authorization_uri, timeout=30)
                    if auth_server_metadata:
                        # Extract base authorization server URL from the issuer or the well-known URL
                        base_auth_server = auth_server_metadata.get('issuer')
                        if not base_auth_server and '/.well-known/' in authorization_uri:
                            base_auth_server = authorization_uri.split('/.well-known/')[0]
                        
                        metadata = {
                            'authorization_servers': [base_auth_server] if base_auth_server else [authorization_uri],
                            'oauth_authorization_server': auth_server_metadata
                        }
                        logger.info(f"[MCP SSE Client] Using authorization_uri: {authorization_uri}, base: {base_auth_server}")
                
                # Fall back to resource_metadata if authorization_uri didn't work
                if not metadata:
                    if resource_metadata_url:
                        metadata = await fetch_resource_metadata_async(
                            resource_metadata_url,
                            session=self._stream_session,
                            timeout=30
                        )
                        # If we got resource_metadata, also fetch oauth_authorization_server
                        if metadata and metadata.get('authorization_servers'):
                            auth_server_metadata = fetch_oauth_authorization_server_metadata(
                                metadata['authorization_servers'][0], timeout=30
                            )
                            if auth_server_metadata:
                                metadata['oauth_authorization_server'] = auth_server_metadata
                                logger.info(f"[MCP SSE Client] Fetched OAuth metadata from resource_metadata")
                
                # Infer authorization servers if not in metadata
                if not metadata or not metadata.get('authorization_servers'):
                    inferred_servers = infer_authorization_servers_from_realm(auth_header, self.url)
                    if inferred_servers:
                        if not metadata:
                            metadata = {}
                        metadata['authorization_servers'] = inferred_servers
                        logger.info(f"[MCP SSE Client] Inferred authorization servers: {inferred_servers}")
                        
                        # Fetch OAuth metadata
                        auth_server_metadata = fetch_oauth_authorization_server_metadata(inferred_servers[0], timeout=30)
                        if auth_server_metadata:
                            metadata['oauth_authorization_server'] = auth_server_metadata
                            logger.info(f"[MCP SSE Client] Fetched OAuth metadata")
                
                raise McpAuthorizationRequired(
                    message=f"MCP server {self.url} requires OAuth authorization",
                    server_url=canonical_resource(self.url),
                    resource_metadata_url=resource_metadata_url,
                    www_authenticate=auth_header,
                    resource_metadata=metadata,
                    status=self._stream_response.status,
                    tool_name=self.url,
                )
            
            if self._stream_response.status != 200:
                error_text = await self._stream_response.text()
                raise Exception(f"Failed to open SSE stream: HTTP {self._stream_response.status}: {error_text}")
            
            # Start background task to read stream
            self._stream_task = asyncio.create_task(self._read_stream())
    
    async def _read_stream(self):
        """Background task that continuously reads the SSE stream."""
        logger.info(f"[MCP SSE Client] Starting stream reader...")
        
        try:
            buffer = ""
            current_event = {}
            
            async for chunk in self._stream_response.content.iter_chunked(1024):
                chunk_str = chunk.decode('utf-8')
                buffer += chunk_str
                
                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line_str = line.strip()
                    
                    # Empty line indicates end of event
                    if not line_str:
                        if current_event and 'data' in current_event:
                            self._process_event(current_event)
                            current_event = {}
                        continue
                    
                    # Parse SSE fields
                    if line_str.startswith('event:'):
                        current_event['event'] = line_str[6:].strip()
                    elif line_str.startswith('data:'):
                        data_str = line_str[5:].strip()
                        current_event['data'] = data_str
                    elif line_str.startswith('id:'):
                        current_event['id'] = line_str[3:].strip()
                    
        except Exception as e:
            logger.error(f"[MCP SSE Client] Stream reader error: {e}")
            # Fail all pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(e)
        finally:
            logger.info(f"[MCP SSE Client] Stream reader stopped")
    
    def _process_event(self, event: Dict[str, str]):
        """Process a complete SSE event."""
        event_type = event.get('event', 'message')
        data_str = event.get('data', '')
        
        # Handle 'endpoint' event - server provides the actual session URL to use
        if event_type == 'endpoint':
            # Extract session ID from endpoint URL
            # Format: /v1/sse?sessionId=<uuid>
            if 'sessionId=' in data_str:
                new_session_id = data_str.split('sessionId=')[1].split('&')[0]
                logger.info(f"[MCP SSE Client] Server provided session ID: {new_session_id}")
                self.session_id = new_session_id
                self.url_with_session = f"{self.url}?sessionId={new_session_id}"
                self._endpoint_ready.set()  # Signal that we can now send requests
            return
        
        # Skip other non-message events
        if event_type != 'message' and not data_str.startswith('{'):
            return
        
        if not data_str:
            return
        
        try:
            data = json.loads(data_str)
            request_id = data.get('id')
            
            logger.debug(f"[MCP SSE Client] Received response for request {request_id}")
            
            # Resolve pending request
            if request_id and request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if not future.done():
                    future.set_result(data)
                
        except json.JSONDecodeError as e:
            logger.warning(f"[MCP SSE Client] Failed to parse SSE data: {e}, data: {repr(data_str)[:200]}")
                            
        except Exception as e:
            logger.error(f"[MCP SSE Client] Stream reader error: {e}")
            # Fail all pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(e)
        finally:
            logger.info(f"[MCP SSE Client] Stream reader stopped")
    
    async def send_request(self, method: str, params: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a JSON-RPC request and wait for response via SSE stream.
        
        Uses dual-connection model:
        1. GET stream is kept open to receive responses
        2. POST request sends the command (returns 202 immediately)
        3. Response comes via the GET stream
        
        Args:
            method: JSON-RPC method name (e.g., "tools/list", "tools/call")
            params: Method parameters
            request_id: Optional request ID (auto-generated if not provided)
            
        Returns:
            Parsed JSON-RPC response
            
        Raises:
            Exception: If request fails or times out
        """
        import time
        if request_id is None:
            request_id = f"{method.replace('/', '_')}_{int(time.time() * 1000)}"
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }
        
        logger.debug(f"[MCP SSE Client] Sending request: {method} (id={request_id})")
        
        # Ensure stream is connected
        await self._ensure_stream_connected()
        
        # Wait for endpoint event (server provides the actual session ID to use)
        await asyncio.wait_for(self._endpoint_ready.wait(), timeout=10)
        
        # Create future for this request
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        # Send POST request
        headers = {
            "Content-Type": "application/json",
            **self.headers
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.url_with_session, json=request, headers=headers) as response:
                    if response.status == 404:
                        error_text = await response.text()
                        raise Exception(f"HTTP 404: {error_text}")
                    
                    # 202 is expected - response will come via stream
                    if response.status not in [200, 202]:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")
            
            # Wait for response from stream (with timeout)
            result = await asyncio.wait_for(future, timeout=self.timeout)
            
            # Check for JSON-RPC error
            if 'error' in result:
                error = result['error']
                raise Exception(f"MCP Error: {error.get('message', str(error))}")
            
            return result
                    
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            logger.error(f"[MCP SSE Client] Request timeout after {self.timeout}s")
            raise Exception(f"SSE request timeout after {self.timeout}s")
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            logger.error(f"[MCP SSE Client] Request failed: {e}")
            raise
    
    async def close(self):
        """Close the persistent SSE stream."""
        logger.info(f"[MCP SSE Client] Closing connection...")
        
        # Cancel background stream reader task
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except (asyncio.CancelledError, Exception) as e:
                logger.debug(f"[MCP SSE Client] Stream task cleanup: {e}")
        
        # Close response stream
        if self._stream_response and not self._stream_response.closed:
            try:
                self._stream_response.close()
            except Exception as e:
                logger.debug(f"[MCP SSE Client] Response close error: {e}")
        
        # Close session
        if self._stream_session and not self._stream_session.closed:
            try:
                await self._stream_session.close()
                # Give aiohttp time to cleanup
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.debug(f"[MCP SSE Client] Session close error: {e}")
        
        logger.info(f"[MCP SSE Client] Connection closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Send initialize request to establish MCP protocol session.
        
        Returns:
            Server capabilities and info
        """
        response = await self.send_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "Alita MCP Client",
                    "version": "1.0.0"
                }
            }
        )
        
        logger.info(f"[MCP SSE Client] MCP session initialized")
        return response.get('result', {})
    
    async def list_tools(self) -> list:
        """
        Discover available tools from the MCP server.
        
        Returns:
            List of tool definitions
        """
        response = await self.send_request(method="tools/list")
        result = response.get('result', {})
        tools = result.get('tools', [])
        
        logger.info(f"[MCP SSE Client] Discovered {len(tools)} tools")
        return tools
    
    async def list_prompts(self) -> list:
        """
        Discover available prompts from the MCP server.
        
        Returns:
            List of prompt definitions
        """
        response = await self.send_request(method="prompts/list")
        result = response.get('result', {})
        prompts = result.get('prompts', [])
        
        logger.debug(f"[MCP SSE Client] Discovered {len(prompts)} prompts")
        return prompts
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        response = await self.send_request(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments
            }
        )
        
        result = response.get('result', {})
        return result
