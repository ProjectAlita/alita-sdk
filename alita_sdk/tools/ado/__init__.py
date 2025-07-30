from .test_plan import AzureDevOpsPlansToolkit
from .wiki import AzureDevOpsWikiToolkit
from .work_item import AzureDevOpsWorkItemsToolkit

name = "azure_devops"


def get_tools(tool_type, tool):
    config_dict = {
        # common
        "selected_tools": tool['settings'].get('selected_tools', []),
        "organization_url": tool['settings']['organization_url'],
        "project": tool['settings'].get('project', None),
        "token": tool['settings'].get('token', None),
        "limit": tool['settings'].get('limit', 5),
        "toolkit_name": tool.get('toolkit_name', ''),
        # indexer settings
        "llm":tool['settings'].get('llm', None),
        "connection_string":tool['settings'].get('connection_string', None),
        "collection_name":str(tool['id']),
        "doctype":'doc',
        "embedding_model":"HuggingFaceEmbeddings",
        "embedding_model_params":{"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        "vectorstore_type":"PGVector"
    }
    if tool_type == 'ado_plans':
        return AzureDevOpsPlansToolkit().get_toolkit(**config_dict).get_tools()
    elif tool_type == 'ado_wiki':
        return AzureDevOpsWikiToolkit().get_toolkit(**config_dict).get_tools()
    else:
        return AzureDevOpsWorkItemsToolkit().get_toolkit(**config_dict).get_tools()
