"""
MCP (Model Context Protocol) Toolkit for Alita SDK.
This toolkit enables connection to a single remote MCP server and exposes its tools.
Following MCP specification: https://modelcontextprotocol.io/specification/2025-06-18
"""

import logging
import requests
from typing import List, Optional, Any, Dict, Literal, ClassVar

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, ConfigDict, Field

from ..tools.mcp_server_tool import McpServerTool
from ..tools.mcp_inspect_tool import McpInspectTool
from ...tools.utils import TOOLKIT_SPLITTER, clean_string
from ..models.mcp_models import McpConnectionConfig

logger = logging.getLogger(__name__)

name = "mcp"


class McpToolkit(BaseToolkit):
    """
    MCP Toolkit for connecting to a single remote MCP server and exposing its tools.
    Each toolkit instance represents one MCP server connection.
    """

    tools: List[BaseTool] = []
    toolkit_name: Optional[str] = None

    # Class variable (not Pydantic field) for tool name length limit
    toolkit_max_length: ClassVar[int] = 0  # No limit for MCP tool names

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
            timeout=(
                int,
                Field(
                    default=60,
                    ge=1, le=300,
                    description="Request timeout in seconds"
                )
            ),
            discovery_mode=(
                Literal['static', 'dynamic', 'hybrid'],
                Field(
                    default="dynamic",
                    description="Discovery mode",
                    json_schema_extra={
                        'tooltip': 'static: use registry, dynamic: live discovery, hybrid: try dynamic first'
                    }
                )
            ),
            discovery_interval=(
                int,
                Field(
                    default=300,
                    ge=60, le=3600,
                    description="Discovery interval in seconds (for periodic discovery)"
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
                int,
                Field(
                    default=300,
                    ge=60, le=3600,
                    description="Cache TTL in seconds"
                )
            ),
            __config__=ConfigDict(
                json_schema_extra={
                    'metadata': {
                        "label": "Remove MCP",
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
        discovery_mode: str = "hybrid",
        discovery_interval: int = 300,
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
            discovery_mode: Discovery mode ('static', 'dynamic', 'hybrid')
            discovery_interval: Discovery interval in seconds (for periodic discovery)
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

        # Create MCP connection configuration
        try:
            connection_config = McpConnectionConfig(url=url, headers=parsed_headers)
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
            client=client,
            discovery_mode=discovery_mode
        )

        return toolkit

    @classmethod
    def _create_tools_from_server(
        cls,
        toolkit_name: str,
        connection_config: McpConnectionConfig,
        timeout: int,
        selected_tools: List[str],
        client,
        discovery_mode: str = "dynamic"
    ) -> List[BaseTool]:
        """
        Create tools from a single MCP server. Always performs live discovery when connection config is provided.
        """
        tools = []

        # First, try direct HTTP discovery since we have valid connection config
        try:
            logger.info(f"Discovering tools from MCP toolkit '{toolkit_name}' at {connection_config.url}")

            # Use synchronous HTTP discovery for toolkit initialization
            tool_metadata_list = cls._discover_tools_sync(
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
            for tool_metadata in tool_metadata_list:
                server_tool = cls._create_tool_from_dict(
                    tool_dict=tool_metadata,
                    toolkit_name=toolkit_name,
                    timeout=timeout,
                    client=client
                )

                if server_tool:
                    tools.append(server_tool)

            logger.info(f"Successfully created {len(tools)} MCP tools from toolkit '{toolkit_name}' via direct discovery")

        except Exception as e:
            logger.error(f"Direct discovery failed for MCP toolkit '{toolkit_name}': {e}")

            # Fallback to static mode if available and not already static
            if client and discovery_mode != "static":
                logger.info(f"Falling back to static discovery for toolkit '{toolkit_name}'")
                tools = cls._create_tools_static(toolkit_name, selected_tools, timeout, client)
            else:
                logger.warning(f"No fallback available for toolkit '{toolkit_name}' - returning empty tools list")

        # Always add the inspection tool (not subject to selected_tools filtering)
        inspection_tool = cls._create_inspection_tool(
            toolkit_name=toolkit_name,
            connection_config=connection_config
        )
        if inspection_tool:
            tools.append(inspection_tool)
            logger.info(f"Added MCP inspection tool for toolkit '{toolkit_name}'")

        return tools

    @classmethod
    def _discover_tools_sync(
        cls,
        toolkit_name: str,
        connection_config: McpConnectionConfig,
        timeout: int
    ) -> List[Dict[str, Any]]:
        """
        Synchronously discover tools from MCP server using HTTP requests.
        Returns list of tool dictionaries with name, description, and inputSchema.
        """
        import time

        # MCP protocol: list_tools request
        mcp_request = {
            "jsonrpc": "2.0",
            "id": f"discover_{int(time.time())}",
            "method": "tools/list",
            "params": {}
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if connection_config.headers:
            headers.update(connection_config.headers)

        try:
            response = requests.post(
                connection_config.url,
                json=mcp_request,
                headers=headers,
                timeout=timeout
            )

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

            # Check content type and parse accordingly
            content_type = response.headers.get('Content-Type', '')
            
            if 'text/event-stream' in content_type:
                # Parse SSE (Server-Sent Events) format
                data = cls._parse_sse_response(response.text)
            elif 'application/json' in content_type:
                # Parse regular JSON
                try:
                    data = response.json()
                except ValueError as json_err:
                    raise Exception(f"Invalid JSON response: {json_err}. Response text: {response.text[:200]}")
            else:
                raise Exception(f"Unexpected Content-Type: {content_type}. Response: {response.text[:200]}")

            if "error" in data:
                raise Exception(f"MCP Error: {data['error']}")

            # Parse MCP response and extract tools
            tools_data = data.get("result", {}).get("tools", [])
            logger.info(f"Discovered {len(tools_data)} tools from MCP toolkit '{toolkit_name}'")

            return tools_data

        except Exception as e:
            logger.error(f"Failed to discover tools from MCP toolkit '{toolkit_name}': {e}")
            raise

    @staticmethod
    def _parse_sse_response(sse_text: str) -> Dict[str, Any]:
        """
        Parse Server-Sent Events (SSE) format response.
        SSE format: event: message\ndata: {json}\n\n
        """
        import json
        
        lines = sse_text.strip().split('\n')
        data_line = None
        
        for line in lines:
            if line.startswith('data:'):
                data_line = line[5:].strip()  # Remove 'data:' prefix
                break
        
        if not data_line:
            raise Exception(f"No data found in SSE response: {sse_text[:200]}")
        
        try:
            return json.loads(data_line)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse SSE data as JSON: {e}. Data: {data_line[:200]}")

    @classmethod
    def _create_tool_from_dict(
        cls,
        tool_dict: Dict[str, Any],
        toolkit_name: str,
        timeout: int,
        client
    ) -> Optional[BaseTool]:
        """Create a BaseTool from a tool dictionary (from direct HTTP discovery)."""
        try:
            # Store toolkit_max_length in local variable to avoid contextual access issues
            max_length_value = cls.toolkit_max_length

            # Clean toolkit name for prefixing
            clean_prefix = clean_string(toolkit_name, max_length_value)

            full_tool_name = f'{clean_prefix}{TOOLKIT_SPLITTER}{tool_dict.get("name", "unknown")}'

            return McpServerTool(
                name=full_tool_name,
                description=f"MCP tool '{tool_dict.get('name')}' from toolkit '{toolkit_name}': {tool_dict.get('description', '')}",
                args_schema=McpServerTool.create_pydantic_model_from_schema(
                    tool_dict.get("inputSchema", {})
                ),
                client=client,
                server=toolkit_name,
                tool_timeout_sec=timeout
            )
        except Exception as e:
            logger.error(f"Failed to create MCP tool '{tool_dict.get('name')}' from toolkit '{toolkit_name}': {e}")
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
                name=f"{clean_string(toolkit_name, 50)}{TOOLKIT_SPLITTER}mcp_inspect",
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
            # Store toolkit_max_length in local variable to avoid contextual access issues
            max_length_value = cls.toolkit_max_length

            # Clean server name for prefixing (use tool_metadata.server instead of toolkit_name)
            clean_prefix = clean_string(tool_metadata.server, max_length_value)
            full_tool_name = f'{clean_prefix}{TOOLKIT_SPLITTER}{tool_metadata.name}'

            return McpServerTool(
                name=full_tool_name,
                description=f"MCP tool '{tool_metadata.name}' from server '{tool_metadata.server}': {tool_metadata.description}",
                args_schema=McpServerTool.create_pydantic_model_from_schema(tool_metadata.input_schema),
                client=client,
                server=tool_metadata.server,
                tool_timeout_sec=timeout
            )
        except Exception as e:
            logger.error(f"Failed to create MCP tool '{tool_metadata.name}' from server '{tool_metadata.server}': {e}")
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
            # Store toolkit_max_length in local variable to avoid contextual access issues
            max_length_value = cls.toolkit_max_length

            # Clean toolkit name for prefixing
            clean_prefix = clean_string(toolkit_name, max_length_value)

            full_tool_name = f'{clean_prefix}{TOOLKIT_SPLITTER}{available_tool["name"]}'

            return McpServerTool(
                name=full_tool_name,
                description=f"MCP tool '{available_tool['name']}' from toolkit '{toolkit_name}': {available_tool.get('description', '')}",
                args_schema=McpServerTool.create_pydantic_model_from_schema(
                    available_tool.get("inputSchema", {})
                ),
                client=client,
                server=toolkit_name,
                tool_timeout_sec=timeout
            )
        except Exception as e:
            logger.error(f"Failed to create MCP tool '{available_tool.get('name')}' from toolkit '{toolkit_name}': {e}")
            return None

    @classmethod
    def _create_inspection_tool(
        cls,
        toolkit_name: str,
        connection_config: McpConnectionConfig
    ) -> Optional[BaseTool]:
        """Create the inspection tool for the MCP toolkit."""
        try:
            # Store toolkit_max_length in local variable to avoid contextual access issues
            max_length_value = cls.toolkit_max_length

            # Clean toolkit name for prefixing
            clean_prefix = clean_string(toolkit_name, max_length_value)

            full_tool_name = f'{clean_prefix}{TOOLKIT_SPLITTER}mcp_inspect'

            return McpInspectTool(
                name=full_tool_name,
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

    return McpToolkit.get_toolkit(
        url=url,
        headers=headers,
        timeout=settings.get('timeout', 60),
        discovery_mode=settings.get('discovery_mode', 'dynamic'),
        discovery_interval=settings.get('discovery_interval', 300),
        selected_tools=settings.get('selected_tools', []),
        enable_caching=settings.get('enable_caching', True),
        cache_ttl=settings.get('cache_ttl', 300),
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