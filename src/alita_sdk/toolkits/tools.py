import logging

from alita_tools import get_toolkits as alita_toolkits
from alita_tools import get_tools as alita_tools

from .application import ApplicationToolkit
from .artifact import ArtifactToolkit
from .datasource import DatasourcesToolkit
from .vectorstore import VectorStoreToolkit
## Community tools and toolkits
from ..community.eda.jiratookit import AnalyseJira

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
    tools = []
    for tool in tools_list:
        if tool['type'] == 'datasource':
            tools.extend(DatasourcesToolkit.get_toolkit(
                alita,
                datasource_ids=[int(tool['settings']['datasource_id'])],
                selected_tools=tool['settings']['selected_tools'],
                toolkit_name=tool.get('toolkit_name', '')
            ).get_tools())
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
                toolkit_name=tool.get('toolkit_name', ''),
                selected_tools=tool['settings'].get('selected_tools', [])
            ).get_tools())
        if tool['type'] == 'analyse_jira':
            tools.extend(AnalyseJira.get_toolkit(
                client=alita, 
                **tool['settings']).get_tools())
        if tool['type'] == 'vectorstore':
            tools.extend(VectorStoreToolkit.get_toolkit(
                llm=llm,
                toolkit_name=tool.get('toolkit_name', ''),
                **tool['settings']).get_tools())
    tools += alita_tools(tools_list, alita, llm)
    return tools
