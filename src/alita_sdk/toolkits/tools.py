import logging

from alita_tools import get_tools as alita_tools

from .prompt import PromptToolkit
from .datasource import DatasourcesToolkit
from .application import ApplicationToolkit
from .artifact import ArtifactToolkit

logger = logging.getLogger(__name__)


def get_toolkits():
    return [
        PromptToolkit.toolkit_config_schema(),
        DatasourcesToolkit.toolkit_config_schema(),
        ApplicationToolkit.toolkit_config_schema(),
        ArtifactToolkit.toolkit_config_schema()
    ]


def get_tools(tools_list: list, alita: 'AlitaClient') -> list:
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
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita, prompts).get_tools()
    tools += alita_tools(tools_list)
    return tools
