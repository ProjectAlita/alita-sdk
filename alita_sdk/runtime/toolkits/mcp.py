"""
MCP (Model Context Protocol) Toolkit for Alita SDK.
This toolkit enables connection to a single remote MCP server and exposes its tools.
Following MCP specification: https://modelcontextprotocol.io/specification/2025-06-18
"""

import logging
import re
import requests
from typing import List, Optional, Any, Dict, Literal, ClassVar, Union

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, ConfigDict, Field

from ..tools.mcp_server_tool import McpServerTool
from ..tools.mcp_remote_tool import McpRemoteTool
from ..tools.mcp_inspect_tool import McpInspectTool
from ...tools.utils import TOOLKIT_SPLITTER, clean_string
from ..models.mcp_models import McpConnectionConfig
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

def optimize_tool_name(prefix: str, tool_name: str, max_total_length: int = 64) -> str:
    """
    Optimize tool name to fit within max_total_length while preserving meaning.
    
    Args:
        prefix: The toolkit prefix (already cleaned)
        tool_name: The original tool name
        max_total_length: Maximum total length for the full tool name (default: 64)
    
    Returns:
        Optimized full tool name in format: prefix___tool_name
    """
    splitter = TOOLKIT_SPLITTER
    splitter_len = len(splitter)
    prefix_len = len(prefix)
    
    # Calculate available space for tool name
    available_space = max_total_length - prefix_len - splitter_len
    
    if available_space <= 0:
        logger.error(f"Prefix '{prefix}' is too long ({prefix_len} chars), cannot create valid tool name")
        # Fallback: truncate prefix itself
        prefix = prefix[:max_total_length - splitter_len - 10]  # Leave 10 chars for tool name
        available_space = max_total_length - len(prefix) - splitter_len
    
    # If tool name fits, use it as-is
    if len(tool_name) <= available_space:
        return f'{prefix}{splitter}{tool_name}'
    
    # Tool name is too long, need to optimize
    logger.debug(f"Tool name '{tool_name}' is too long ({len(tool_name)} chars), optimizing to fit {available_space} chars")
    
    # Split tool name into parts (handle camelCase, snake_case, and mixed)
    # First, split by underscores and hyphens
    parts = re.split(r'[_-]', tool_name)
    
    # Further split camelCase within each part
    all_parts = []
    for part in parts:
        # Insert underscore before uppercase letters (camelCase to snake_case)
        snake_case_part = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', part)
        all_parts.extend(snake_case_part.split('_'))
    
    # Filter out empty parts
    all_parts = [p for p in all_parts if p]
    
    # Remove redundant prefix words (case-insensitive comparison)
    # Only remove if prefix is meaningful (>= 3 chars) to avoid over-filtering
    prefix_lower = prefix.lower()
    filtered_parts = []
    for part in all_parts:
        part_lower = part.lower()
        # Skip if this part contains the prefix or the prefix contains this part
        # But only if both are meaningful (>= 3 chars)
        should_remove = False
        if len(prefix_lower) >= 3 and len(part_lower) >= 3:
            if part_lower in prefix_lower or prefix_lower in part_lower:
                should_remove = True
                logger.debug(f"Removing redundant part '{part}' (matches prefix '{prefix}')")
        
        if not should_remove:
            filtered_parts.append(part)
    
    # If we removed all parts, keep the original parts
    if not filtered_parts:
        filtered_parts = all_parts
    
    # Reconstruct tool name with filtered parts
    optimized_name = '_'.join(filtered_parts)
    
    # If still too long, truncate intelligently
    if len(optimized_name) > available_space:
        # Strategy: Keep beginning and end, as they often contain the most important info
        # For example: "projectalita_github_io_list_branches" -> "projectalita_list_branches"
        
        # Try removing middle parts first
        if len(filtered_parts) > 2:
            # Keep first and last parts, remove middle
            kept_parts = [filtered_parts[0], filtered_parts[-1]]
            optimized_name = '_'.join(kept_parts)
            
            # If still too long, add parts from the end until we run out of space
            if len(optimized_name) <= available_space and len(filtered_parts) > 2:
                for i in range(len(filtered_parts) - 2, 0, -1):
                    candidate = '_'.join([filtered_parts[0]] + filtered_parts[i:])
                    if len(candidate) <= available_space:
                        optimized_name = candidate
                        break
        
        # If still too long, just truncate
        if len(optimized_name) > available_space:
            # Try to truncate at word boundary
            truncated = optimized_name[:available_space]
            last_underscore = truncated.rfind('_')
            if last_underscore > available_space * 0.7:  # Keep if we're not losing too much
                optimized_name = truncated[:last_underscore]
            else:
                optimized_name = truncated
    
    full_name = f'{prefix}{splitter}{optimized_name}'
    logger.info(f"Optimized tool name: '{tool_name}' ({len(tool_name)} chars) -> '{optimized_name}' ({len(optimized_name)} chars), full: '{full_name}' ({len(full_name)} chars)")
    
    return full_name

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
                Union[int, str], # TODO: remove one I will figure out why UI sends str
                Field(
                    default=300,
                    description="Request timeout in seconds (1-3600)"
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
                Union[int, str],
                Field(
                    default=300,
                    description="Discovery interval in seconds (60-3600, for periodic discovery)"
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

        # Convert numeric parameters that may come as strings from UI
        timeout = safe_int(timeout, 60)
        discovery_interval = safe_int(discovery_interval, 300)
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
            # Use session_id from discovery (which may have been created if server requires it)
            # If discovery returned a session_id, it means a new session was created
            # Log it so UI can capture and store it
            if session_id:
                logger.info(f"[MCP Session] Using session from discovery: {session_id}")
                logger.info(f"[MCP Session] Session created - server: {canonical_resource(connection_config.url)}, session_id: {session_id}")
            
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

        except Exception as e:
            logger.error(f"Direct discovery failed for MCP toolkit '{toolkit_name}': {e}", exc_info=True)
            logger.error(f"Discovery error details - URL: {connection_config.url}, Timeout: {timeout}s")

            # Fallback to static mode if available and not already static
            if isinstance(e, McpAuthorizationRequired):
                # Authorization is required; surface upstream so the caller can prompt the user
                raise
            if client and discovery_mode != "static":
                logger.info(f"Falling back to static discovery for toolkit '{toolkit_name}'")
                tools = cls._create_tools_static(toolkit_name, selected_tools, timeout, client)
            else:
                logger.warning(f"No fallback available for toolkit '{toolkit_name}' - returning empty tools list")

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
    ) -> List[Dict[str, Any]]:
        """
        Synchronously discover tools and prompts from MCP server using HTTP requests.
        Returns list of tool/prompt dictionaries with name, description, and inputSchema.
        Prompts are converted to tools that can be invoked.
        """
        all_tools = []
        
        # Check if we have a session_id from UI (passed via connection_config)
        # If not, we'll try discovery without session first, and create one if needed
        session_id = connection_config.session_id
        
        # Discover regular tools - if server requires session and we don't have one, this will fail
        # and we'll catch it below to initialize a session
        try:
            tools_data = cls._discover_mcp_endpoint(
                endpoint="tools/list",
                toolkit_name=toolkit_name,
                connection_config=connection_config,
                timeout=timeout,
                session_id=session_id
            )
        except Exception as discovery_error:
            # Check if error is due to missing session
            if "Missing sessionId" in str(discovery_error) and not session_id:
                logger.info(f"[MCP Session] Server requires session for discovery, initializing...")
                # Try to initialize session if we have OAuth headers
                session_id = cls._initialize_mcp_session(
                    toolkit_name=toolkit_name,
                    connection_config=connection_config,
                    timeout=timeout,
                    extra_headers=connection_config.headers  # Use headers from connection_config
                )
                
                if session_id:
                    logger.info(f"[MCP Session] Created session for discovery: {session_id}")
                    # Retry discovery with session
                    tools_data = cls._discover_mcp_endpoint(
                        endpoint="tools/list",
                        toolkit_name=toolkit_name,
                        connection_config=connection_config,
                        timeout=timeout,
                        session_id=session_id
                    )
                else:
                    logger.error(f"[MCP Session] Failed to create session for discovery")
                    raise discovery_error
            else:
                raise
        all_tools.extend(tools_data)
        logger.info(f"Discovered {len(tools_data)} tools from MCP toolkit '{toolkit_name}'")
        
        # Discover prompts and convert them to tools
        try:
            prompts_data = cls._discover_mcp_endpoint(
                endpoint="prompts/list",
                toolkit_name=toolkit_name,
                connection_config=connection_config,
                timeout=timeout,
                session_id=session_id
            )
            # Convert prompts to tool format
            for prompt in prompts_data:
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
            logger.info(f"Discovered {len(prompts_data)} prompts from MCP toolkit '{toolkit_name}'")
        except Exception as e:
            logger.warning(f"Failed to discover prompts from MCP toolkit '{toolkit_name}': {e}")
        
        logger.info(f"Total discovered {len(all_tools)} tools+prompts from MCP toolkit '{toolkit_name}'")
        return all_tools, session_id

    @classmethod
    def _initialize_mcp_session(
        cls,
        toolkit_name: str,
        connection_config: McpConnectionConfig,
        timeout: int,
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Initialize an MCP session for stateful SSE servers.
        Returns sessionId if successful, None if server doesn't require sessions.
        
        Note: This session should be stored by the caller (e.g., UI sessionStorage)
        and passed back for subsequent requests. Sessions should NOT be cached
        on the backend for security reasons (multi-tenant environment).
        
        Args:
            toolkit_name: Name of the toolkit
            connection_config: MCP connection configuration
            timeout: Request timeout in seconds
            extra_headers: Additional headers (e.g., Authorization) to include
        """
        import time

        mcp_request = {
            "jsonrpc": "2.0",
            "id": f"initialize_{int(time.time())}",
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

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if connection_config.headers:
            headers.update(connection_config.headers)
        if extra_headers:
            headers.update(extra_headers)
            logger.debug(f"[MCP Session] Added extra headers: {list(extra_headers.keys())}")

        try:
            logger.info(f"[MCP Session] Attempting to initialize session for {connection_config.url}")
            logger.debug(f"[MCP Session] Initialize request: {mcp_request}")
            response = requests.post(
                connection_config.url,
                json=mcp_request,
                headers=headers,
                timeout=timeout
            )

            logger.info(f"[MCP Session] Initialize response status: {response.status_code}")
            if response.status_code == 200:
                # Parse the response to extract sessionId
                content_type = response.headers.get('Content-Type', '')
                logger.debug(f"[MCP Session] Response Content-Type: {content_type}")
                
                if 'text/event-stream' in content_type:
                    data = cls._parse_sse_response(response.text)
                elif 'application/json' in content_type:
                    data = response.json()
                else:
                    logger.warning(f"[MCP Session] Unexpected Content-Type during initialize: {content_type}")
                    logger.debug(f"[MCP Session] Response text: {response.text[:500]}")
                    return None

                logger.debug(f"[MCP Session] Parsed response: {data}")
                
                # Extract sessionId from response
                result = data.get("result", {})
                session_id = result.get("sessionId")
                if session_id:
                    logger.info(f"[MCP Session] ✓ Session initialized for '{toolkit_name}': {session_id}")
                    logger.info(f"[MCP Session] This sessionId should be stored by the caller and sent back for subsequent requests")
                    return session_id
                else:
                    logger.info(f"[MCP Session] No sessionId in initialize response for '{toolkit_name}' - server may not require sessions")
                    logger.debug(f"[MCP Session] Full result: {result}")
                    return None
            else:
                logger.warning(f"[MCP Session] Initialize returned {response.status_code} for '{toolkit_name}' - server may not support sessions")
                logger.debug(f"[MCP Session] Response: {response.text[:500]}")
                return None

        except Exception as e:
            logger.warning(f"[MCP Session] Failed to initialize MCP session for '{toolkit_name}': {e} - proceeding without session")
            import traceback
            logger.debug(f"[MCP Session] Traceback: {traceback.format_exc()}")
            return None

    @classmethod
    def _discover_mcp_endpoint(
        cls,
        endpoint: str,
        toolkit_name: str,
        connection_config: McpConnectionConfig,
        timeout: int,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Discover items from a specific MCP endpoint (tools/list or prompts/list).
        Returns list of dictionaries.
        """
        import time

        # MCP protocol request
        mcp_request = {
            "jsonrpc": "2.0",
            "id": f"discover_{endpoint.replace('/', '_')}_{int(time.time())}",
            "method": endpoint,
            "params": {}
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if connection_config.headers:
            headers.update(connection_config.headers)

        # Add sessionId to URL if provided (for stateful SSE servers)
        url = connection_config.url
        if session_id:
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}sessionId={session_id}"
            logger.info(f"[MCP Session] Using session {session_id} for {endpoint} request")
        else:
            logger.debug(f"[MCP Session] No session ID available for {endpoint} request - server may not require sessions")

        try:
            logger.debug(f"Sending MCP {endpoint} request to {url}")
            response = requests.post(
                url,
                json=mcp_request,
                headers=headers,
                timeout=timeout
            )

            auth_header = response.headers.get('WWW-Authenticate', '')
            if response.status_code == 401:
                resource_metadata_url = extract_resource_metadata_url(auth_header, connection_config.url)
                metadata = fetch_resource_metadata(resource_metadata_url, timeout=timeout) if resource_metadata_url else None
                
                # If we couldn't get metadata from the resource_metadata endpoint,
                # infer authorization servers from the WWW-Authenticate header and server URL
                if not metadata or not metadata.get('authorization_servers'):
                    inferred_servers = infer_authorization_servers_from_realm(auth_header, connection_config.url)
                    if inferred_servers:
                        if not metadata:
                            metadata = {}
                        metadata['authorization_servers'] = inferred_servers
                        logger.info(f"Inferred authorization servers for {connection_config.url}: {inferred_servers}")
                        
                        # Fetch OAuth authorization server metadata from the inferred server
                        # This avoids CORS issues in the frontend
                        from alita_sdk.runtime.utils.mcp_oauth import fetch_oauth_authorization_server_metadata
                        auth_server_metadata = fetch_oauth_authorization_server_metadata(inferred_servers[0], timeout=timeout)
                        if auth_server_metadata:
                            metadata['oauth_authorization_server'] = auth_server_metadata
                            logger.info(f"Fetched OAuth metadata for {inferred_servers[0]}")
                
                raise McpAuthorizationRequired(
                    message=f"MCP server {connection_config.url} requires OAuth authorization",
                    server_url=canonical_resource(connection_config.url),
                    resource_metadata_url=resource_metadata_url,
                    www_authenticate=auth_header,
                    resource_metadata=metadata,
                    status=response.status_code,
                    tool_name=toolkit_name,
                )

            if response.status_code != 200:
                logger.error(f"MCP server returned non-200 status: {response.status_code}")
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

            # Parse MCP response - different endpoints return different keys
            result = data.get("result", {})
            if endpoint == "tools/list":
                return result.get("tools", [])
            elif endpoint == "prompts/list":
                return result.get("prompts", [])
            else:
                return result.get("items", [])

        except Exception as e:
            logger.error(f"Failed to discover from {endpoint} on MCP toolkit '{toolkit_name}': {e}")
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
        connection_config: McpConnectionConfig,
        timeout: int,
        client,
        session_id: Optional[str] = None
    ) -> Optional[BaseTool]:
        """Create a BaseTool from a tool/prompt dictionary (from direct HTTP discovery)."""
        try:
            # Store toolkit_max_length in local variable to avoid contextual access issues
            max_length_value = cls.toolkit_max_length

            # Clean toolkit name for prefixing
            clean_prefix = clean_string(toolkit_name, max_length_value)

            # Optimize tool name to fit within 64 character limit
            full_tool_name = optimize_tool_name(clean_prefix, tool_dict.get("name", "unknown"))
            
            # Check if this is a prompt (converted to tool)
            is_prompt = tool_dict.get("_mcp_type") == "prompt"
            item_type = "prompt" if is_prompt else "tool"

            # Build description and ensure it doesn't exceed 1000 characters
            description = f"MCP {item_type} '{tool_dict.get('name')}' from toolkit '{toolkit_name}': {tool_dict.get('description', '')}"
            if len(description) > 1000:
                description = description[:997] + "..."
                logger.debug(f"Trimmed description for tool '{tool_dict.get('name')}' from {len(description)} to 1000 chars")

            # Use McpRemoteTool for remote MCP servers (HTTP/SSE)
            return McpRemoteTool(
                name=full_tool_name,
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
                original_tool_name=tool_dict.get('name'),  # Store original name for MCP server invocation
                session_id=session_id  # Pass session ID for stateful SSE servers
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
            # Optimize tool name to fit within 64 character limit
            full_tool_name = optimize_tool_name(clean_prefix, tool_metadata.name)

            # Build description and ensure it doesn't exceed 1000 characters
            description = f"MCP tool '{tool_metadata.name}' from server '{tool_metadata.server}': {tool_metadata.description}"
            if len(description) > 1000:
                description = description[:997] + "..."
                logger.debug(f"Trimmed description for tool '{tool_metadata.name}' from {len(description)} to 1000 chars")

            return McpServerTool(
                name=full_tool_name,
                description=description,
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

            # Optimize tool name to fit within 64 character limit
            full_tool_name = optimize_tool_name(clean_prefix, available_tool["name"])

            # Build description and ensure it doesn't exceed 1000 characters
            description = f"MCP tool '{available_tool['name']}' from toolkit '{toolkit_name}': {available_tool.get('description', '')}"
            if len(description) > 1000:
                description = description[:997] + "..."
                logger.debug(f"Trimmed description for tool '{available_tool['name']}' from {len(description)} to 1000 chars")

            return McpServerTool(
                name=full_tool_name,
                description=description,
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
        discovery_mode=settings.get('discovery_mode', 'dynamic'),
        discovery_interval=safe_int(settings.get('discovery_interval'), 300),
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
