import logging

from alita_tools import get_toolkits as alita_toolkits
from alita_tools import get_tools as alita_tools

from .application import ApplicationToolkit
from .artifact import ArtifactToolkit
from .datasource import DatasourcesToolkit
from .prompt import PromptToolkit
from .subgraph import SubgraphToolkit
from .vectorstore import VectorStoreToolkit
## Community tools and toolkits
from ..community.analysis.jira_analyse import AnalyseJira
from ..community.browseruse import BrowserUseToolkit

from ..tools.mcp_server_tool import McpServerTool

logger = logging.getLogger(__name__)


def get_toolkits():
    core_toolkits = [
        # PromptToolkit.toolkit_config_schema(),
        # DatasourcesToolkit.toolkit_config_schema(),
        # ApplicationToolkit.toolkit_config_schema(),
        ArtifactToolkit.toolkit_config_schema(),
        VectorStoreToolkit.toolkit_config_schema()
    ]
    
    community_toolkits = [ 
        AnalyseJira.toolkit_config_schema(),
        BrowserUseToolkit.toolkit_config_schema()
    ]
    
    return  core_toolkits + community_toolkits + alita_toolkits()


def get_tools(tools_list: list, alita_client, llm) -> list:
    prompts = []
    tools = []

    for tool in tools_list:
        if tool['type'] == 'prompt':
            prompts.append([
                int(tool['settings']['prompt_id']),
                int(tool['settings']['prompt_version_id'])
            ])
        elif tool['type'] == 'datasource':
            tools.extend(DatasourcesToolkit.get_toolkit(
                alita_client,
                datasource_ids=[int(tool['settings']['datasource_id'])],
                selected_tools=tool['settings']['selected_tools'],
                toolkit_name=tool.get('toolkit_name', '') or tool.get('name', '')
            ).get_tools())
        elif tool['type'] == 'application' and tool.get('agent_type', '') != 'pipeline' :
            tools.extend(ApplicationToolkit.get_toolkit(
                alita_client,
                application_id=int(tool['settings']['application_id']),
                application_version_id=int(tool['settings']['application_version_id']),
                app_api_key=alita_client.auth_token,
                selected_tools=[]
            ).get_tools())
        elif tool['type'] == 'application' and tool.get('agent_type', '') == 'pipeline':
            # static get_toolkit returns a list of CompiledStateGraph stubs
            tools.extend(SubgraphToolkit.get_toolkit(
                alita_client,
                application_id=int(tool['settings']['application_id']),
                application_version_id=int(tool['settings']['application_version_id']),
                app_api_key=alita_client.auth_token,
                selected_tools=[],
                llm=llm
            ))
        elif tool['type'] == 'artifact':
            tools.extend(ArtifactToolkit.get_toolkit(
                client=alita_client,
                bucket=tool['settings']['bucket'],
                toolkit_name=tool.get('toolkit_name', ''),
                selected_tools=tool['settings'].get('selected_tools', [])
            ).get_tools())
        if tool['type'] == 'analyse_jira':
            tools.extend(AnalyseJira.get_toolkit(
                client=alita_client,
                **tool['settings']).get_tools())
        if tool['type'] == 'browser_use':
            tools.extend(BrowserUseToolkit.get_toolkit(
                client=alita_client,
                llm=llm,
                toolkit_name=tool.get('toolkit_name', ''),
                **tool['settings']).get_tools())
        if tool['type'] == 'vectorstore':
            tools.extend(VectorStoreToolkit.get_toolkit(
                llm=llm,
                toolkit_name=tool.get('toolkit_name', ''),
                **tool['settings']).get_tools())
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita_client, prompts).get_tools()
    tools += alita_tools(tools_list, alita_client, llm)
    tools += _mcp_tools(tools_list, alita_client)
    return tools


def _mcp_tools(tools_list, alita):
    try:
        all_available_toolkits = alita.get_mcp_toolkits()
        toolkit_lookup = {tk["name"].lower(): tk for tk in all_available_toolkits}
        tools = []
        #
        for selected_toolkit in tools_list:
            toolkit_name = selected_toolkit['type'].lower()
            toolkit_conf = toolkit_lookup.get(toolkit_name)
            #
            if not toolkit_conf:
                logger.warning(f"Toolkit '{toolkit_name}' not found in available toolkits.")
                continue
            #
            available_tools = toolkit_conf.get("tools", [])
            selected_tools = [name.lower() for name in selected_toolkit['settings'].get('selected_tools', [])]
            for available_tool in available_tools:
                tool_name = available_tool.get("name", "").lower()
                if not selected_tools or tool_name in selected_tools:
                    if server_tool := _init_single_mcp_tool(toolkit_name, available_tool, alita, selected_toolkit['settings']):
                        tools.append(server_tool)
        return tools
    except Exception:
        logger.error("Error while fetching MCP tools", exc_info=True)
        return []


def _init_single_mcp_tool(toolkit_name, available_tool, alita, toolkit_settings):
    try:
        tool_name = available_tool["name"]
        return McpServerTool(
            name=tool_name,
            description=available_tool.get("description", ""),
            args_schema=McpServerTool.create_pydantic_model_from_schema(
                available_tool.get("inputSchema", {})
            ),
            client=alita,
            server=toolkit_name,
            tool_timeout_sec=toolkit_settings["timeout"]
        )
    except Exception as e:
        logger.error(f"Failed to create McpServerTool for '{toolkit_name}.{tool_name}': {e}")
        return None
