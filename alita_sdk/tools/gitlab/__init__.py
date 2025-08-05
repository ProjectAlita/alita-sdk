from typing import Dict, List, Literal, Optional

from alita_sdk.tools.base.tool import BaseAction
from langchain_core.tools import BaseTool
from langchain_core.tools import BaseToolkit
from pydantic import create_model, BaseModel, ConfigDict, SecretStr
from pydantic.fields import Field

from .api_wrapper import GitLabAPIWrapper
# from .tools import __all__
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "gitlab"


def get_tools(tool):
    return AlitaGitlabToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        url=tool['settings']['url'],
        repository=tool['settings']['repository'],
        branch=tool['settings']['branch'],
        private_token=tool['settings']['private_token'],

        llm=tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),
        connection_string=tool['settings'].get('connection_string', None),
        collection_name=f"{tool.get('toolkit_name')}_{str(tool['id'])}",
        doctype='code',
        embedding_model="HuggingFaceEmbeddings",
        embedding_model_params={"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        vectorstore_type="PGVector",
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class AlitaGitlabToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          GitLabAPIWrapper.model_construct().get_available_tools()}
        AlitaGitlabToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            url=(str, Field(description="GitLab URL", json_schema_extra={'configuration': True, 'configuration_title': True})),
            repository=(str, Field(description="GitLab repository", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': AlitaGitlabToolkit.toolkit_max_length})),
            private_token=(SecretStr, Field(description="GitLab private token", json_schema_extra={'secret': True, 'configuration': True})),
            branch=(str, Field(description="Main branch", default="main")),
            # indexer settings
            connection_string=(Optional[SecretStr], Field(description="Connection string for vectorstore",
                                                          default=None,
                                                          json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "GitLab",
                    "icon_url": None,
                    "sections": {
                        "auth": {
                            "required": True,
                            "subsections": [
                                {
                                    "name": "GitLab private token",
                                    "fields": ["private_token"]
                                }
                            ]
                        }
                    },
                    "categories": ["code repositories"],
                    "extra_categories": ["gitlab", "git", "repository", "code", "version control"],
                }
            })
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        gitlab_api_wrapper = GitLabAPIWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools: List[Dict] = gitlab_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue

            tools.append(BaseAction(
                api_wrapper=gitlab_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"] +  f"\nrepo: {gitlab_api_wrapper.repository}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self)-> List[BaseTool]:
        return self.tools