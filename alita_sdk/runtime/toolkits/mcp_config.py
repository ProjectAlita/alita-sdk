"""
MCP Config Toolkit for Alita SDK.

This toolkit enables connection to pre-configured MCP servers defined in YAML config.
Supports both stdio (local subprocess) and http (remote) MCP servers.

Configuration is loaded from:
1. SDK config file (ALITA_MCP_SERVERS_CONFIG environment variable)
2. Direct configuration passed to get_toolkit()

Example config (mcp_servers.yml):
```yaml
mcp_servers:
  # Stdio server (local subprocess)
  playwright:
    type: stdio
    runtime: npm
    package: "@playwright/mcp@latest"
    command: npx
    args: ["@playwright/mcp@latest"]
    stateful: true
    description: "Browser automation via Playwright"

  # HTTP server (remote)
  github_copilot:
    type: http
    url: "https://api.githubcopilot.com/mcp/"
    description: "GitHub Copilot MCP"
    config_schema:
      properties:
        github_token:
          type: string
          secret: true
          required: true
    headers:
      Authorization: "Bearer {github_token}"
```
"""

import asyncio
import logging
import os
import re
import threading
from typing import List, Optional, Dict, Any

import yaml
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

name = "mcp_config"

# Global session manager for stdio process lifecycle
_session_manager_lock = threading.Lock()
_session_manager: Optional['McpStdioSessionManager'] = None


class McpStdioSessionManager:
    """
    Manages MCP stdio server sessions across agent executions.

    Keeps MCP server subprocesses alive for stateful servers.
    """

    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self.clients: Dict[str, Any] = {}
        self._session_contexts: Dict[str, Any] = {}
        self._lock = threading.Lock()

    async def get_or_create_session(
        self,
        server_name: str,
        server_config: Dict[str, Any]
    ) -> tuple:
        """Get existing session or create a new one."""
        with self._lock:
            if server_name in self.sessions:
                return self.sessions[server_name], self.clients[server_name]

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            raise ImportError(
                "langchain-mcp-adapters is required for stdio MCP servers. "
                "Install with: pip install langchain-mcp-adapters"
            )

        mcp_config = {
            'transport': 'stdio',
            'command': server_config['command'],
            'args': server_config.get('args', [])
        }

        env = server_config.get('env', {})
        if env:
            mcp_config['env'] = env

        logger.info(f"[MCP Config] Starting stdio server: {server_name}")

        client = MultiServerMCPClient({server_name: mcp_config})
        session_context = client.session(server_name)
        session = await session_context.__aenter__()

        with self._lock:
            self.sessions[server_name] = session
            self.clients[server_name] = client
            self._session_contexts[server_name] = session_context

        return session, client

    async def cleanup(self):
        """Cleanup all sessions."""
        with self._lock:
            for name, ctx in self._session_contexts.items():
                try:
                    await ctx.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"[MCP Config] Error cleaning up {name}: {e}")
            self.sessions.clear()
            self.clients.clear()
            self._session_contexts.clear()


def get_session_manager() -> McpStdioSessionManager:
    """Get or create the global session manager."""
    global _session_manager
    with _session_manager_lock:
        if _session_manager is None:
            _session_manager = McpStdioSessionManager()
        return _session_manager


def load_mcp_servers_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load MCP servers configuration from YAML file.

    Config is loaded from (in order of priority):
    1. Explicit config_path parameter
    2. ALITA_MCP_SERVERS_CONFIG environment variable
    3. Plugin config: /data/plugins/indexer_worker/config.yml
    4. Template config: /data/configs/indexer_worker.yml
    """
    if config_path is None:
        config_path = os.environ.get('ALITA_MCP_SERVERS_CONFIG')

    # List of paths to check in order
    paths_to_check = []
    if config_path:
        paths_to_check.append(config_path)
    else:
        # Plugin's runtime config (merged by pylon)
        paths_to_check.append('/data/plugins/indexer_worker/config.yml')
        # Template config in configs directory
        paths_to_check.append('/data/configs/indexer_worker.yml')

    for path in paths_to_check:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    config = yaml.safe_load(f)
                mcp_servers = config.get('mcp_servers', {})
                if mcp_servers:
                    logger.info(f"[MCP Config] Loaded {len(mcp_servers)} MCP servers from {path}")
                    return mcp_servers
            except Exception as e:
                logger.warning(f"[MCP Config] Failed to load config from {path}: {e}")

    logger.debug("[MCP Config] No MCP servers configuration found")
    return {}


_server_configs: Optional[Dict[str, Any]] = None


def get_mcp_server_config(server_name: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific MCP server."""
    global _server_configs
    if _server_configs is None:
        _server_configs = load_mcp_servers_config()
    return _server_configs.get(server_name)


