"""
MCP Manager - Unified interface for both static and dynamic MCP tool discovery.
Provides a single API that can work with both registry-based and live discovery.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from ..models.mcp_models import McpConnectionConfig, McpToolMetadata
from .mcp_discovery import McpDiscoveryService, get_discovery_service

logger = logging.getLogger(__name__)


class DiscoveryMode(Enum):
    """MCP discovery modes."""
    STATIC = "static"      # Use alita.get_mcp_toolkits() registry
    DYNAMIC = "dynamic"    # Live discovery from MCP servers
    HYBRID = "hybrid"      # Try dynamic first, fallback to static


class McpManager:
    """
    Unified manager for MCP tool discovery supporting multiple modes.
    """

    def __init__(
        self,
        default_mode: DiscoveryMode = DiscoveryMode.DYNAMIC,
        discovery_service: Optional[McpDiscoveryService] = None
    ):
        self.default_mode = default_mode
        self.discovery_service = discovery_service or get_discovery_service()
        self._static_fallback_enabled = True

    async def discover_server_tools(
        self,
        server_name: str,
        connection_config: Optional[McpConnectionConfig] = None,
        alita_client=None,
        mode: Optional[DiscoveryMode] = None,
        **kwargs
    ) -> List[McpToolMetadata]:
        """
        Discover tools from an MCP server using the specified mode.

        Args:
            server_name: Name of the MCP server
            connection_config: Connection configuration (required for dynamic mode)
            alita_client: Alita client (required for static mode)
            mode: Discovery mode to use (defaults to manager's default)
            **kwargs: Additional options

        Returns:
            List of discovered tool metadata
        """
        discovery_mode = mode or self.default_mode

        if discovery_mode == DiscoveryMode.DYNAMIC:
            return await self._discover_dynamic(server_name, connection_config)

        elif discovery_mode == DiscoveryMode.STATIC:
            return await self._discover_static(server_name, alita_client)

        elif discovery_mode == DiscoveryMode.HYBRID:
            return await self._discover_hybrid(server_name, connection_config, alita_client)

        else:
            raise ValueError(f"Unknown discovery mode: {discovery_mode}")

    async def _discover_dynamic(
        self,
        server_name: str,
        connection_config: Optional[McpConnectionConfig]
    ) -> List[McpToolMetadata]:
        """Discover tools using dynamic MCP protocol."""
        if not connection_config:
            raise ValueError("Connection configuration required for dynamic discovery")

        try:
            # Ensure discovery service is started
            await self.discovery_service.start()

            # Register and discover
            await self.discovery_service.register_server(server_name, connection_config)
            tools = await self.discovery_service.get_server_tools(server_name)

            logger.info(f"Dynamic discovery found {len(tools)} tools from {server_name}")
            return tools

        except Exception as e:
            logger.error(f"Dynamic discovery failed for {server_name}: {e}")
            raise

    async def _discover_static(
        self,
        server_name: str,
        alita_client
    ) -> List[McpToolMetadata]:
        """Discover tools using static registry."""
        if not alita_client or not hasattr(alita_client, 'get_mcp_toolkits'):
            raise ValueError("Alita client with get_mcp_toolkits() required for static discovery")

        try:
            # Use existing registry approach
            all_toolkits = alita_client.get_mcp_toolkits()
            server_toolkit = next((tk for tk in all_toolkits if tk.get('name') == server_name), None)

            if not server_toolkit:
                logger.warning(f"Static registry: Server {server_name} not found")
                return []

            # Convert to metadata format
            tools = []
            for tool_info in server_toolkit.get('tools', []):
                metadata = McpToolMetadata(
                    name=tool_info.get('name', ''),
                    description=tool_info.get('description', ''),
                    server=server_name,
                    input_schema=tool_info.get('inputSchema', {}),
                    enabled=True
                )
                tools.append(metadata)

            logger.info(f"Static discovery found {len(tools)} tools from {server_name}")
            return tools

        except Exception as e:
            logger.error(f"Static discovery failed for {server_name}: {e}")
            raise

    async def _discover_hybrid(
        self,
        server_name: str,
        connection_config: Optional[McpConnectionConfig],
        alita_client
    ) -> List[McpToolMetadata]:
        """Discover tools using hybrid approach (dynamic first, static fallback)."""

        # Try dynamic discovery first
        if connection_config:
            try:
                return await self._discover_dynamic(server_name, connection_config)
            except Exception as e:
                logger.warning(f"Dynamic discovery failed for {server_name}, trying static: {e}")

        # Fallback to static discovery
        if self._static_fallback_enabled and alita_client:
            try:
                return await self._discover_static(server_name, alita_client)
            except Exception as e:
                logger.error(f"Static fallback also failed for {server_name}: {e}")

        logger.error(f"All discovery methods failed for {server_name}")
        return []

    async def get_server_health(
        self,
        server_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get health information for servers."""
        try:
            if server_name:
                # Get specific server health from discovery service
                all_health = self.discovery_service.get_server_health()
                return all_health.get(server_name, {"status": "unknown"})
            else:
                # Get all server health
                return self.discovery_service.get_server_health()
        except Exception as e:
            logger.error(f"Failed to get server health: {e}")
            return {"status": "error", "error": str(e)}

    async def refresh_server(self, server_name: str):
        """Force refresh a specific server's tools."""
        try:
            await self.discovery_service.refresh_server(server_name)
        except Exception as e:
            logger.error(f"Failed to refresh server {server_name}: {e}")

    async def start(self):
        """Start the MCP manager."""
        await self.discovery_service.start()

    async def stop(self):
        """Stop the MCP manager."""
        await self.discovery_service.stop()

    def set_static_fallback(self, enabled: bool):
        """Enable or disable static fallback in hybrid mode."""
        self._static_fallback_enabled = enabled


# Global manager instance
_mcp_manager: Optional[McpManager] = None


def get_mcp_manager(mode: DiscoveryMode = DiscoveryMode.HYBRID) -> McpManager:
    """Get the global MCP manager instance."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = McpManager(default_mode=mode)
    return _mcp_manager


async def discover_mcp_tools(
    server_name: str,
    connection_config: Optional[McpConnectionConfig] = None,
    alita_client=None,
    mode: Optional[DiscoveryMode] = None
) -> List[McpToolMetadata]:
    """
    Convenience function for discovering MCP tools.

    Args:
        server_name: Name of the MCP server
        connection_config: Connection config (for dynamic discovery)
        alita_client: Alita client (for static discovery)
        mode: Discovery mode (defaults to HYBRID)

    Returns:
        List of discovered tool metadata
    """
    manager = get_mcp_manager()
    return await manager.discover_server_tools(
        server_name=server_name,
        connection_config=connection_config,
        alita_client=alita_client,
        mode=mode or DiscoveryMode.HYBRID
    )


async def init_mcp_manager(mode: DiscoveryMode = DiscoveryMode.HYBRID):
    """Initialize the global MCP manager."""
    manager = get_mcp_manager(mode)
    await manager.start()


async def shutdown_mcp_manager():
    """Shutdown the global MCP manager."""
    global _mcp_manager
    if _mcp_manager:
        await _mcp_manager.stop()
        _mcp_manager = None


# Configuration helpers
def create_discovery_config(
    mode: str = "hybrid",
    discovery_interval: int = 300,
    enable_static_fallback: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """Create a discovery configuration dictionary."""
    return {
        "discovery_mode": mode,
        "discovery_interval": discovery_interval,
        "enable_static_fallback": enable_static_fallback,
        **kwargs
    }