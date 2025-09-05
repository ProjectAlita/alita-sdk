from typing import List, Literal, Optional

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, Field, create_model

import requests

from ...elitea_base import filter_missconfigured_index_tools
from ....configurations.ado import AdoReposConfiguration
from ....configurations.pgvector import PgVectorConfiguration
from ...base.tool import BaseAction
from .repos_wrapper import ReposApiWrapper
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length, check_connection_response

name = "ado_repos"


def _get_toolkit(tool) -> BaseToolkit:
    return AzureDevOpsReposToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        ado_repos_configuration=tool['settings']['ado_repos_configuration'],
        limit=tool['settings'].get('limit', 5),
        base_branch=tool['settings'].get('base_branch', ""),
        active_branch=tool['settings'].get('active_branch', ""),
        toolkit_name=tool['settings'].get('toolkit_name', ""),
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        embedding_model=tool['settings'].get('embedding_model'),
        collection_name=tool['toolkit_name'],
        alita=tool['settings'].get('alita', None),
        llm=tool['settings'].get('llm', None),
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
        m = create_model(
            name,
            ado_repos_configuration=(AdoReposConfiguration, Field(description="Ado Repos configuration", default=None,
                                                                       json_schema_extra={'configuration_types': ['ado_repos']})),
            base_branch=(Optional[str], Field(default="", title="Base branch", description="ADO base branch (e.g., main)")),
            active_branch=(Optional[str], Field(default="", title="Active branch", description="ADO active branch (e.g., main)")),

            # indexer settings
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(default=None, description="PgVector Configuration", json_schema_extra={'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),

            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={'json_schema_extra': {'metadata':
                {
                    "label": "ADO repos",
                    "icon_url": "ado-repos-icon.svg",
                    "categories": ["code repositories"],
                    "extra_categories": ["code", "repository", "version control"],
                }}}
        )

        @check_connection_response
        def check_connection(self):
            response = requests.get(
                f'{self.organization_url}/{self.project}/_apis/git/repositories/{self.repository_id}?api-version=7.0',
                headers = {'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            return response

        m.check_connection = check_connection
        return m

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        from os import environ

        if not environ.get("AZURE_DEVOPS_CACHE_DIR", None):
            environ["AZURE_DEVOPS_CACHE_DIR"] = "/tmp/.azure-devops"
        if selected_tools is None:
            selected_tools = []

        wrapper_payload = {
            **kwargs,
            # TODO use ado_repos_configuration fields
            **kwargs['ado_repos_configuration'],
            **kwargs['ado_repos_configuration']['ado_configuration'],
            **(kwargs.get('pgvector_configuration') or {}),
        }
        azure_devops_repos_wrapper = ReposApiWrapper(**wrapper_payload)
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
