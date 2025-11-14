import logging
from typing import Optional

from langchain_core.tools import ToolException
from langgraph.store.base import BaseStore

from alita_sdk.tools import get_toolkits as alita_toolkits
from alita_sdk.tools import get_tools as alita_tools
from .application import ApplicationToolkit
from .artifact import ArtifactToolkit
from .datasource import DatasourcesToolkit
from .prompt import PromptToolkit
from .subgraph import SubgraphToolkit
from .vectorstore import VectorStoreToolkit
from ..tools.mcp_server_tool import McpServerTool
from ..tools.sandbox import SandboxToolkit
from ..tools.image_generation import ImageGenerationToolkit
# Import community tools
from ...community import get_toolkits as community_toolkits, get_tools as community_tools
from ...tools.memory import MemoryToolkit
from ...tools.utils import TOOLKIT_SPLITTER

logger = logging.getLogger(__name__)


def get_toolkits():
    core_toolkits = [
        ArtifactToolkit.toolkit_config_schema(),
        MemoryToolkit.toolkit_config_schema(),
        VectorStoreToolkit.toolkit_config_schema(),
        SandboxToolkit.toolkit_config_schema(),
        ImageGenerationToolkit.toolkit_config_schema()
    ]

    return core_toolkits + community_toolkits() + alita_toolkits()


def get_tools(tools_list: list, alita_client, llm, memory_store: BaseStore = None, debug_mode: Optional[bool] = False) -> list:
    prompts = []
    tools = []

    for tool in tools_list:
        try:
            if tool['type'] == 'datasource':
                tools.extend(DatasourcesToolkit.get_toolkit(
                    alita_client,
                    datasource_ids=[int(tool['settings']['datasource_id'])],
                    selected_tools=tool['settings']['selected_tools'],
                    toolkit_name=tool.get('toolkit_name', '') or tool.get('name', '')
                ).get_tools())
            elif tool['type'] == 'application':
                tools.extend(ApplicationToolkit.get_toolkit(
                    alita_client,
                    application_id=int(tool['settings']['application_id']),
                    application_version_id=int(tool['settings']['application_version_id']),
                    selected_tools=[]
                ).get_tools())
                # backward compatibility for pipeline application type as subgraph node
                if tool.get('agent_type', '') == 'pipeline':
                    # static get_toolkit returns a list of CompiledStateGraph stubs
                    tools.extend(SubgraphToolkit.get_toolkit(
                        alita_client,
                        application_id=int(tool['settings']['application_id']),
                        application_version_id=int(tool['settings']['application_version_id']),
                        app_api_key=alita_client.auth_token,
                        selected_tools=[],
                        llm=llm
                    ))
            elif tool['type'] == 'memory':
                tools += MemoryToolkit.get_toolkit(
                    namespace=tool['settings'].get('namespace', str(tool['id'])),
                    pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
                    store=memory_store,
                ).get_tools()
            # TODO: update configuration of internal tools
            elif tool['type'] == 'internal_tool':
                if tool['name'] == 'pyodide':
                    tools += SandboxToolkit.get_toolkit(
                        stateful=False,
                        allow_net=True,
                        alita_client=alita_client,
                    ).get_tools()
                elif tool['name'] == 'image_generation':
                    if alita_client and alita_client.model_image_generation:
                        tools += ImageGenerationToolkit.get_toolkit(
                            client=alita_client,
                        ).get_tools()
                    else:
                        logger.warning("Image generation internal tool requested "
                                       "but no image generation model configured")
            elif tool['type'] == 'artifact':
                tools.extend(ArtifactToolkit.get_toolkit(
                    client=alita_client,
                    bucket=tool['settings']['bucket'],
                    toolkit_name=tool.get('toolkit_name', ''),
                    selected_tools=tool['settings'].get('selected_tools', []),
                    llm=llm,
                    # indexer settings
                    pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
                    embedding_model=tool['settings'].get('embedding_model'),
                    collection_name=f"{tool.get('toolkit_name')}",
                    collection_schema = str(tool['id'])
                ).get_tools())
            elif tool['type'] == 'vectorstore':
                tools.extend(VectorStoreToolkit.get_toolkit(
                    llm=llm,
                    toolkit_name=tool.get('toolkit_name', ''),
                    **tool['settings']).get_tools())
        except Exception as e:
            logger.error(f"Error initializing toolkit for tool '{tool.get('name', 'unknown')}': {e}", exc_info=True)
            if debug_mode:
                logger.info("Skipping tool initialization error due to debug mode.")
                continue
            else:
                raise ToolException(f"Error initializing toolkit for tool '{tool.get('name', 'unknown')}': {e}")
    
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita_client, prompts).get_tools()
    
    # Add community tools
    tools += community_tools(tools_list, alita_client, llm)
    # Add alita tools
    tools += alita_tools(tools_list, alita_client, llm, memory_store)
    # Add MCP tools
    tools += _mcp_tools(tools_list, alita_client)
    
    # Sanitize tool names to meet OpenAI's function naming requirements
    # tools = _sanitize_tool_names(tools)
    
    return tools


