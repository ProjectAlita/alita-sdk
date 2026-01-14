from typing import List, Literal, Optional
from .ado_wrapper import AzureDevOpsApiWrapper  # Import the API wrapper for Azure DevOps
from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import create_model, BaseModel, Field

import requests

from ...elitea_base import filter_missconfigured_index_tools
from ....configurations.ado import AdoConfiguration
from ....configurations.pgvector import PgVectorConfiguration
from ...base.tool import BaseAction
from ...utils import clean_string, get_max_toolkit_length, check_connection_response
from ....runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "azure_devops_wiki"
name_alias = 'ado_wiki'

def get_toolkit(tool):
    return AzureDevOpsWikiToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        ado_configuration=tool['settings']['ado_configuration'],
        limit=tool['settings'].get('limit', 5),
        toolkit_name=tool.get('toolkit_name', ''),
        alita=tool['settings'].get('alita', None),
        llm=tool['settings'].get('llm', None),
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        collection_name=tool['toolkit_name'],
        doctype='doc',
        embedding_model=tool['settings'].get('embedding_model'),
        vectorstore_type="PGVector"
    )

class AzureDevOpsWikiToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in AzureDevOpsApiWrapper.model_construct().get_available_tools()}
        m = create_model(
            name_alias,
            ado_configuration=(AdoConfiguration, Field(description="Ado configuration", json_schema_extra={'configuration_types': ['ado']})),
            # indexer settings
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(default=None,
                                                                           description="PgVector Configuration", json_schema_extra={'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),
            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={
                'json_schema_extra': {
                    'metadata': {
                        "label": "ADO wiki",
                        "icon_url": "ado-wiki-icon.svg",
                        "categories": ["documentation"],
                        "extra_categories": ["knowledge base", "documentation management", "wiki"],
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
                        },
                        "configuration_group": {
                            "name": "ado",
                        }
                    }
                }
            }
        )

        @check_connection_response
        def check_connection(self):
            ado_config = self.ado_wiki_configuration.ado_configuration if self.ado_wiki_configuration else None
            if not ado_config:
                raise ValueError("ADO wiki configuration is required")
            response = requests.get(
                f'{ado_config.organization_url}/{ado_config.project}/_apis/wiki/wikis?api-version=7.0',
                headers={'Authorization': f'Bearer {ado_config.token}'},
                timeout=5
            )
            return response

        m.check_connection = check_connection
        return m

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        from os import environ
        if not environ.get('AZURE_DEVOPS_CACHE_DIR', None):
            environ['AZURE_DEVOPS_CACHE_DIR'] = '/tmp/.azure-devops'
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use ado_configuration fields in AzureDevOpsApiWrapper
            **kwargs['ado_configuration'],
            **(kwargs.get('pgvector_configuration') or {}),
        }
        azure_devops_api_wrapper = AzureDevOpsApiWrapper(**wrapper_payload)
        available_tools = azure_devops_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            description = tool["description"] + f"\nADO instance: {azure_devops_api_wrapper.organization_url}/{azure_devops_api_wrapper.project}"
            if toolkit_name:
                description = f"{description}\nToolkit: {toolkit_name}"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=azure_devops_api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
