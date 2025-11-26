"""
Dynamic MCP Server Discovery Client.
Implements the MCP protocol for discovering tools from remote servers.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urlparse
import aiohttp
from datetime import datetime, timedelta

from ..models.mcp_models import McpConnectionConfig, McpToolMetadata

logger = logging.getLogger(__name__)


@dataclass
class McpServerInfo:
    """Information about an MCP server."""
    name: str
    url: str
    headers: Optional[Dict[str, str]] = None
    last_discovery: Optional[datetime] = None
    tools: List[McpToolMetadata] = field(default_factory=list)
    status: str = "unknown"  # unknown, online, offline, error
    error: Optional[str] = None


class McpDiscoveryClient:
    """
    Client for dynamically discovering tools from MCP servers.
    Implements the MCP protocol for tool discovery.
    """

    def __init__(
        self,
        discovery_interval: int = 300,  # 5 minutes
        request_timeout: int = 30,
        max_retries: int = 3,
        cache_ttl: int = 600  # 10 minutes
    ):
        self.discovery_interval = discovery_interval
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.cache_ttl = cache_ttl

        # Server registry
        self.servers: Dict[str, McpServerInfo] = {}
        self.session: Optional[aiohttp.ClientSession] = None

        # Discovery state
        self._discovery_task: Optional[asyncio.Task] = None
        self._running = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def start(self):
        """Start the discovery client."""
        if self._running:
            return

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.request_timeout)
        )
        self._running = True

        # Start background discovery task
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        logger.info("MCP Discovery Client started")

    async def stop(self):
        """Stop the discovery client."""
        if not self._running:
            return

        self._running = False

        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass

        if self.session:
            await self.session.close()

        logger.info("MCP Discovery Client stopped")

    def add_server(self, server_name: str, connection_config: McpConnectionConfig):
        """Add an MCP server to discovery."""
        server_info = McpServerInfo(
            name=server_name,
            url=connection_config.url,
            headers=connection_config.headers
        )
        self.servers[server_name] = server_info
        logger.info(f"Added MCP server for discovery: {server_name} at {connection_config.url}")

    def remove_server(self, server_name: str):
        """Remove an MCP server from discovery."""
        if server_name in self.servers:
            del self.servers[server_name]
            logger.info(f"Removed MCP server from discovery: {server_name}")

    async def discover_server_tools(self, server_name: str, force: bool = False) -> List[McpToolMetadata]:
        """Discover tools from a specific MCP server."""
        if server_name not in self.servers:
            raise ValueError(f"Server {server_name} not registered for discovery")

        server_info = self.servers[server_name]

        # Check cache unless force refresh
        if not force and self._is_cache_valid(server_info):
            logger.debug(f"Using cached tools for server {server_name}")
            return server_info.tools

        try:
            tools = await self._fetch_server_tools(server_info)
            server_info.tools = tools
            server_info.last_discovery = datetime.now()
            server_info.status = "online"
            server_info.error = None

            logger.info(f"Discovered {len(tools)} tools from server {server_name}")
            return tools

        except Exception as e:
            error_msg = f"Failed to discover tools from {server_name}: {e}"
            logger.error(error_msg)
            server_info.status = "error"
            server_info.error = str(e)
            return []

    async def get_all_tools(self) -> Dict[str, List[McpToolMetadata]]:
        """Get all discovered tools from all servers."""
        all_tools = {}

        for server_name in self.servers:
            tools = await self.discover_server_tools(server_name)
            all_tools[server_name] = tools

        return all_tools

    def get_server_status(self, server_name: str) -> Optional[McpServerInfo]:
        """Get status information for a server."""
        return self.servers.get(server_name)

    def get_all_server_status(self) -> Dict[str, McpServerInfo]:
        """Get status information for all servers."""
        return self.servers.copy()

    async def _discovery_loop(self):
        """Background task for periodic tool discovery."""
        while self._running:
            try:
                await self._perform_discovery()
                await asyncio.sleep(self.discovery_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _perform_discovery(self):
        """Perform discovery on all registered servers."""
        if not self.servers:
            return

        discovery_tasks = [
            self.discover_server_tools(server_name)
            for server_name in self.servers
        ]

        results = await asyncio.gather(*discovery_tasks, return_exceptions=True)

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                server_name = list(self.servers.keys())[i]
                logger.error(f"Discovery failed for server {server_name}: {result}")

    async def _fetch_server_tools(self, server_info: McpServerInfo) -> List[McpToolMetadata]:
        """Fetch tools from an MCP server using HTTP requests."""
        if not self.session:
            raise RuntimeError("Discovery client not started")

        # MCP protocol: list_tools request
        mcp_request = {
            "jsonrpc": "2.0",
            "id": f"discover_{int(time.time())}",
            "method": "tools/list",
            "params": {}
        }

        headers = {"Content-Type": "application/json"}
        if server_info.headers:
            headers.update(server_info.headers)

        async with self.session.post(
            server_info.url,
            json=mcp_request,
            headers=headers
        ) as response:

            if response.status != 200:
                raise Exception(f"HTTP {response.status}: {await response.text()}")

            data = await response.json()

            if "error" in data:
                raise Exception(f"MCP Error: {data['error']}")

            # Parse MCP response
            tools_data = data.get("result", {}).get("tools", [])
            tools = []

            for tool_data in tools_data:
                try:
                    tool_metadata = McpToolMetadata(
                        name=tool_data.get("name", ""),
                        description=tool_data.get("description", ""),
                        server=server_info.name,
                        input_schema=tool_data.get("inputSchema", {}),
                        enabled=True
                    )
                    tools.append(tool_metadata)
                except Exception as e:
                    logger.warning(f"Failed to parse tool from {server_info.name}: {e}")

            return tools

    def _is_cache_valid(self, server_info: McpServerInfo) -> bool:
        """Check if cached tools are still valid."""
        if not server_info.last_discovery:
            return False

        cache_age = datetime.now() - server_info.last_discovery
        return cache_age.total_seconds() < self.cache_ttl


class McpDiscoveryService:
    """
    High-level service for managing MCP server discovery.
    Integrates with the existing toolkit system.
    """

    def __init__(self, discovery_client: Optional[McpDiscoveryClient] = None):
        self.client = discovery_client or McpDiscoveryClient()
        self._started = False

    async def start(self):
        """Start the discovery service."""
        if not self._started:
            await self.client.start()
            self._started = True

    async def stop(self):
        """Stop the discovery service."""
        if self._started:
            await self.client.stop()
            self._started = False

    async def register_server(self, server_name: str, connection_config: McpConnectionConfig):
        """Register an MCP server for discovery."""
        self.client.add_server(server_name, connection_config)

        # Perform immediate discovery
        await self.client.discover_server_tools(server_name, force=True)

    def unregister_server(self, server_name: str):
        """Unregister an MCP server."""
        self.client.remove_server(server_name)

    async def get_server_tools(self, server_name: str) -> List[McpToolMetadata]:
        """Get tools from a specific server."""
        return await self.client.discover_server_tools(server_name)

    async def get_all_available_tools(self) -> Dict[str, List[McpToolMetadata]]:
        """Get all available tools from all registered servers."""
        return await self.client.get_all_tools()

    def get_server_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all servers."""
        status_info = {}

        for name, server_info in self.client.get_all_server_status().items():
            status_info[name] = {
                "status": server_info.status,
                "url": server_info.url,
                "last_discovery": server_info.last_discovery.isoformat() if server_info.last_discovery else None,
                "tool_count": len(server_info.tools),
                "error": server_info.error
            }

        return status_info

    async def refresh_server(self, server_name: str):
        """Force refresh tools from a specific server."""
        await self.client.discover_server_tools(server_name, force=True)

    async def refresh_all_servers(self):
        """Force refresh tools from all servers."""
        for server_name in self.client.servers:
            await self.client.discover_server_tools(server_name, force=True)


# Global discovery service instance
_discovery_service: Optional[McpDiscoveryService] = None


def get_discovery_service() -> McpDiscoveryService:
    """Get the global MCP discovery service instance."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = McpDiscoveryService()
    return _discovery_service


async def init_discovery_service():
    """Initialize the global discovery service."""
    service = get_discovery_service()
    await service.start()


async def shutdown_discovery_service():
    """Shutdown the global discovery service."""
    global _discovery_service
    if _discovery_service:
        await _discovery_service.stop()
        _discovery_service = None