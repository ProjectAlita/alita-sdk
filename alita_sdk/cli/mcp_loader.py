"""
MCP (Model Context Protocol) server integration.

Handles loading MCP server configurations and connecting to MCP servers
using langchain-mcp-adapters to load tools with persistent sessions.

Requires: pip install langchain-mcp-adapters
Documentation: https://docs.langchain.com/oss/python/langchain/mcp
Issue Reference: https://github.com/langchain-ai/langchain-mcp-adapters/issues/178
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console

from .config import substitute_env_vars

console = Console()
logger = logging.getLogger(__name__)


def load_mcp_config(file_path: str) -> Dict[str, Any]:
    """Load MCP configuration from JSON file (VSCode/Copilot format).
    
    Args:
        file_path: Path to mcp.json configuration file
        
    Returns:
        Dictionary with mcpServers configuration, or empty dict if file doesn't exist
    """
    path = Path(file_path)
    
    if not path.exists():
        # Gracefully handle missing file - MCP is optional
        return {}
    
    try:
        with open(path) as f:
            content = f.read()
        
        # Apply environment variable substitution
        content = substitute_env_vars(content)
        config = json.loads(content)
        
        # Validate structure
        if 'mcpServers' not in config:
            console.print(f"[yellow]Warning: {file_path} missing 'mcpServers' key[/yellow]")
            return {}
            
        return config
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing {file_path}:[/red] {e}")
        return {}
    except Exception as e:
        console.print(f"[red]Error loading {file_path}:[/red] {e}")
        return {}


def load_mcp_tools(agent_def: Dict[str, Any], mcp_config_path: str) -> List[Dict[str, Any]]:
    """Load MCP tools from agent definition with tool-level filtering.
    
    This function creates MCP server configuration objects that will be processed
    by the runtime layer using langchain-mcp-adapters to connect to MCP servers
    and load their tools.
    
    The actual connection happens in create_mcp_client() which uses:
    - langchain_mcp_adapters.client.MultiServerMCPClient for connection
    - langchain_mcp_adapters.tools.load_mcp_tools for tool loading
    
    Args:
        agent_def: Agent definition dictionary containing mcps list
        mcp_config_path: Path to mcp.json configuration file (workspace-level)
        
    Returns:
        List of MCP server configurations that will be used by MultiServerMCPClient
        to connect to servers and load tools with filtering applied.
    """
    import fnmatch
    
    toolkit_configs = []
    
    # Get MCP configuration
    mcps = agent_def.get('mcps', [])
    if not mcps:
        return toolkit_configs
    
    # Load mcp.json config file from workspace
    mcp_config = load_mcp_config(mcp_config_path)
    mcp_servers = mcp_config.get('mcpServers', {})
    
    # Process each MCP entry
    for mcp_entry in mcps:
        # Handle both string and object formats
        if isinstance(mcp_entry, str):
            server_name = mcp_entry
            agent_selected_tools = None
            agent_excluded_tools = None
        elif isinstance(mcp_entry, dict):
            server_name = mcp_entry.get('name')
            agent_selected_tools = mcp_entry.get('selected_tools')
            agent_excluded_tools = mcp_entry.get('excluded_tools')
        else:
            console.print(f"[yellow]Warning: Invalid MCP entry format: {mcp_entry}[/yellow]")
            continue
        
        if not server_name:
            console.print(f"[yellow]Warning: MCP entry missing 'name': {mcp_entry}[/yellow]")
            continue
        
        # Get server configuration
        server_config = mcp_servers.get(server_name)
        if not server_config:
            console.print(f"[yellow]Warning: MCP server '{server_name}' not found in MCP configuration[/yellow]")
            continue
        
        # Determine tool selection (agent overrides server defaults)
        server_selected_tools = server_config.get('selected_tools')
        server_excluded_tools = server_config.get('excluded_tools')
        
        # Agent overrides take precedence
        final_selected_tools = agent_selected_tools if agent_selected_tools is not None else server_selected_tools
        final_excluded_tools = agent_excluded_tools if agent_excluded_tools is not None else server_excluded_tools
        
        # Get connection details
        server_type = server_config.get('type')  # VSCode format: "stdio" or "streamable_http"
        server_url = server_config.get('url')
        server_command = server_config.get('command')
        server_args = server_config.get('args', [])
        server_env = server_config.get('env', {})
        stateful = server_config.get('stateful', False)
        
        # Build MCP server config for langchain-mcp-adapters
        # Support both VSCode format (type: "stdio") and our format (command: "...")
        if server_type == 'stdio' or server_command:
            # stdio transport (subprocess)
            if not server_command:
                console.print(f"[red]Error: MCP server '{server_name}' has type 'stdio' but no 'command'[/red]")
                continue
            
            console.print(f"[yellow]Note: MCP server '{server_name}' uses command/stdio connection[/yellow]")
            mcp_server_config = {
                'transport': 'stdio',
                'command': server_command,
                'args': server_args or []
            }
        elif server_type == 'streamable_http' or server_url:
            # HTTP-based transport
            if not server_url:
                console.print(f"[red]Error: MCP server '{server_name}' has type 'streamable_http' but no 'url'[/red]")
                continue
            
            mcp_server_config = {
                'transport': 'streamable_http',
                'url': server_url
            }
        else:
            console.print(f"[red]Error: MCP server '{server_name}' has neither 'type'/'url' nor 'command'[/red]")
            continue
        
        # Add environment variables if specified
        if server_env:
            mcp_server_config['env'] = server_env
        
        # Wrap in toolkit config format
        toolkit_config = {
            'toolkit_type': 'mcp',
            'name': server_name,
            'mcp_server_config': mcp_server_config,
        }
        
        # Add tool filtering if specified
        if final_selected_tools is not None:
            toolkit_config['selected_tools'] = final_selected_tools
        if final_excluded_tools is not None:
            toolkit_config['excluded_tools'] = final_excluded_tools
        
        toolkit_configs.append(toolkit_config)
        
        # Display loaded tools info
        if final_selected_tools:
            tools_display = ', '.join(final_selected_tools)
            console.print(f"✓ Loaded MCP server: [cyan]{server_name}[/cyan] (selected: {tools_display})")
        elif final_excluded_tools:
            console.print(f"✓ Loaded MCP server: [cyan]{server_name}[/cyan] (excluded: {', '.join(final_excluded_tools)})")
        else:
            console.print(f"✓ Loaded MCP server: [cyan]{server_name}[/cyan] (all tools)")
    
    return toolkit_configs


class MCPSessionManager:
    """Manages persistent MCP sessions for stateful tools like Playwright.
    
    Holds MCP client and session context managers alive for the entire agent lifetime.
    This is critical for stateful MCP servers that maintain state across tool calls
    (e.g., Playwright browser sessions).
    
    See: https://github.com/langchain-ai/langchain-mcp-adapters/issues/178
    """
    def __init__(self):
        self.client = None
        self.sessions = {}
        self._session_contexts = {}
    
    def __del__(self):
        """Cleanup sessions when manager is garbage collected."""
        # Best effort cleanup - sessions will be closed when process exits anyway
        pass


async def load_mcp_tools_async(mcp_toolkit_configs: List[Dict[str, Any]]):
    """
    Load actual MCP tools from servers with persistent sessions.
    
    IMPORTANT: This function returns an MCPSessionManager that MUST be kept alive
    for the entire agent session to maintain stateful MCP server state (e.g., browser).
    
    Args:
        mcp_toolkit_configs: List of MCP toolkit configurations with transport details
        
    Returns:
        Tuple of (session_manager, list_of_tools) where:
        - session_manager: MCPSessionManager that holds client and persistent sessions
        - list_of_tools: LangChain async tools from MCP that use persistent sessions
    """
    if not mcp_toolkit_configs:
        return None, []
    
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain_mcp_adapters.tools import load_mcp_tools
    except ImportError:
        console.print("[yellow]Warning: langchain-mcp-adapters not installed. MCP tools will not be available.[/yellow]")
        console.print("[yellow]Install with: pip install langchain-mcp-adapters[/yellow]")
        return None, []
    
    # Build server configs for MultiServerMCPClient
    server_configs = {}
    for config in mcp_toolkit_configs:
        server_name = config.get('name', 'unknown')
        mcp_server_config = config.get('mcp_server_config', {})
        transport = mcp_server_config.get('transport', 'stdio')
        
        if transport == 'stdio':
            command = mcp_server_config.get('command')
            args = mcp_server_config.get('args', [])
            env = mcp_server_config.get('env')
            
            # Ensure command is a string
            if isinstance(command, list):
                command = command[0] if command else None
            
            # Build config dict - only include env if it's set
            config_dict = {
                'transport': 'stdio',
                'command': command,
                'args': args
            }
            if env:
                config_dict['env'] = env
            
            server_configs[server_name] = config_dict
            console.print(f"[dim]MCP server {server_name}: {command} {' '.join(args)}[/dim]")
            
        elif transport == 'streamable_http':
            server_configs[server_name] = {
                'transport': 'streamable_http',
                'url': mcp_server_config.get('url'),
                'headers': mcp_server_config.get('headers')
            }
    
    if not server_configs:
        return None, []
    
    try:
        # Create session manager to hold everything alive
        manager = MCPSessionManager()
        manager.client = MultiServerMCPClient(server_configs)
        
        # Create PERSISTENT sessions for each server
        # This keeps the MCP server subprocess and state alive for stateful tools
        all_tools = []
        
        for server_name in server_configs.keys():
            # Enter the session context and keep it alive for entire agent lifetime
            session_context = manager.client.session(server_name)
            session = await session_context.__aenter__()
            
            # Store both for cleanup and reference
            manager.sessions[server_name] = session
            manager._session_contexts[server_name] = session_context
            
            # Load tools using the persistent session
            tools = await load_mcp_tools(
                session,
                connection=manager.client.connections[server_name],
                server_name=server_name
            )
            all_tools.extend(tools)
            
            console.print(f"[dim]Created persistent session for {server_name}: {len(tools)} tools[/dim]")
        
        console.print(f"✓ Loaded {len(all_tools)} MCP tools total from {len(mcp_toolkit_configs)} servers with persistent sessions")
        
        return manager, all_tools
            
    except ImportError:
        # Already handled above
        raise
    except Exception as e:
        logger.exception(f"Failed to create MCP client and sessions")
        console.print(f"[red]Error: Failed to load MCP tools: {e}[/red]")
        return None, []
