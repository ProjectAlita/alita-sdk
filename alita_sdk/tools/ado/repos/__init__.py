from typing import List, Literal, Optional

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, Field, create_model, SecretStr

from ...base.tool import BaseAction
from .repos_wrapper import ReposApiWrapper
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "ado_repos"


def _get_toolkit(tool) -> BaseToolkit:
    return AzureDevOpsReposToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        organization_url=tool['settings'].get('organization_url', ""),
        project=tool['settings'].get('project', ""),
        token=tool['settings'].get('token', ""),
        limit=tool['settings'].get('limit', 5),
        repository_id=tool['settings'].get('repository_id', ""),
        base_branch=tool['settings'].get('base_branch', ""),
        active_branch=tool['settings'].get('active_branch', ""),
        toolkit_name=tool['settings'].get('toolkit_name', ""),
        connection_string=tool['settings'].get('connection_string', None),
        collection_name=str(tool['id']),
        doctype='code',
        embedding_model="HuggingFaceEmbeddings",
        embedding_model_params={"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        vectorstore_type="PGVector",
    )

def get_toolkit():
    return AzureDevOpsReposToolkit.toolkit_config_schema()

def get_tools(tool):
    return _get_toolkit(tool).get_tools()

class AzureDevOpsReposToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ReposApiWrapper.model_construct().get_available_tools()}
        AzureDevOpsReposToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            organization_url=(Optional[str], Field(default="", title="Organization URL", description="ADO organization url")),
            project=(Optional[str], Field(default="", title="Project", description="ADO project")),
            repository_id=(Optional[str], Field(default="", title="Repository ID", description="ADO repository ID", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': AzureDevOpsReposToolkit.toolkit_max_length})),
            token=(Optional[SecretStr], Field(default="", title="Token", description="ADO token", json_schema_extra={'secret': True})),
            base_branch=(Optional[str], Field(default="", title="Base branch", description="ADO base branch (e.g., main)")),
            active_branch=(Optional[str], Field(default="", title="Active branch", description="ADO active branch (e.g., main)")),

            # indexer settings
            connection_string = (Optional[SecretStr], Field(description="Connection string for vectorstore",
                                                            default=None,
                                                            json_schema_extra={'secret': True})),
            
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={'json_schema_extra': {'metadata':
                {
                    "label": "ADO repos",
                    "icon_url": "ado-repos-icon.svg",
                    "sections": {
                        "auth": {
                            "required": True,
                            "subsections": [
                                {
                                    "name": "Token",
                                    "fields": ["token"]
                                }
                            ]
                        }
                    }
                }}}
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        from os import environ

        if not environ.get("AZURE_DEVOPS_CACHE_DIR", None):
            environ["AZURE_DEVOPS_CACHE_DIR"] = "/tmp/.azure-devops"
        if selected_tools is None:
            selected_tools = []
        
        azure_devops_repos_wrapper = ReposApiWrapper(**kwargs)
        available_tools = azure_devops_repos_wrapper.get_available_tools()
        tools = []
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(
                BaseAction(
                    api_wrapper=azure_devops_repos_wrapper,
                    name=prefix + tool["name"],
                    description=tool["description"] + f"\nADO instance: {azure_devops_repos_wrapper.organization_url}/{azure_devops_repos_wrapper.project}",
                    args_schema=tool["args_schema"],
                )
            )
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
