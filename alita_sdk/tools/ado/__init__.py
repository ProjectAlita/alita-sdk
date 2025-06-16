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
    }
    if tool_type == 'ado_plans':
        return AzureDevOpsPlansToolkit().get_toolkit(**config_dict).get_tools()
    elif tool_type == 'ado_wiki':
        return AzureDevOpsWikiToolkit().get_toolkit(**config_dict).get_tools()
    else:
        return AzureDevOpsWorkItemsToolkit().get_toolkit(**config_dict).get_tools()