def get_all_mcp_server_configs() -> Dict[str, Any]:
    """Get all configured MCP server definitions."""
    global _server_configs
    if _server_configs is None:
        _server_configs = load_mcp_servers_config()
    return _server_configs


def _substitute_placeholders(value: Any, user_config: Dict[str, Any]) -> Any:
    """Substitute {param} placeholders with values from user_config."""
    if isinstance(value, str):
        def replacer(match):
            key = match.group(1)
            return str(user_config.get(key, match.group(0)))
        return re.sub(r'\{(\w+)\}', replacer, value)
    elif isinstance(value, dict):
        return {k: _substitute_placeholders(v, user_config) for k, v in value.items()}
    elif isinstance(value, list):
        return [_substitute_placeholders(v, user_config) for v in value]
    return value


class McpConfigToolkit(BaseToolkit):
    """
    MCP Config Toolkit for pre-configured MCP servers.

    Supports both stdio (local subprocess) and http (remote) servers
    defined in mcp_servers.yml configuration.
    """

    tools: List[BaseTool] = []
    toolkit_name: Optional[str] = None
    server_name: Optional[str] = None
    server_type: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        """Generate the configuration schema for MCP config toolkit."""
        from pydantic import create_model

        return create_model(
            'mcp_config',
            server_name=(
                str,
                Field(
                    description="Name of the MCP server to connect to",
                    json_schema_extra={
                        'tooltip': 'Server name as defined in mcp_servers.yml config',
                        'example': 'playwright'
                    }
                )
            ),
            selected_tools=(
                Optional[List[str]],
                Field(
                    default=None,
                    description="List of specific tools to enable (empty = all tools)",
                )
            ),
            excluded_tools=(
                Optional[List[str]],
                Field(
                    default=None,
                    description="List of tools to exclude",
                )
            ),
        )

    @staticmethod
    def get_available_servers() -> List[Dict[str, Any]]:
        """Get list of available MCP servers from config."""
        servers = get_all_mcp_server_configs()
        result = []

        for name, config in servers.items():
            server_type = config.get('type', 'stdio')
            result.append({
                'name': name,
                'type': server_type,
                'description': config.get('description', f'MCP server: {name}'),
                'stateful': config.get('stateful', False),
                'config_schema': config.get('config_schema', {'properties': {}}),
            })

        return result

    @classmethod
    def get_toolkit(
        cls,
        server_name: str,
        server_config: Optional[Dict[str, Any]] = None,
        user_config: Optional[Dict[str, Any]] = None,
        selected_tools: Optional[List[str]] = None,
        excluded_tools: Optional[List[str]] = None,
        toolkit_name: Optional[str] = None,
        client=None,
        **kwargs
    ) -> 'McpConfigToolkit':
        """
        Create an MCP toolkit instance from config.

        Automatically routes to stdio or http handler based on server type.
        """
        if server_config is None:
            server_config = get_mcp_server_config(server_name)
            if server_config is None:
                raise ValueError(
                    f"MCP server '{server_name}' not found in configuration. "
                    f"Available servers: {list(get_all_mcp_server_configs().keys())}"
                )

        if user_config is None:
            user_config = {}

        server_type = server_config.get('type', 'stdio')

        if server_type == 'stdio':
            tools = cls._load_stdio_tools(
                server_name=server_name,
                server_config=server_config,
                user_config=user_config,
                selected_tools=selected_tools,
                excluded_tools=excluded_tools,
                toolkit_name=toolkit_name or server_name,
            )
        elif server_type == 'http':
            tools = cls._load_http_tools(
                server_name=server_name,
                server_config=server_config,
                user_config=user_config,
                selected_tools=selected_tools,
                excluded_tools=excluded_tools,
                toolkit_name=toolkit_name or server_name,
                client=client,
            )
        else:
            raise ValueError(f"Unknown MCP server type: {server_type}")

        return cls(
            tools=tools,
            toolkit_name=toolkit_name or server_name,
            server_name=server_name,
            server_type=server_type
        )

    @classmethod
    def _load_stdio_tools(
        cls,
        server_name: str,
        server_config: Dict[str, Any],
        user_config: Dict[str, Any],
        selected_tools: Optional[List[str]],
        excluded_tools: Optional[List[str]],
        toolkit_name: str,
    ) -> List[BaseTool]:
        """Load tools from stdio MCP server."""
        # Resolve environment variables from user config
        env = dict(server_config.get('env', {}))
        env_mapping = server_config.get('env_mapping', {})

        for env_var, config_ref in env_mapping.items():
            config_key = config_ref.strip('{}')
            if config_key in user_config:
                value = user_config[config_key]
                if isinstance(value, list):
                    value = ','.join(str(v) for v in value)
                env[env_var] = str(value)

        resolved_config = {**server_config, 'env': env}

        # Load tools asynchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            cls._load_stdio_tools_async(
                server_name=server_name,
                server_config=resolved_config,
                selected_tools=selected_tools,
                excluded_tools=excluded_tools,
                toolkit_name=toolkit_name,
            )
        )

    @classmethod
    async def _load_stdio_tools_async(
        cls,
        server_name: str,
        server_config: Dict[str, Any],
        selected_tools: Optional[List[str]],
        excluded_tools: Optional[List[str]],
        toolkit_name: str,
    ) -> List[BaseTool]:
        """Load tools from stdio MCP server asynchronously."""
        try:
            from langchain_mcp_adapters.tools import load_mcp_tools
        except ImportError:
            raise ImportError(
                "langchain-mcp-adapters is required for stdio MCP servers. "
                "Install with: pip install langchain-mcp-adapters"
            )

        session_manager = get_session_manager()
        session, client = await session_manager.get_or_create_session(
            server_name, server_config
        )

        tools = await load_mcp_tools(
            session,
            connection=client.connections[server_name],
            server_name=server_name
        )

        logger.info(f"[MCP Config] Discovered {len(tools)} tools from stdio server {server_name}")

        # Apply filtering
        if selected_tools:
            tools = [t for t in tools if t.name in selected_tools]
        if excluded_tools:
            tools = [t for t in tools if t.name not in excluded_tools]

        # Add toolkit context
        if toolkit_name:
            for tool in tools:
                if not tool.description.startswith(f"[{toolkit_name}]"):
                    tool.description = f"[{toolkit_name}] {tool.description}"

        return tools

    @classmethod
    def _load_http_tools(
        cls,
        server_name: str,
        server_config: Dict[str, Any],
        user_config: Dict[str, Any],
        selected_tools: Optional[List[str]],
        excluded_tools: Optional[List[str]],
        toolkit_name: str,
        client=None,
    ) -> List[BaseTool]:
        """Load tools from HTTP MCP server using existing McpToolkit."""
        from .mcp import McpToolkit

        # Substitute placeholders in URL and headers
        url = _substitute_placeholders(server_config.get('url', ''), user_config)
        headers = _substitute_placeholders(server_config.get('headers', {}), user_config)
        timeout = server_config.get('timeout', 60)

        logger.info(f"[MCP Config] Connecting to HTTP server {server_name} at {url}")

        # Use existing McpToolkit for HTTP servers
        mcp_toolkit = McpToolkit.get_toolkit(
            url=url,
            headers=headers,
            timeout=timeout,
            selected_tools=selected_tools or [],
            toolkit_name=toolkit_name,
            client=client,
        )

        tools = mcp_toolkit.get_tools()

        # Apply excluded_tools filter (McpToolkit only supports selected_tools)
        if excluded_tools:
            tools = [t for t in tools if t.name not in excluded_tools]

        logger.info(f"[MCP Config] Loaded {len(tools)} tools from HTTP server {server_name}")

        return tools

    def get_tools(self) -> List[BaseTool]:
        """Return all tools from this MCP server."""
        return self.tools