def _sanitize_tool_names(tools: list) -> list:
    """
    Sanitize tool names to meet OpenAI's function naming requirements.
    OpenAI function names must match pattern ^[a-zA-Z0-9_\\.-]+$
    """
    import re
    from langchain_core.tools import BaseTool
    
    def sanitize_name(name):
        """Sanitize a single tool name"""
        # Replace spaces and other invalid characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_{2,}', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized
    
    sanitized_tools = []
    name_mapping = {}
    
    for tool in tools:
        if isinstance(tool, BaseTool):
            original_name = tool.name
            sanitized_name = sanitize_name(original_name)
            
            # Only update if the name actually changed
            if original_name != sanitized_name:
                logger.info(f"Sanitizing tool name: '{original_name}' -> '{sanitized_name}'")
                # Create a new tool instance with the sanitized name
                # We need to be careful here to preserve all other tool properties
                tool.name = sanitized_name
                name_mapping[original_name] = sanitized_name
            
            sanitized_tools.append(tool)
        else:
            # For non-BaseTool objects (like CompiledStateGraph), just pass through
            sanitized_tools.append(tool)
    
    if name_mapping:
        logger.info(f"Tool name sanitization complete. Mapped {len(name_mapping)} tool names.")
    
    return sanitized_tools


def _mcp_tools(tools_list, alita):
    try:
        all_available_toolkits = alita.get_mcp_toolkits()
        toolkit_lookup = {tk["name"]: tk for tk in all_available_toolkits}
        tools = []
        #
        for selected_toolkit in tools_list:
            server_toolkit_name = selected_toolkit['type']
            toolkit_conf = toolkit_lookup.get(server_toolkit_name)
            #
            if not toolkit_conf:
                logger.debug(f"Toolkit '{server_toolkit_name}' not found in available MCP toolkits. Skipping...")
                continue
            #
            available_tools = toolkit_conf.get("tools", [])
            selected_tools = [name.lower() for name in selected_toolkit['settings'].get('selected_tools', [])]
            for available_tool in available_tools:
                tool_name = available_tool.get("name", "").lower()
                if not selected_tools or tool_name in selected_tools:
                    if server_tool := _init_single_mcp_tool(server_toolkit_name,
                                                            # selected_toolkit["name"] is None for toolkit_test
                                                            selected_toolkit["toolkit_name"] if selected_toolkit.get("toolkit_name")
                                                            else server_toolkit_name,
                                                            available_tool, alita, selected_toolkit['settings']):
                        tools.append(server_tool)
        return tools
    except Exception:
        logger.error("Error while fetching MCP tools", exc_info=True)
        return []


def _init_single_mcp_tool(server_toolkit_name, toolkit_name, available_tool, alita, toolkit_settings):
    try:

        tool_name = f'{toolkit_name}{TOOLKIT_SPLITTER}{available_tool["name"]}'
        return McpServerTool(
            name=tool_name,
            description=f"MCP for a tool '{tool_name}': {available_tool.get("description", "")}",
            args_schema=McpServerTool.create_pydantic_model_from_schema(
                available_tool.get("inputSchema", {})
            ),
            client=alita,
            server=server_toolkit_name,
            tool_timeout_sec=toolkit_settings.get("timeout", 90)
        )
    except Exception as e:
        logger.error(f"Failed to create McpServerTool ('{server_toolkit_name}') for '{toolkit_name}.{tool_name}': {e}")
        return None
