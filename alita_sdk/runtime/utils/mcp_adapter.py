"""
Unified MCP Adapter using langchain-mcp-adapters.

This adapter provides a compatibility layer between the old custom McpClient
interface and the official langchain-mcp-adapters implementation.

Phase 2 of MCP consolidation plan - provides backward compatibility while
migrating from custom McpClient/McpSseClient to langchain-mcp-adapters.

Usage:
    # Old way (custom client):
    from ..utils.mcp_client import McpClient
    client = McpClient(url=url, headers=headers)

    # New way (unified adapter):
    from ..utils.mcp_adapter import UnifiedMcpClient
    client = UnifiedMcpClient(url=url, headers=headers)

    # Both have same interface!
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UnifiedMcpClient:
    """
    Unified MCP client using langchain-mcp-adapters under the hood.

    Provides compatibility with the existing McpClient interface while
    using the official langchain-mcp-adapters implementation internally.

    This allows incremental migration - code can switch from McpClient
    to UnifiedMcpClient without changing the interface.
    """

    def __init__(
        self,
        url: str,
        session_id: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 300,
        transport: str = "auto",
        ssl_verify: bool = True
    ):
        """
        Initialize the unified MCP client.

        Args:
            url: MCP server URL
            session_id: Session ID (for compatibility, may not be used by adapter)
            headers: HTTP headers (e.g., Authorization)
            timeout: Request timeout in seconds
            transport: Transport type - "auto", "sse", "streamable_http", "stdio"
            ssl_verify: Whether to verify SSL certificates (default: True)
        """
        self.url = url
        self.session_id = session_id or str(uuid.uuid4())
        self.headers = headers or {}
        self.timeout = timeout
        self.transport = transport
        self.ssl_verify = ssl_verify

        # Internal state
        self._client = None
        self._session = None
        self._session_context = None
        self._server_name = f"mcp_server_{self.session_id[:8]}"
        self._initialized = False
        self._detected_transport = None

        logger.info(f"[Unified MCP] Created client for {url} (transport={transport}, ssl_verify={ssl_verify})")

    async def __aenter__(self):
        """Async context manager entry."""
        await self._connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _connect(self):
        """Establish connection using langchain-mcp-adapters."""
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            raise ImportError(
                "langchain-mcp-adapters is required. "
                "Install with: pip install langchain-mcp-adapters"
            )

        # Detect transport if auto
        detected_transport = self._detect_transport()

        # For HTTP-based transports, do a pre-flight 401 check
        # This catches OAuth requirements before langchain-mcp-adapters wraps the error
        if detected_transport in ['streamable_http', 'sse', 'http']:
            await self._preflight_auth_check()

        # Build server config for langchain-mcp-adapters
        # Note: SSL verification is handled via httpx_client_factory in _build_server_config
        server_config = self._build_server_config(detected_transport)

        logger.debug(f"[Unified MCP] Connecting with config: {server_config}")

        # Create MultiServerMCPClient with single server
        self._client = MultiServerMCPClient({self._server_name: server_config})

        # Create persistent session
        self._session_context = self._client.session(self._server_name)
        self._session = await self._session_context.__aenter__()

        self._detected_transport = detected_transport
        logger.info(f"[Unified MCP] Connected using {detected_transport} transport")

    def _detect_transport(self) -> str:
        """
        Detect transport type from URL and configuration.

        Mimics the logic from custom McpClient._auto_detect_and_connect.
        """
        if self.transport != "auto":
            return self.transport

        # If URL ends with /sse, use SSE transport
        if self.url.rstrip('/').endswith('/sse'):
            logger.debug("[Unified MCP] URL ends with /sse, using SSE transport")
            return "sse"

        # Default to streamable_http for HTTP URLs
        if self.url.startswith('http://') or self.url.startswith('https://'):
            return "streamable_http"

        # Fallback to streamable_http
        return "streamable_http"

    def _build_server_config(self, transport: str) -> Dict[str, Any]:
        """
        Build server configuration for langchain-mcp-adapters.

        Converts our interface to langchain-mcp-adapters format.
        """
        config = {
            'transport': transport,
        }

        if transport in ['streamable_http', 'sse', 'http']:
            config['url'] = self.url
            if self.headers:
                config['headers'] = self.headers
            # Use httpx_client_factory to disable SSL verification
            # This is the proper way to configure SSL in langchain-mcp-adapters
            if not self.ssl_verify:
                config['httpx_client_factory'] = self._create_insecure_httpx_client
                logger.warning("[Unified MCP] Using custom httpx client with SSL verification disabled")
        elif transport == 'stdio':
            # Not typically used via this adapter, but support it
            raise ValueError("stdio transport not supported via UnifiedMcpClient URL interface")

        return config

    def _create_insecure_httpx_client(self, headers=None, timeout=None, auth=None):
        """
        Create an httpx.AsyncClient with SSL verification disabled.

        This factory is passed to langchain-mcp-adapters when ssl_verify=False.
        """
        import httpx

        return httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            auth=auth,
            verify=False  # Disable SSL certificate verification
        )

    async def _preflight_auth_check(self):
        """
        Pre-flight check for authentication requirements.

        Makes a test initialize request to the MCP server BEFORE attempting
        to connect with langchain-mcp-adapters. This allows us to catch 401
        responses and extract OAuth metadata from the raw HTTP response.

        Raises:
            McpAuthorizationRequired: If server returns 401 with OAuth metadata
        """
        import aiohttp
        import ssl
        from ..utils.mcp_oauth import McpAuthorizationRequired

        # Configure SSL context based on ssl_verify setting
        ssl_context = None
        if not self.ssl_verify:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            logger.warning("[Unified MCP] SSL verification disabled for preflight check")

        try:
            # Create connector with SSL settings
            connector = aiohttp.TCPConnector(ssl=ssl_context) if not self.ssl_verify else None
            # Make a test request to check for 401
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector
            ) as session:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    **self.headers
                }

                # Try to make a simple initialize request
                init_request = {
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "ELITEA MCP Client",
                            "version": "1.0.0"
                        }
                    }
                }

                async with session.post(self.url, json=init_request, headers=headers) as response:
                    if response.status == 401:
                        logger.info(f"[Unified MCP] Server requires OAuth authorization (401)")
                        # Extract OAuth metadata and raise McpAuthorizationRequired
                        try:
                            await self._handle_401_response(response)
                        except Exception as handle_ex:
                            logger.error(f"[Unified MCP] _handle_401_response raised: {type(handle_ex).__name__}: {handle_ex}")
                            raise
                    # Not a 401, auth check passed (or server will handle auth differently)

        except McpAuthorizationRequired:
            # Re-raise McpAuthorizationRequired - this is expected and should propagate
            raise
        except Exception as e:
            # If pre-flight check fails for non-auth reasons, log but don't block
            # Let langchain-mcp-adapters try and it will fail with proper error
            error_str = str(e).lower()
            if '401' in error_str or 'unauthorized' in error_str:
                # This is still an auth error, but we couldn't extract details
                logger.warning(f"[Unified MCP] Pre-flight auth check failed with possible 401: {e}")
            # Non-auth errors are ignored - langchain-mcp-adapters will handle them

    async def _handle_401_response(self, response):
        """
        Handle 401 Unauthorized response by extracting OAuth metadata and raising exception.

        Args:
            response: aiohttp.ClientResponse with 401 status

        Raises:
            McpAuthorizationRequired: Always, with OAuth metadata
        """
        from ..utils.mcp_oauth import (
            McpAuthorizationRequired,
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
                # Create a new session for fetching resource metadata
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    metadata = await fetch_resource_metadata_async(
                        resource_metadata_url,
                        session=session,
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

    @property
    def detected_transport(self) -> Optional[str]:
        """Get the detected transport type."""
        return self._detected_transport

    @property
    def server_session_id(self) -> Optional[str]:
        """
        Get the server-provided session ID.

        For compatibility with custom McpClient interface.
        langchain-mcp-adapters may provide session IDs differently,
        so we return the session_id we're using.
        """
        return self.session_id

    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize MCP session.

        Returns server capabilities and info.

        For langchain-mcp-adapters, initialization happens during session creation,
        so this is mostly a no-op for compatibility.
        """
        if self._initialized:
            return {'status': 'already_initialized'}

        if not self._session:
            await self._connect()

        # Session is already initialized by _connect
        self._initialized = True

        logger.info("[Unified MCP] MCP session initialized")
        return {'status': 'initialized'}

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from the MCP server.

        Returns:
            List of tool dictionaries with name, description, and inputSchema.
        """
        if not self._session:
            await self._connect()

        try:
            from langchain_mcp_adapters.tools import load_mcp_tools
        except ImportError:
            raise ImportError(
                "langchain-mcp-adapters is required. "
                "Install with: pip install langchain-mcp-adapters"
            )

        # Load tools using langchain-mcp-adapters
        connection = self._client.connections.get(self._server_name)
        tools = await load_mcp_tools(
            self._session,
            connection=connection,
            server_name=self._server_name
        )

        # Convert LangChain tools to our format
        tool_list = []
        for tool in tools:
            tool_dict = {
                'name': tool.name,
                'description': tool.description or '',
            }

            # Add inputSchema if available
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    # Handle both dict (already JSON schema) and Pydantic model
                    if isinstance(tool.args_schema, dict):
                        # langchain-mcp-adapters returns dict (already JSON schema)
                        tool_dict['inputSchema'] = tool.args_schema
                    else:
                        # Pydantic model - convert to JSON schema
                        tool_dict['inputSchema'] = tool.args_schema.model_json_schema()
                except Exception as e:
                    logger.warning(f"[Unified MCP] Failed to convert args_schema for {tool.name}: {e}")

            tool_list.append(tool_dict)

        logger.info(f"[Unified MCP] Listed {len(tool_list)} tools")
        return tool_list

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        if not self._session:
            await self._connect()

        try:
            from langchain_mcp_adapters.tools import load_mcp_tools
        except ImportError:
            raise ImportError(
                "langchain-mcp-adapters is required. "
                "Install with: pip install langchain-mcp-adapters"
            )

        # Load tools to get the specific tool
        connection = self._client.connections.get(self._server_name)
        tools = await load_mcp_tools(
            self._session,
            connection=connection,
            server_name=self._server_name
        )

        # Find the tool
        target_tool = None
        for tool in tools:
            if tool.name == tool_name:
                target_tool = tool
                break

        if not target_tool:
            raise ValueError(f"Tool '{tool_name}' not found")

        # Call the tool
        logger.debug(f"[Unified MCP] Calling tool {tool_name} with args: {arguments}")

        # LangChain tools can be invoked with  .a/invoke() or ._run()
        if hasattr(target_tool, 'ainvoke'):
            result = await target_tool.ainvoke(arguments or {})
        elif hasattr(target_tool, 'invoke'):
            result = await target_tool.invoke(arguments or {})
        elif hasattr(target_tool, '_arun'):
            result = await target_tool._arun(**(arguments or {}))
        else:
            result = target_tool.run(**(arguments or {}))

        # Format result to match MCP protocol
        return {
            'content': [{'type': 'text', 'text': str(result)}]
        }

    async def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a raw JSON-RPC request.

        This is for compatibility with custom McpClient interface.
        Most code should use higher-level methods like list_tools() or call_tool().
        """
        if not self._session:
            await self._connect()

        # Map common methods to our interface
        if method == 'tools/list':
            tools = await self.list_tools()
            return {'result': {'tools': tools}}
        elif method == 'tools/call':
            tool_name = params.get('name') if params else None
            arguments = params.get('arguments', {}) if params else {}
            result = await self.call_tool(tool_name, arguments)
            return {'result': result}
        elif method == 'initialize':
            result = await self.initialize()
            return {'result': result}
        else:
            logger.warning(f"[Unified MCP] Unsupported method: {method}")
            raise NotImplementedError(f"Method '{method}' not supported by UnifiedMcpClient")

    async def close(self):
        """Close the MCP connection."""
        logger.info("[Unified MCP] Closing connection...")

        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"[Unified MCP] Error closing session: {e}")

        self._session = None
        self._session_context = None
        self._client = None
        self._initialized = False

        logger.info("[Unified MCP] Connection closed")


# Convenience function for creating clients
def create_mcp_client(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 300,
    transport: str = "auto",
    ssl_verify: bool = True
) -> UnifiedMcpClient:
    """
    Create a unified MCP client.

    This is a drop-in replacement for creating custom McpClient instances.

    Args:
        url: MCP server URL
        headers: HTTP headers (authentication, etc.)
        timeout: Request timeout in seconds
        transport: Transport type ("auto", "sse", "streamable_http")
        ssl_verify: Whether to verify SSL certificates (default: True)

    Returns:
        UnifiedMcpClient instance
    """
    return UnifiedMcpClient(
        url=url,
        headers=headers,
        timeout=timeout,
        transport=transport,
        ssl_verify=ssl_verify
    )