# Utility functions for toolkit registration

def _discover_tools_for_http_server(url: str, headers: Optional[Dict[str, Any]] = None, timeout: int = 30) -> List[Dict[str, Any]]:
    """
    Attempt to discover tools from an HTTP MCP server.

    Returns list of tool dictionaries with 'name' and 'description' keys.
    Returns empty list if discovery fails (e.g., auth required).
    """
    try:
        from ..utils.mcp_client import McpClient
        import asyncio

        async def _discover():
            client = McpClient(
                url=url,
                headers=headers or {},
                timeout=timeout
            )
            tools = []
            try:
                async with client:
                    await client.initialize()
                    discovered = await client.list_tools()
                    for tool in discovered:
                        tools.append({
                            'name': tool.get('name', 'unknown'),
                            'description': tool.get('description', '')
                        })
            except Exception as e:
                logger.debug(f"[MCP Config] Tool discovery failed: {e}")
            return tools

        # Run async discovery
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _discover())
                    return future.result(timeout=timeout)
            else:
                return loop.run_until_complete(_discover())
        except RuntimeError:
            return asyncio.run(_discover())

    except Exception as e:
        logger.debug(f"[MCP Config] Tool discovery error: {e}")
        return []


def _create_check_connection_for_http(server_name: str, server_config: Dict[str, Any]):
    """
    Create a check_connection static method for an HTTP MCP server.

    This method discovers tools from the MCP server using the provided credentials.
    Returns dict with 'tools' on success, or error message string on failure.
    """
    def check_connection(settings: dict) -> dict | str | None:
        """
        Discover tools from the MCP server.

        Args:
            settings: Dictionary containing user-provided credentials

        Returns:
            Dict with 'tools' list on success, error message string on failure
        """
        url = server_config.get('url', '')
        headers_template = server_config.get('headers', {})
        timeout = server_config.get('timeout', 60)

        # Substitute placeholders in headers with user-provided values
        headers = _substitute_placeholders(headers_template, settings)

        logger.info(f"[MCP Config] Discovering tools from {server_name} at {url}")

        try:
            from ..utils.mcp_client import McpClient
            import asyncio

            async def _discover():
                client = McpClient(
                    url=url,
                    headers=headers,
                    timeout=timeout
                )
                tools = []
                try:
                    async with client:
                        await client.initialize()
                        discovered = await client.list_tools()
                        for tool in discovered:
                            tools.append({
                                'name': tool.get('name', 'unknown'),
                                'description': tool.get('description', '')
                            })
                    return tools
                except Exception as e:
                    logger.error(f"[MCP Config] Tool discovery failed for {server_name}: {e}")
                    raise

            # Run async discovery
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _discover())
                        tools = future.result(timeout=timeout)
                else:
                    tools = loop.run_until_complete(_discover())
            except RuntimeError:
                tools = asyncio.run(_discover())

            logger.info(f"[MCP Config] Discovered {len(tools)} tools from {server_name}")
            return {'tools': tools}

        except Exception as e:
            error_msg = f"Failed to discover tools: {str(e)}"
            logger.error(f"[MCP Config] {error_msg}")
            return error_msg

    return check_connection


