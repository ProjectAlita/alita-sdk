from typing import List, Literal, Optional
from .api_wrapper import GitLabWorkspaceAPIWrapper
from langchain_core.tools import BaseToolkit
from langchain_core.tools import BaseTool
from ..base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from ...configurations.gitlab import GitlabConfiguration

name = "gitlab_org"

def get_tools(tool):
    return AlitaGitlabSpaceToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        gitlab_configuration=tool['settings']['gitlab_configuration'],
        repositories=tool['settings'].get('repositories', ''),
        branch=tool['settings']['branch'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class AlitaGitlabSpaceToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in GitLabWorkspaceAPIWrapper.model_construct().get_available_tools()}
        AlitaGitlabSpaceToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            name=(str, Field(description="Toolkit name", json_schema_extra={'toolkit_name': True,
                                                                            'max_toolkit_length': AlitaGitlabSpaceToolkit.toolkit_max_length})),
            gitlab_configuration=(GitlabConfiguration, Field(description="GitLab configuration",
                                                                       json_schema_extra={
                                                                           'configuration_types': ['gitlab']})),
            repositories=(str, Field(
                description="List of comma separated repositories user plans to interact with. Leave it empty in case you pass it in instruction.",
                default=''
            )),
            branch=(str, Field(description="Main branch", default="main")),
            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "GitLab Org",
                    "icon_url": None,
                    "categories": ["code repositories"],
                    "extra_categories": ["gitlab", "git", "repository", "code", "version control"],
                }
            })
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use gitlab_configuration fields
            **kwargs['gitlab_configuration'],
        }
        gitlab_wrapper = GitLabWorkspaceAPIWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, AlitaGitlabSpaceToolkit.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = gitlab_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=gitlab_wrapper,
                name=prefix + tool['name'],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools