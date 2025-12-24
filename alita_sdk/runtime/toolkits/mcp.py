"""
MCP (Model Context Protocol) Toolkit for Alita SDK.
This toolkit enables connection to a single remote MCP server and exposes its tools.
Following MCP specification: https://modelcontextprotocol.io/specification/2025-06-18
"""

import logging
import re
import asyncio
from typing import List, Optional, Any, Dict, Literal, ClassVar, Union

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..tools.mcp_server_tool import McpServerTool
from ..tools.mcp_remote_tool import McpRemoteTool
from ..tools.mcp_inspect_tool import McpInspectTool
from ..models.mcp_models import McpConnectionConfig
from ..utils.mcp_client import McpClient
from ..utils.mcp_oauth import (
    McpAuthorizationRequired,
    canonical_resource,
    extract_resource_metadata_url,
    fetch_resource_metadata,
    infer_authorization_servers_from_realm,
)

logger = logging.getLogger(__name__)

name = "mcp"

def safe_int(value, default):
    """Convert value to int, handling string inputs."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid integer value '{value}', using default {default}")
        return default

class McpToolkit(BaseToolkit):
    """
    MCP Toolkit for connecting to a single remote MCP server and exposing its tools.
    Each toolkit instance represents one MCP server connection.
    """

    tools: List[BaseTool] = []
    toolkit_name: Optional[str] = None

    def __getstate__(self):
        """Custom serialization for pickle compatibility."""
        state = self.__dict__.copy()
        # The tools list should already be pickle-safe due to individual tool fixes
        # Just return the state as-is since tools handle their own serialization
        return state

    def __setstate__(self, state):
        """Custom deserialization for pickle compatibility."""
        # Initialize Pydantic internal attributes if needed
        if '__pydantic_fields_set__' not in state:
            state['__pydantic_fields_set__'] = set(state.keys())
        if '__pydantic_extra__' not in state:
            state['__pydantic_extra__'] = None
        if '__pydantic_private__' not in state:
            state['__pydantic_private__'] = None

        # Update object state
        self.__dict__.update(state)

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        """
        Generate the configuration schema for MCP toolkit.
        Following MCP specification for connection parameters.
        """
        from pydantic import create_model

        return create_model(
            'mcp',
            url=(
                str,
                Field(
                    description="MCP server HTTP URL",
                    json_schema_extra={
                        'tooltip': 'HTTP URL for the MCP server (http:// or https://)',
                        'example': 'https://your-mcp-server.com/mcp'
                    }
                )
            ),
            headers=(
                Optional[Dict[str, str]],
                Field(
                    default=None,
                    description="HTTP headers for authentication and configuration",
                    json_schema_extra={
                        'tooltip': 'HTTP headers to send with requests (e.g. Authorization)',
                        'example': {'Authorization': 'Bearer your-api-token'}
                    }
                )
            ),
            client_id=(
                Optional[str],
                Field(
                    default=None,
                    description="OAuth Client ID (if applicable)"
                )
            ),
            client_secret=(
                Optional[SecretStr],
                Field(
                    default=None,
                    description="OAuth Client Secret (if applicable)"
                )
            ),
            scopes=(
                Optional[List[str]],
                Field(
                    default=None,
                    description="OAuth Scopes (if applicable)"
                )
            ),
            timeout=(
                Union[int, str], # TODO: remove one I will figure out why UI sends str
                Field(
                    default=300,
                    description="Request timeout in seconds (1-3600)"
                )
            ),
            selected_tools=(
                List[str],
                Field(
                    default=[],
                    description="Specific tools to enable (empty = all tools)",
                    json_schema_extra={
                        'tooltip': 'Leave empty to enable all tools from the MCP server'
                    }
                )
            ),
            enable_caching=(
                bool,
                Field(
                    default=True,
                    description="Enable caching of tool schemas and responses"
                )
            ),
            cache_ttl=(
                Union[int, str],
                Field(
                    default=300,
                    description="Cache TTL in seconds (60-3600)"
                )
            ),
            __config__=ConfigDict(
                json_schema_extra={
                    'metadata': {
                        "label": "Remote MCP",
                        "icon_url": None,
                        "categories": ["other"],
                        "extra_categories": ["remote tools", "sse", "http"],
                        "description": "Connect to a remote Model Context Protocol (MCP) server via HTTP to access tools"
                    }
                }
            )
        )

    @classmethod
    def get_toolkit(
        cls,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 60,
        selected_tools: List[str] = None,
        enable_caching: bool = True,
        cache_ttl: int = 300,
        toolkit_name: str = None,
        client = None,
        **kwargs
    ) -> 'McpToolkit':
        """
        Create an MCP toolkit instance for a single MCP server.

        When valid connection configuration (url + headers) is provided, the toolkit will:
        1. Immediately perform live discovery from the MCP server
        2. Create BaseTool instances for all discovered tools with complete schemas
        3. Include an inspection tool for server exploration
        4. Return all tools via get_tools() method

        Args:
            url: MCP server HTTP URL
            headers: HTTP headers for authentication
            timeout: Request timeout in seconds
            selected_tools: List of specific tools to enable (empty = all tools)
            enable_caching: Whether to enable caching
            cache_ttl: Cache TTL in seconds
            toolkit_name: Toolkit name/identifier and prefix for tools
            client: Alita client for MCP communication
            **kwargs: Additional configuration options

        Returns:
            Configured McpToolkit instance with all available tools discovered
        """
        if selected_tools is None:
            selected_tools = []
        
        if not toolkit_name:
            raise ValueError("toolkit_name is required")

        # Convert numeric parameters that may come as strings from UI
        timeout = safe_int(timeout, 60)
        cache_ttl = safe_int(cache_ttl, 300)

        logger.info(f"Creating MCP toolkit: {toolkit_name}")

        # Parse headers if they're provided as a JSON string
        parsed_headers = headers
        if isinstance(headers, str) and headers.strip():
            try:
                import json
                logger.debug(f"Raw headers string length: {len(headers)} chars")
                logger.debug(f"Raw headers string (first 100 chars): {headers[:100]}")
                logger.debug(f"Raw headers string (last 100 chars): {headers[-100:]}")
                parsed_headers = json.loads(headers)
                logger.info(f"Parsed headers from JSON string successfully")
                logger.debug(f"Parsed headers: {parsed_headers}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse headers JSON: {e}")
                logger.error(f"Headers string length: {len(headers)}")
                logger.error(f"Headers string content: {repr(headers)}")
                raise ValueError(f"Invalid headers JSON format: {e}")
        elif headers is not None and not isinstance(headers, dict):
            logger.error(f"Headers must be a dictionary or JSON string, got: {type(headers)}")
            raise ValueError(f"Headers must be a dictionary or JSON string, got: {type(headers)}")

        # Extract session_id from kwargs if provided
        session_id = kwargs.get('session_id')
        if session_id:
            logger.info(f"[MCP Session] Using provided session ID for toolkit '{toolkit_name}': {session_id}")
        
        # Create MCP connection configuration
        try:
            connection_config = McpConnectionConfig(url=url, headers=parsed_headers, session_id=session_id)
        except Exception as e:
            logger.error(f"Invalid MCP connection configuration: {e}")
            raise ValueError(f"Invalid MCP connection configuration: {e}")

        # Create toolkit instance
        toolkit = cls(toolkit_name=toolkit_name)

        # Generate tools from the MCP server
        toolkit.tools = cls._create_tools_from_server(
            toolkit_name=toolkit_name,
            connection_config=connection_config,
            timeout=timeout,
            selected_tools=selected_tools,
            client=client
        )

        return toolkit

    @classmethod
    def _create_tools_from_server(
        cls,
        toolkit_name: str,
        connection_config: McpConnectionConfig,
        timeout: int,
        selected_tools: List[str],
        client
    ) -> List[BaseTool]:
        """
        Create tools from a single MCP server. Always performs live discovery when connection config is provided.
        """
        tools = []

        # First, try direct HTTP discovery since we have valid connection config
        try:
            logger.info(f"Discovering tools from MCP toolkit '{toolkit_name}' at {connection_config.url}")

            # Use synchronous HTTP discovery for toolkit initialization
            tool_metadata_list, session_id = cls._discover_tools_sync(
                toolkit_name=toolkit_name,
                connection_config=connection_config,
                timeout=timeout
            )

            # Filter tools if specific ones are selected
            selected_tools_lower = [tool.lower() for tool in selected_tools] if selected_tools else []
            if selected_tools_lower:
                tool_metadata_list = [
                    tool for tool in tool_metadata_list
                    if tool.get('name', '').lower() in selected_tools_lower
                ]

            # Create BaseTool instances from discovered metadata
            # Use session_id from frontend (passed via connection_config)
            if session_id:
                logger.info(f"[MCP Session] Using session_id from frontend: {session_id}")
            
            for tool_metadata in tool_metadata_list:
                server_tool = cls._create_tool_from_dict(
                    tool_dict=tool_metadata,
                    toolkit_name=toolkit_name,
                    connection_config=connection_config,
                    timeout=timeout,
                    client=client,
                    session_id=session_id  # Use session from discovery
                )

                if server_tool:
                    tools.append(server_tool)

            logger.info(f"Successfully created {len(tools)} MCP tools from toolkit '{toolkit_name}' via direct discovery")

        except McpAuthorizationRequired:
            # Authorization is required; surface upstream so the caller can prompt the user
            logger.info(f"MCP toolkit '{toolkit_name}' requires OAuth authorization")
            raise
        except Exception as e:
            logger.error(f"Direct discovery failed for MCP toolkit '{toolkit_name}': {e}", exc_info=True)
            logger.error(f"Discovery error details - URL: {connection_config.url}, Timeout: {timeout}s")
            
            # For new MCP toolkits (no client), don't silently return empty - surface the error
            # This helps users understand why tool discovery failed
            if not client:
                logger.warning(f"No fallback available for toolkit '{toolkit_name}' - re-raising discovery error")
                raise
            
            # Only fall back to static discovery for existing toolkits with a client
            logger.info(f"Falling back to static discovery for toolkit '{toolkit_name}'")
            tools = cls._create_tools_static(toolkit_name, selected_tools, timeout, client)

        # Don't add inspection tool to agent - it's only for internal use by toolkit
        # inspection_tool = cls._create_inspection_tool(
        #     toolkit_name=toolkit_name,
        #     connection_config=connection_config
        # )
        # if inspection_tool:
        #     tools.append(inspection_tool)
        #     logger.info(f"Added MCP inspection tool for toolkit '{toolkit_name}'")

        # Log final tool count before returning
        logger.info(f"MCP toolkit '{toolkit_name}' will provide {len(tools)} tools to agent")
        if len(tools) == 0:
            logger.warning(f"MCP toolkit '{toolkit_name}' has no tools - discovery may have failed")

        return tools

    @classmethod
    def _discover_tools_sync(
        cls,
        toolkit_name: str,
        connection_config: McpConnectionConfig,
        timeout: int
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Discover tools and prompts from MCP server using SSE client.
        
        Returns:
            Tuple of (tool_list, server_session_id) - session_id may be server-provided
        """
        initial_session_id = connection_config.session_id
        
        if not initial_session_id:
            logger.warning(f"[MCP Session] No session_id provided for '{toolkit_name}' - will generate one")
        
        # Run async discovery in sync context
        try:
            all_tools, server_session_id = asyncio.run(
                cls._discover_tools_async(
                    toolkit_name=toolkit_name,
                    connection_config=connection_config,
                    timeout=timeout
                )
            )
            # Return tools and the session_id (server-provided or generated)
            logger.info(f"[MCP Session] Final session_id for '{toolkit_name}': {server_session_id}")
            return all_tools, server_session_id
        except McpAuthorizationRequired:
            # Re-raise auth required exceptions directly
            logger.info(f"[MCP SSE] Authorization required for '{toolkit_name}'")
            raise
        except Exception as e:
            logger.error(f"[MCP SSE] Discovery failed for '{toolkit_name}': {e}")
            raise
    
    @classmethod
    async def _discover_tools_async(
        cls,
        toolkit_name: str,
        connection_config: McpConnectionConfig,
        timeout: int
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Async implementation of tool discovery using SSE client.
        
        Returns:
            Tuple of (tool_list, server_session_id)
        """
        all_tools = []
        session_id = connection_config.session_id
        
        # Generate temporary session_id if not provided (for OAuth flow)
        # The real session_id should come from frontend after OAuth completes
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            logger.info(f"[MCP SSE] Generated temporary session_id for OAuth: {session_id}")
        
        logger.info(f"[MCP] Discovering from {connection_config.url} with session {session_id}")
        
        # Prepare headers
        headers = {}
        if connection_config.headers:
            headers.update(connection_config.headers)
        
        # Create unified MCP client (auto-detects SSE vs Streamable HTTP)
        client = McpClient(
            url=connection_config.url,
            session_id=session_id,
            headers=headers,
            timeout=timeout
        )
        
        server_session_id = None
        async with client:
            # Initialize MCP session
            await client.initialize()
            logger.info(f"[MCP] Session initialized for '{toolkit_name}' (transport={client.detected_transport})")
            
            # Capture server-provided session_id (from mcp-session-id header)
            server_session_id = client.server_session_id
            if server_session_id:
                logger.info(f"[MCP] Server provided session_id: {server_session_id}")
            
            # Discover tools
            tools = await client.list_tools()
            all_tools.extend(tools)
            logger.info(f"[MCP] Discovered {len(tools)} tools from '{toolkit_name}'")
            
            # Discover prompts
            try:
                prompts = await client.list_prompts()
                # Convert prompts to tool format
                for prompt in prompts:
                    prompt_tool = {
                        "name": f"prompt_{prompt.get('name', 'unnamed')}",
                        "description": prompt.get('description', f"Execute prompt: {prompt.get('name')}"),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "arguments": {
                                    "type": "object",
                                    "description": "Arguments for the prompt template",
                                    "properties": {
                                        arg.get("name"): {
                                            "type": "string",
                                            "description": arg.get("description", ""),
                                            "required": arg.get("required", False)
                                        }
                                        for arg in prompt.get("arguments", [])
                                    }
                                }
                            }
                        },
                        "_mcp_type": "prompt",
                        "_mcp_prompt_name": prompt.get('name')
                    }
                    all_tools.append(prompt_tool)
                logger.info(f"[MCP] Discovered {len(prompts)} prompts from '{toolkit_name}'")
            except Exception as e:
                logger.warning(f"[MCP] Failed to discover prompts: {e}")
        
        logger.info(f"[MCP] Total discovered {len(all_tools)} items from '{toolkit_name}'")
        # Return tools and server-provided session_id (use server's if available, else the one we sent)
        final_session_id = server_session_id or session_id
        return all_tools, final_session_id

    @classmethod
    def _create_tool_from_dict(
        cls,
        tool_dict: Dict[str, Any],
        toolkit_name: str,
        connection_config: McpConnectionConfig,
        timeout: int,
        client,
        session_id: Optional[str] = None
    ) -> Optional[BaseTool]:
        """Create a BaseTool from a tool/prompt dictionary (from direct HTTP discovery)."""
        try:
            # Use original tool name directly
            tool_name = tool_dict.get("name", "unknown")
            
            # Check if this is a prompt (converted to tool)
            is_prompt = tool_dict.get("_mcp_type") == "prompt"
            item_type = "prompt" if is_prompt else "tool"

            # Build description with toolkit context and ensure it doesn't exceed 1000 characters
            base_description = tool_dict.get('description', '')
            description = f"{base_description}\nToolkit: {toolkit_name} ({connection_config.url})"
            if len(description) > 1000:
                description = description[:997] + "..."
                logger.debug(f"Trimmed description for tool '{tool_name}' to 1000 chars")

            # Use McpRemoteTool for remote MCP servers (HTTP/SSE)
            return McpRemoteTool(
                name=tool_name,
                description=description,
                args_schema=McpServerTool.create_pydantic_model_from_schema(
                    tool_dict.get("inputSchema", {})
                ),
                client=client,
                server=toolkit_name,
                server_url=connection_config.url,
                server_headers=connection_config.headers,
                tool_timeout_sec=timeout,
                is_prompt=is_prompt,
                prompt_name=tool_dict.get("_mcp_prompt_name") if is_prompt else None,
                original_tool_name=tool_name,  # Store original name for MCP server invocation
                session_id=session_id  # Pass session ID for stateful SSE servers
            )
        except Exception as e:
            logger.error(f"Failed to create MCP tool '{tool_name}' from toolkit '{toolkit_name}': {e}")
            return None

    @classmethod
    def _create_tools_static(
        cls,
        toolkit_name: str,
        selected_tools: List[str],
        timeout: int,
        client
    ) -> List[BaseTool]:
        """Fallback static tool creation using the original method."""
        tools = []

        if not client or not hasattr(client, 'get_mcp_toolkits'):
            logger.warning("Alita client does not support MCP toolkit discovery")
            return tools

        try:
            all_toolkits = client.get_mcp_toolkits()
            server_toolkit = next((tk for tk in all_toolkits if tk.get('name') == toolkit_name), None)

            if not server_toolkit:
                logger.warning(f"MCP toolkit '{toolkit_name}' not found in available toolkits")
                return tools

            # Extract tools from the toolkit
            available_tools = server_toolkit.get('tools', [])
            selected_tools_lower = [tool.lower() for tool in selected_tools] if selected_tools else []

            for available_tool in available_tools:
                tool_name = available_tool.get("name", "").lower()

                # Filter tools if specific tools are selected
                if selected_tools_lower and tool_name not in selected_tools_lower:
                    continue

                # Create the tool
                server_tool = cls._create_single_tool(
                    toolkit_name=toolkit_name,
                    available_tool=available_tool,
                    timeout=timeout,
                    client=client
                )

                if server_tool:
                    tools.append(server_tool)

            logger.info(f"Successfully created {len(tools)} MCP tools from toolkit '{toolkit_name}' using static mode")

        except Exception as e:
            logger.error(f"Error in static tool creation: {e}")

        # Always add the inspection tool (not subject to selected_tools filtering)
        # For static mode, we need to create a basic connection config from the server info
        try:
            # We don't have full connection config in static mode, so create a basic one
            # The inspection tool will work as long as the server is accessible
            inspection_tool = McpInspectTool(
                name="mcp_inspect",
                server_name=toolkit_name,
                server_url="",  # Will be populated by the client if available
                description=f"Inspect available tools, prompts, and resources from MCP toolkit '{toolkit_name}'"
            )
            tools.append(inspection_tool)
            logger.info(f"Added MCP inspection tool for toolkit '{toolkit_name}' (static mode)")
        except Exception as e:
            logger.warning(f"Failed to create inspection tool for {toolkit_name}: {e}")

        return tools

    @classmethod
    def _create_tool_from_metadata(
        cls,
        tool_metadata,
        toolkit_name: str,
        timeout: int,
        client
    ) -> Optional[BaseTool]:
        """Create a BaseTool from discovered metadata."""
        try:
            # Use original tool name directly
            tool_name = tool_metadata.name

            # Build description with toolkit context and ensure it doesn't exceed 1000 characters
            description = f"{tool_metadata.description}\nToolkit: {toolkit_name}"
            if len(description) > 1000:
                description = description[:997] + "..."
                logger.debug(f"Trimmed description for tool '{tool_name}' to 1000 chars")

            return McpServerTool(
                name=tool_name,
                description=description,
                args_schema=McpServerTool.create_pydantic_model_from_schema(tool_metadata.input_schema),
                client=client,
                server=tool_metadata.server,
                tool_timeout_sec=timeout,
                metadata={"toolkit_name": toolkit_name, "toolkit_type": name}
            )
        except Exception as e:
            logger.error(f"Failed to create MCP tool '{tool_name}' from server '{tool_metadata.server}': {e}")
            return None

    @classmethod
    def _create_single_tool(
        cls,
        toolkit_name: str,
        available_tool: Dict[str, Any],
        timeout: int,
        client
    ) -> Optional[BaseTool]:
        """Create a single MCP tool."""
        try:
            # Use original tool name directly
            tool_name = available_tool["name"]

            # Build description with toolkit context and ensure it doesn't exceed 1000 characters
            base_description = available_tool.get('description', '')
            description = f"{base_description}\nToolkit: {toolkit_name}"
            if len(description) > 1000:
                description = description[:997] + "..."
                logger.debug(f"Trimmed description for tool '{tool_name}' to 1000 chars")

            return McpServerTool(
                name=tool_name,
                description=description,
                args_schema=McpServerTool.create_pydantic_model_from_schema(
                    available_tool.get("inputSchema", {})
                ),
                client=client,
                server=toolkit_name,
                tool_timeout_sec=timeout,
                metadata={"toolkit_name": toolkit_name, "toolkit_type": name}
            )
        except Exception as e:
            logger.error(f"Failed to create MCP tool '{tool_name}' from toolkit '{toolkit_name}': {e}")
            return None

    @classmethod
    def _create_inspection_tool(
        cls,
        toolkit_name: str,
        connection_config: McpConnectionConfig
    ) -> Optional[BaseTool]:
        """Create the inspection tool for the MCP toolkit."""
        try:
            return McpInspectTool(
                name="mcp_inspect",
                server_name=toolkit_name,
                server_url=connection_config.url,
                server_headers=connection_config.headers,
                description=f"Inspect available tools, prompts, and resources from MCP toolkit '{toolkit_name}'"
            )
        except Exception as e:
            logger.error(f"Failed to create MCP inspection tool for toolkit '{toolkit_name}': {e}")
            return None

    def get_tools(self) -> List[BaseTool]:
        """Get the list of tools provided by this toolkit."""
        logger.info(f"MCP toolkit '{self.toolkit_name}' returning {len(self.tools)} tools")
        if len(self.tools) > 0:
            tool_names = [t.name if hasattr(t, 'name') else str(t) for t in self.tools]
            logger.info(f"MCP toolkit '{self.toolkit_name}' tools: {tool_names}")
        return self.tools

    async def refresh_tools(self):
        """Manually refresh tools from the MCP toolkit."""
        if not self.toolkit_name:
            logger.warning("Cannot refresh tools: toolkit_name not set")
            return

        try:
            from ..clients.mcp_manager import get_mcp_manager
            manager = get_mcp_manager()
            await manager.refresh_server(self.toolkit_name)
            logger.info(f"Successfully refreshed tools for toolkit {self.toolkit_name}")
        except Exception as e:
            logger.error(f"Failed to refresh tools for toolkit {self.toolkit_name}: {e}")

    async def get_server_health(self) -> Dict[str, Any]:
        """Get health status of the configured MCP toolkit."""
        if not self.toolkit_name:
            return {"status": "not_configured"}

        try:
            from ..clients.mcp_manager import get_mcp_manager
            manager = get_mcp_manager()
            health_info = await manager.get_server_health(self.toolkit_name)
            return health_info
        except Exception as e:
            logger.error(f"Failed to get server health for {self.toolkit_name}: {e}")
            return {"status": "error", "error": str(e)}


def get_tools(tool_config: dict, alita_client, llm=None, memory_store=None) -> List[BaseTool]:
    """
    Create MCP tools from configuration.
    This function is called by the main tool loading system.

    Args:
        tool_config: Tool configuration dictionary
        alita_client: Alita client instance
        llm: Language model (not used by MCP tools)
        memory_store: Memory store (not used by MCP tools)

    Returns:
        List of configured MCP tools
    """
    settings = tool_config.get('settings', {})
    toolkit_name = tool_config.get('toolkit_name')

    # Extract required fields
    url = settings.get('url')
    headers = settings.get('headers')

    if not toolkit_name:
        logger.error("MCP toolkit configuration missing required 'toolkit_name'")
        return []

    if not url:
        logger.error("MCP toolkit configuration missing required 'url'")
        return []

    # Type conversion for numeric settings that may come as strings from config
    return McpToolkit.get_toolkit(
        url=url,
        headers=headers,
        timeout=safe_int(settings.get('timeout'), 60),
        selected_tools=settings.get('selected_tools', []),
        enable_caching=settings.get('enable_caching', True),
        cache_ttl=safe_int(settings.get('cache_ttl'), 300),
        toolkit_name=toolkit_name,
        client=alita_client
    ).get_tools()


# Utility functions for managing MCP discovery
async def start_global_discovery():
    """Start the global MCP discovery service."""
    from ..clients.mcp_discovery import init_discovery_service
    await init_discovery_service()


async def stop_global_discovery():
    """Stop the global MCP discovery service."""
    from ..clients.mcp_discovery import shutdown_discovery_service
    await shutdown_discovery_service()


async def register_mcp_server_for_discovery(toolkit_name: str, connection_config):
    """Register an MCP server for global discovery."""
    from ..clients.mcp_discovery import get_discovery_service
    service = get_discovery_service()
    await service.register_server(toolkit_name, connection_config)


def get_all_discovered_servers():
    """Get status of all discovered servers."""
    from ..clients.mcp_discovery import get_discovery_service
    service = get_discovery_service()
    return service.get_server_health()