def get_mcp_config_toolkit_schemas() -> List[BaseModel]:
    """
    Get toolkit configuration schemas for all configured MCP servers.

    Returns Pydantic models that the platform can use to display available toolkits.
    Each configured MCP server appears as a separate toolkit in the UI.
    """
    from pydantic import create_model, ConfigDict, SecretStr
    from typing import Literal

    schemas = []
    servers = get_all_mcp_server_configs()

    for server_name, config in servers.items():
        server_type = config.get('type', 'stdio')
        server_schema = config.get('config_schema', {'properties': {}})
        description = config.get('description', f'MCP server: {server_name}')
        display_name = config.get('display_name', server_name.replace('_', ' ').title())

        # Attempt to discover tools from the MCP server
        discovered_tools = []
        tools_discovery_status = 'pending'  # 'discovered', 'auth_required', 'failed', 'pending'

        if server_type == 'http':
            url = config.get('url', '')
            # Only attempt discovery if no auth is required (no placeholder in headers)
            headers = config.get('headers', {})
            has_auth_placeholder = any('{' in str(v) for v in headers.values()) if headers else False

            if not has_auth_placeholder and url:
                # No auth placeholders, try to discover tools
                logger.info(f"[MCP Config] Attempting tool discovery for {server_name} (no auth required)")
                discovered_tools = _discover_tools_for_http_server(url, headers)
                tools_discovery_status = 'discovered' if discovered_tools else 'failed'
            else:
                # Auth is required, can't discover without credentials
                logger.info(f"[MCP Config] Skipping tool discovery for {server_name} (auth required)")
                tools_discovery_status = 'auth_required'

        # Use statically configured tools as fallback
        static_tools = config.get('tools', [])
        if not discovered_tools and static_tools:
            discovered_tools = static_tools
            if tools_discovery_status != 'auth_required':
                tools_discovery_status = 'static'

        # Get tool names for field options
        tool_names = [t.get('name', '') for t in discovered_tools if t.get('name')]

        # Build field definitions for the Pydantic model
        field_definitions = {
            # Hidden field to identify the server
            'server_name': (
                str,
                Field(
                    default=server_name,
                    description="MCP server name",
                    json_schema_extra={'hidden': True}
                )
            ),
        }

        # Add tool selection field only if tools were discovered
        # For auth-required servers, tools are discovered via check_connection after credentials are provided
        if tool_names:
            field_definitions['selected_tools'] = (
                Optional[List[str]],
                Field(
                    default=None,
                    description="Specific tools to enable (empty = all tools)",
                    json_schema_extra={
                        'tooltip': 'Leave empty to enable all tools from this MCP server',
                        'ui:widget': 'multiselect',
                        'options': tool_names
                    }
                )
            )

        # Add user-configurable fields from config_schema
        for param_name, param_config in server_schema.get('properties', {}).items():
            field_type, field_info = _create_pydantic_field(param_name, param_config)
            field_definitions[param_name] = (field_type, field_info)

        # Determine categories based on server type
        # Use 'integrations' as the UI category for visibility in credentials page
        # Keep MCP-specific info in extra_categories for search/filtering
        if server_type == 'stdio':
            categories = ['integrations']
            extra_categories = ['mcp', 'local', 'subprocess', config.get('runtime', 'npm')]
        else:
            categories = ['integrations']
            extra_categories = ['mcp', 'remote', 'http', 'sse']

        # Create the Pydantic model for this MCP server
        model = create_model(
            f'mcp_{server_name}',
            **field_definitions,
            __config__=ConfigDict(
                json_schema_extra={
                    'metadata': {
                        'label': display_name,
                        'icon_url': config.get('icon_url'),
                        'categories': categories,
                        'extra_categories': extra_categories,
                        'description': description,
                        # Section for configuration registration (credentials page)
                        'section': 'credentials',
                        # Custom metadata for MCP config
                        'mcp_server_type': server_type,
                        'mcp_server_name': server_name,
                        'stateful': config.get('stateful', False),
                        # Tool discovery results - enables UI to show available tools
                        'tools': discovered_tools,
                        'tools_discovery_status': tools_discovery_status,
                        # Custom button label for tool discovery
                        'check_connection_label': 'Load Tools',
                    }
                }
            )
        )

        # Attach check_connection method for tool discovery
        if server_type == 'http':
            model.check_connection = staticmethod(_create_check_connection_for_http(server_name, config))

        schemas.append(model)

    return schemas


