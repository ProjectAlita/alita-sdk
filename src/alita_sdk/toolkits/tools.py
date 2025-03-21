import logging

from alita_tools import get_tools as alita_tools
from alita_tools import get_toolkits as alita_toolkits
from langchain_core.tools import ToolException

from .prompt import PromptToolkit
from .datasource import DatasourcesToolkit
from .application import ApplicationToolkit
from .artifact import ArtifactToolkit
from .vectorstore import VectorStoreToolkit

## Community tools and toolkits
from ..community.eda.jiratookit import AnalyseJira
from ..tools.mcp import McpTool

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
        AnalyseJira.toolkit_config_schema()
    ]

    return  core_toolkits + community_toolkits + alita_toolkits()


def get_tools(tools_list: list, alita: 'AlitaClient', llm: 'LLMLikeObject') -> list:
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
                alita,
                datasource_ids=[int(tool['settings']['datasource_id'])],
                selected_tools=tool['settings']['selected_tools']).get_tools())
        elif tool['type'] == 'application':
            tools.extend(ApplicationToolkit.get_toolkit(
                alita,
                application_id=int(tool['settings']['application_id']),
                application_version_id=int(tool['settings']['application_version_id']),
                app_api_key=alita.auth_token,
                selected_tools=[]
            ).get_tools())
        elif tool['type'] == 'artifact':
            tools.extend(ArtifactToolkit.get_toolkit(
                client=alita,
                bucket=tool['settings']['bucket'],
                selected_tools=tool['settings'].get('selected_tools', [])
            ).get_tools())
        if tool['type'] == 'analyse_jira':
            tools.extend(AnalyseJira.get_toolkit(
                client=alita,
                **tool['settings']).get_tools())
        if tool['type'] == 'vectorstore':
            tools.extend(VectorStoreToolkit.get_toolkit(
                llm=llm,
                **tool['settings']).get_tools())
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita, prompts).get_tools()
    tools += alita_tools(tools_list, alita, llm)
    # add tools from ELITEA APP
    tools += mcp_tools(tools_list)
    return tools

def mcp_tools(tools_list):
    # get available MCP tools from ELITEA APP
    tools = []
    for tool in tools_list:
        toolkit_name = tool['type']
        # get MCP Toolkits from platform
        toolkit = find_toolkit_by_name(toolkit_name)
        # get selected tools from the toolkit
        available_tools = toolkit["tools"]
        selected_tools = tool['settings'].get('selected_tools', [])
        for available_tool in available_tools:
            if not selected_tools or available_tool["name"].lower() in selected_tools:
                # check that tool is available
                tools.append(McpTool(name=available_tool["name"],
                                     description=available_tool["description"],
                                     socket_client=None,
                                     args_schema=McpTool.create_pydantic_model_from_schema(available_tool["inputSchema"])))
    return tools

# TODO: remove after BE
def find_toolkit_by_name(name):
    for toolkit in _available_mcp_toolkits:
        if toolkit["toolkit_name"] == name:
            return toolkit
    raise ToolException(f"MCP Toolkit `{name}` is not available in ELITEA APP")

# TODO: remove after BE
_available_mcp_toolkits = [
    {
        "toolkit_name": "ej-code",
        "tools": [
            {
                "name": "create-message",
                "description": "Generate a custom message with various options",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "messageType": {
                            "type": "string",
                            "enum": [
                                "greeting",
                                "farewell",
                                "thank-you"
                            ],
                            "description": "Type of message to generate"
                        },
                        "recipient": {
                            "type": "string",
                            "description": "Name of the person to address"
                        },
                        "tone": {
                            "type": "string",
                            "enum": [
                                "formal",
                                "casual",
                                "playful"
                            ],
                            "description": "Tone of the message"
                        }
                    },
                    "required": [
                        "messageType",
                        "recipient"
                    ]
                }
            },
            {
                "name": "file_listing",
                "description": "List existing files",
                "inputSchema": {
                     "type": "object",
                     "properties": {
                         "limit": {
                             "type": "integer",
                             "description": "Limit for the number of items"
                         },
                         "validation": {
                             "type": "string",
                             "description": "Validation criteria"
                         }
                     },
                     "required": [
                         "limit",
                         "validation"
                     ]
                 }
            },
        ]
    }
]
