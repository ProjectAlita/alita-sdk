"""
Unified MCP Client with auto-detection for SSE and Streamable HTTP transports.

This module provides a unified interface for MCP server communication that
automatically detects and uses the appropriate transport:
- SSE (Server-Sent Events): Traditional dual-connection model (GET for stream, POST for commands)
- Streamable HTTP: Newer POST-based model used by servers like GitHub Copilot MCP

Usage:
    # Auto-detect transport (recommended)
    client = McpClient(url=url, session_id=session_id, headers=headers)
    
    # Force specific transport
    client = McpClient(url=url, session_id=session_id, transport="streamable_http")
    
    async with client:
        await client.initialize()
        tools = await client.list_tools()
        result = await client.call_tool("tool_name", {"arg": "value"})
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

import aiohttp

from .mcp_oauth import McpAuthorizationRequired

logger = logging.getLogger(__name__)

# Transport types
TransportType = Literal["auto", "sse", "streamable_http"]


class McpClient:
    """
    Unified MCP client that supports both SSE and Streamable HTTP transports.
    
    Auto-detects the appropriate transport by trying Streamable HTTP first,
    then falling back to SSE if the server returns 405 Method Not Allowed.
    """
    
    def __init__(
        self,
        url: str,
        session_id: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 300,
        transport: TransportType = "auto"
    ):
        """
        Initialize the unified MCP client.
        
        Args:
            url: MCP server URL
            session_id: Session ID for stateful connections (auto-generated if not provided)
            headers: HTTP headers (e.g., Authorization)
            timeout: Request timeout in seconds
            transport: Transport type - "auto", "sse", or "streamable_http"
        """
        self.url = url
        self.session_id = session_id or str(uuid.uuid4())
        self.headers = headers or {}
        self.timeout = timeout
        self.transport = transport
        
        # Will be set during connection
        self._detected_transport: Optional[str] = None
        self._sse_client = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._mcp_session_id: Optional[str] = None  # Server-provided session ID
        self._initialized = False
        
        logger.info(f"[MCP Client] Created for {url} (transport={transport}, session={self.session_id})")
    
    @property
    def server_session_id(self) -> Optional[str]:
        """Get the server-provided session ID (from mcp-session-id header)."""
        return self._mcp_session_id
    
    @property
    def detected_transport(self) -> Optional[str]:
        """Get the detected transport type."""
        return self._detected_transport
    
    async def __aenter__(self):
        """Async context manager entry - detect and connect."""
        await self._connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup."""
        await self.close()
    
    async def _connect(self):
        """Detect transport and establish connection."""
        if self.transport == "sse":
            self._detected_transport = "sse"
            await self._connect_sse()
        elif self.transport == "streamable_http":
            self._detected_transport = "streamable_http"
            await self._connect_streamable_http()
        else:  # auto
            await self._auto_detect_and_connect()
    
    async def _auto_detect_and_connect(self):
        """Try Streamable HTTP first, fall back to SSE."""
        # If URL ends with /sse, use SSE transport directly
        if self.url.rstrip('/').endswith('/sse'):
            logger.debug("[MCP Client] URL ends with /sse, using SSE transport")
            await self._connect_sse()
            self._detected_transport = "sse"
            logger.info("[MCP Client] Using SSE transport")
            return
            
        try:
            logger.debug("[MCP Client] Auto-detecting transport, trying Streamable HTTP first...")
            await self._connect_streamable_http()
            self._detected_transport = "streamable_http"
            logger.info("[MCP Client] Using Streamable HTTP transport")
        except Exception as e:
            error_str = str(e).lower()
            # Check for 405, 404, or indicators that SSE is needed
            if "405" in error_str or "method not allowed" in error_str or "404" in error_str:
                logger.debug(f"[MCP Client] Streamable HTTP not supported ({e}), trying SSE...")
                await self._connect_sse()
                self._detected_transport = "sse"
                logger.info("[MCP Client] Using SSE transport")
            else:
                # Re-raise other errors
                raise
    
    async def _connect_streamable_http(self):
        """Connect using Streamable HTTP transport."""
        self._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
    
    async def _connect_sse(self):
        """Connect using SSE transport."""
        from .mcp_sse_client import McpSseClient
        
        self._sse_client = McpSseClient(
            url=self.url,
            session_id=self.session_id,
            headers=self.headers,
            timeout=self.timeout
        )
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize MCP protocol session.
        
        Returns:
            Server capabilities and info
        """
        if self._detected_transport == "streamable_http":
            return await self._initialize_streamable_http()
        else:
            return await self._initialize_sse()
    
    async def _initialize_streamable_http(self, retry_without_session: bool = False) -> Dict[str, Any]:
        """Initialize via Streamable HTTP transport."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers
        }
        
        # DON'T send session_id on initialization - per MCP spec, initialization requests
        # must not include a sessionId. The server will provide one in the response.
        # Session ID is only used for subsequent requests after initialization.
        # (The retry_without_session flag is kept for backwards compatibility but
        # is effectively always true for initialization now)
        
        # Debug: log headers (mask sensitive data)
        debug_headers = {k: (v[:20] + '...' if k.lower() == 'authorization' and len(v) > 20 else v) 
                        for k, v in headers.items()}
        logger.debug(f"[MCP Client] Request headers: {debug_headers}")
        
        init_request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
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
        }
        
        logger.debug(f"[MCP Client] Sending initialize via Streamable HTTP to {self.url}")
        
        async with self._http_session.post(self.url, json=init_request, headers=headers) as response:
            if response.status == 401:
                await self._handle_401_response(response)
            
            if response.status == 405:
                raise Exception("HTTP 405 Method Not Allowed - server may require SSE transport")
            
            # Handle invalid session error - retry without session_id
            if response.status == 400 and not retry_without_session and self.session_id:
                try:
                    error_body = await response.text()
                    if "invalid session" in error_body.lower():
                        logger.warning(f"[MCP Client] Invalid session, retrying without session_id")
                        return await self._initialize_streamable_http(retry_without_session=True)
                except Exception:
                    pass
            
            # Log error response body for debugging
            if response.status >= 400:
                try:
                    error_body = await response.text()
                    logger.error(f"[MCP Client] HTTP {response.status} error response: {error_body[:1000]}")
                except Exception:
                    pass
            
            response.raise_for_status()
            
            # Get session ID from response headers
            self._mcp_session_id = response.headers.get("mcp-session-id")
            if self._mcp_session_id:
                logger.info(f"[MCP Client] Server provided session_id: {self._mcp_session_id}")
            else:
                logger.debug(f"[MCP Client] No session_id in response headers. Headers: {dict(response.headers)}")
            
            # Parse response
            result = await self._parse_response(response)
            logger.debug(f"[MCP Client] Initialize response: {result}")
        
        # Send initialized notification
        await self._send_notification("notifications/initialized")
        
        self._initialized = True
        return result.get('result', {})
    
    async def _initialize_sse(self) -> Dict[str, Any]:
        """Initialize via SSE transport."""
        result = await self._sse_client.initialize()
        self._initialized = True
        return result
    
    async def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a JSON-RPC request to the MCP server.
        
        Args:
            method: JSON-RPC method name (e.g., "tools/list", "tools/call")
            params: Method parameters
            request_id: Optional request ID (auto-generated if not provided)
            
        Returns:
            Parsed JSON-RPC response
        """
        if self._detected_transport == "streamable_http":
            return await self._send_request_streamable_http(method, params, request_id)
        else:
            return await self._sse_client.send_request(method, params, request_id)
    
    async def _send_request_streamable_http(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send request via Streamable HTTP."""
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers
        }
        
        # Add MCP session ID if we have one
        if self._mcp_session_id:
            headers["mcp-session-id"] = self._mcp_session_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }
        
        logger.debug(f"[MCP Client] Sending request: {method} (id={request_id})")
        
        async with self._http_session.post(self.url, json=request, headers=headers) as response:
            if response.status == 401:
                await self._handle_401_response(response)
            
            response.raise_for_status()
            
            result = await self._parse_response(response)
            
            # Check for JSON-RPC error
            if 'error' in result:
                error = result['error']
                raise Exception(f"MCP Error: {error.get('message', str(error))}")
            
            return result
    
    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Send a JSON-RPC notification (no response expected)."""
        if self._detected_transport == "streamable_http":
            headers = {
                "Content-Type": "application/json",
                **self.headers
            }
            if self._mcp_session_id:
                headers["mcp-session-id"] = self._mcp_session_id
            
            notification = {
                "jsonrpc": "2.0",
                "method": method
            }
            if params:
                notification["params"] = params
            
            async with self._http_session.post(self.url, json=notification, headers=headers) as response:
                pass  # Notifications don't expect a response
    
    async def _parse_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Parse response, handling both JSON and SSE formats."""
        content_type = response.headers.get("content-type", "")
        text = await response.text()
        
        if "text/event-stream" in content_type:
            return self._parse_sse_text(text)
        else:
            return json.loads(text) if text else {}
    
    def _parse_sse_text(self, text: str) -> Dict[str, Any]:
        """Parse SSE formatted response to extract JSON data."""
        for line in text.split('\n'):
            if line.startswith('data:'):
                data = line[5:].strip()
                if data:
                    return json.loads(data)
        return {}
    
    async def _handle_401_response(self, response: aiohttp.ClientResponse):
        """Handle 401 Unauthorized response with OAuth flow."""
        from .mcp_oauth import (
            canonical_resource,
            extract_resource_metadata_url,
            extract_authorization_uri,
            fetch_resource_metadata_async,
            infer_authorization_servers_from_realm,
            fetch_oauth_authorization_server_metadata
        )
        
        auth_header = response.headers.get('WWW-Authenticate', '')
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
        
        # Fall back to resource_metadata if authorization_uri didn't work
        if not metadata:
            if resource_metadata_url:
                metadata = await fetch_resource_metadata_async(
                    resource_metadata_url,
                    session=self._http_session,
                    timeout=30
                )
                # If we got resource_metadata, also fetch oauth_authorization_server
                if metadata and metadata.get('authorization_servers'):
                    auth_server_metadata = fetch_oauth_authorization_server_metadata(
                        metadata['authorization_servers'][0], timeout=30
                    )
                    if auth_server_metadata:
                        metadata['oauth_authorization_server'] = auth_server_metadata
        
        # Infer authorization servers if not in metadata
        if not metadata or not metadata.get('authorization_servers'):
            inferred_servers = infer_authorization_servers_from_realm(auth_header, self.url)
            if inferred_servers:
                if not metadata:
                    metadata = {}
                metadata['authorization_servers'] = inferred_servers
                
                # Fetch OAuth metadata
                auth_server_metadata = fetch_oauth_authorization_server_metadata(inferred_servers[0], timeout=30)
                if auth_server_metadata:
                    metadata['oauth_authorization_server'] = auth_server_metadata
        
        raise McpAuthorizationRequired(
            message=f"MCP server {self.url} requires OAuth authorization",
            server_url=canonical_resource(self.url),
            resource_metadata_url=resource_metadata_url,
            www_authenticate=auth_header,
            resource_metadata=metadata,
            status=401,
            tool_name=self.url,
        )
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools from the MCP server.
        
        Returns:
            List of tool definitions
        """
        response = await self.send_request("tools/list")
        result = response.get('result', {})
        tools = result.get('tools', [])
        logger.info(f"[MCP Client] Discovered {len(tools)} tools")
        return tools
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """
        Get list of available prompts from the MCP server.
        
        Returns:
            List of prompt definitions
        """
        response = await self.send_request("prompts/list")
        result = response.get('result', {})
        prompts = result.get('prompts', [])
        logger.debug(f"[MCP Client] Discovered {len(prompts)} prompts")
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
            "tools/call",
            params={
                "name": tool_name,
                "arguments": arguments
            }
        )
        return response.get('result', {})
    
    async def close(self):
        """Close the client and cleanup resources."""
        logger.info(f"[MCP Client] Closing connection...")
        
        if self._sse_client:
            await self._sse_client.close()
            self._sse_client = None
        
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None
        
        logger.info(f"[MCP Client] Connection closed")
    
    @property
    def detected_transport(self) -> Optional[str]:
        """Return the detected/selected transport type."""
        return self._detected_transport
