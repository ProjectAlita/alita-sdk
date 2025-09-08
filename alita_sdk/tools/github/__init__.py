from typing import Dict, List, Optional, Literal

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import create_model, BaseModel, ConfigDict, Field

from .api_wrapper import AlitaGitHubAPIWrapper
from .tool import GitHubAction
from ..elitea_base import filter_missconfigured_index_tools

from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from ...configurations.github import GithubConfiguration
from ...configurations.pgvector import PgVectorConfiguration

name = "github"

def _get_toolkit(tool) -> BaseToolkit:
    return AlitaGitHubToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        github_base_url=tool['settings'].get('base_url', ''),
        github_repository=tool['settings']['repository'],
        active_branch=tool['settings']['active_branch'],
        github_base_branch=tool['settings']['base_branch'],
        github_configuration=tool['settings']['github_configuration'],
        llm=tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        collection_name=str(tool['toolkit_name']),
        doctype='code',
        embedding_model=tool['settings'].get('embedding_model'),
        vectorstore_type="PGVector",
        toolkit_name=tool.get('toolkit_name')
    )

def get_toolkit():
    return AlitaGitHubToolkit.toolkit_config_schema()

def get_tools(tool):
    return _get_toolkit(tool).get_tools()

class AlitaGitHubToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          AlitaGitHubAPIWrapper.model_construct().get_available_tools()}
        AlitaGitHubToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            __config__=ConfigDict(
                json_schema_extra={
                    'metadata': {
                        "label": "GitHub",
                        "icon_url": None,
                        "categories": ["code repositories"],
                        "extra_categories": ["github", "git", "repository", "code", "version control"],
                    },
                }
            ),
            github_configuration=(GithubConfiguration, Field(description="Github configuration",
                                                             json_schema_extra={'configuration_types': ['github']})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(description="PgVector configuration", default=None,
                                                                     json_schema_extra={'configuration_types': ['pgvector']})),
            repository=(str, Field(description="Github repository", json_schema_extra={'toolkit_name': True,
                                                                                       'max_toolkit_length': AlitaGitHubToolkit.toolkit_max_length})),
            active_branch=(Optional[str], Field(description="Active branch", default="main")),
            base_branch=(Optional[str], Field(description="Github Base branch", default="main")),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),
            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools}))
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use github_configuration fields
            **kwargs['github_configuration'],
            **(kwargs.get('pgvector_configuration') or {}),
            **(kwargs.get('embedding_configuration') or {}),
        }
        github_api_wrapper = AlitaGitHubAPIWrapper(**wrapper_payload)
        available_tools: List[Dict] = github_api_wrapper.get_available_tools()
        tools = []
        prefix = clean_string(toolkit_name, AlitaGitHubToolkit.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(GitHubAction(
                api_wrapper=github_api_wrapper,
                name=prefix + tool["name"],
                mode=tool["mode"],
                # set unique description for declared tools to differentiate the same methods for different toolkits
                description=f"Repository: {github_api_wrapper.github_repository}\n" + tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
