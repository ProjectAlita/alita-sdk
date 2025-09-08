from .test_plan import AzureDevOpsPlansToolkit
from .wiki import AzureDevOpsWikiToolkit
from .work_item import AzureDevOpsWorkItemsToolkit

name = "azure_devops"


def get_tools(tool_type, tool):
    config_dict = {
        # common
        "selected_tools": tool['settings'].get('selected_tools', []),
        "ado_configuration": tool['settings']['ado_configuration'],
        "limit": tool['settings'].get('limit', 5),
        "toolkit_name": tool.get('toolkit_name', ''),
        # indexer settings
        "alita": tool['settings'].get('alita', None),
        "llm": tool['settings'].get('llm', None),
        "pgvector_configuration": tool['settings'].get('pgvector_configuration', {}),
        "collection_name": tool['toolkit_name'],
        "doctype": 'doc',
        "embedding_model": tool['settings'].get('embedding_model'),
        "vectorstore_type": "PGVector"
    }
    if tool_type == 'ado_plans':
        return AzureDevOpsPlansToolkit().get_toolkit(**config_dict).get_tools()
    elif tool_type == 'ado_wiki':
        return AzureDevOpsWikiToolkit().get_toolkit(**config_dict).get_tools()
    else:
        return AzureDevOpsWorkItemsToolkit().get_toolkit(**config_dict).get_tools()