def _create_pydantic_field(param_name: str, param_config: Dict[str, Any]) -> tuple:
    """Create a Pydantic field definition from config schema parameter."""
    from pydantic import SecretStr

    param_type = param_config.get('type', 'string')
    is_required = param_config.get('required', False)
    is_secret = param_config.get('secret', False)
    default_value = param_config.get('default')
    description = param_config.get('description', '')

    # Map config types to Python types
    if param_type == 'string':
        if is_secret:
            python_type = SecretStr
        else:
            python_type = str
    elif param_type == 'integer':
        python_type = int
    elif param_type == 'number':
        python_type = float
    elif param_type == 'boolean':
        python_type = bool
    elif param_type == 'array':
        item_type = param_config.get('items', {}).get('type', 'string')
        if item_type == 'string':
            python_type = List[str]
        elif item_type == 'integer':
            python_type = List[int]
        else:
            python_type = List[Any]
    else:
        python_type = str

    # Make optional if not required
    if not is_required:
        python_type = Optional[python_type]

    # Build field kwargs
    field_kwargs = {
        'description': description,
    }

    if default_value is not None:
        field_kwargs['default'] = default_value
    elif not is_required:
        field_kwargs['default'] = None

    # Add extra schema info
    json_schema_extra = {}
    if is_secret:
        json_schema_extra['secret'] = True
        json_schema_extra['format'] = 'password'
    if param_config.get('tooltip'):
        json_schema_extra['tooltip'] = param_config['tooltip']
    if param_config.get('example'):
        json_schema_extra['example'] = param_config['example']

    if json_schema_extra:
        field_kwargs['json_schema_extra'] = json_schema_extra

    return python_type, Field(**field_kwargs)


# Backward compatibility aliases
McpStdioToolkit = McpConfigToolkit
get_mcp_stdio_toolkit_schemas = get_mcp_config_toolkit_schemas
