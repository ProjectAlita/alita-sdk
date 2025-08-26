from typing import List, Literal, Optional
from langchain_community.agent_toolkits.base import BaseToolkit
from .api_wrapper import ConfluenceAPIWrapper
from langchain_core.tools import BaseTool
from ..base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length, parse_list, check_connection_response
from ...configurations.confluence import ConfluenceConfiguration
from ...configurations.pgvector import PgVectorConfiguration
import requests

name = "confluence"

def get_tools(tool):
    return ConfluenceToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        base_url=tool['settings']['base_url'],
        space=tool['settings'].get('space', None),
        cloud=tool['settings'].get('cloud', True),
        confluence_configuration=tool['settings']['confluence_configuration'],
        limit=tool['settings'].get('limit', 5),
        labels=parse_list(tool['settings'].get('labels', None)),
        custom_headers=tool['settings'].get('custom_headers', {}),
        additional_fields=tool['settings'].get('additional_fields', []),
        verify_ssl=tool['settings'].get('verify_ssl', True),
        alita=tool['settings'].get('alita'),
        llm=tool['settings'].get('llm', None),
        toolkit_name=tool.get('toolkit_name'),
        # indexer settings
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        collection_name=str(tool['toolkit_name']),
        doctype='doc',
        embedding_model=tool['settings'].get('embedding_model'),
        vectorstore_type="PGVector"
    ).get_tools()


class ConfluenceToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          ConfluenceAPIWrapper.model_construct().get_available_tools()}
        ConfluenceToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)

        @check_connection_response
        def check_connection(self):
            url = self.base_url.rstrip('/') + '/wiki/rest/api/space'
            headers = {'Accept': 'application/json'}
            auth = None
            confluence_config = self.confluence_configuration or {}
            token = confluence_config.get('token')
            username = confluence_config.get('username')
            api_key = confluence_config.get('api_key')

            if token:
                headers['Authorization'] = f'Bearer {token}'
            elif username and api_key:
                auth = (username, api_key)
            else:
                raise ValueError('Confluence connection requires either token or username+api_key')
            response = requests.get(url, headers=headers, auth=auth, timeout=5, verify=getattr(self, 'verify_ssl', True))
            return response

        model = create_model(
            name,
            space=(str, Field(description="Space", json_schema_extra={'toolkit_name': True,
                                                                                    'max_toolkit_length': ConfluenceToolkit.toolkit_max_length})),
            cloud=(bool, Field(description="Hosting Option", json_schema_extra={'configuration': True})),
            limit=(int, Field(description="Pages limit per request", default=5)),
            labels=(Optional[str], Field(
                description="List of comma separated labels used for labeling of agent's created or updated entities",
                default=None,
                examples="alita,elitea;another-label"
            )),
            max_pages=(int, Field(description="Max total pages", default=10)),
            number_of_retries=(int, Field(description="Number of retries", default=2)),
            min_retry_seconds=(int, Field(description="Min retry, sec", default=10)),
            max_retry_seconds=(int, Field(description="Max retry, sec", default=60)),
            # optional field for custom headers as dictionary
            custom_headers=(Optional[dict], Field(description="Custom headers for API requests", default=None)),
            confluence_configuration=(ConfluenceConfiguration, Field(description="Confluence Configuration", json_schema_extra={'configuration_types': ['confluence']})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(default = None,
                                                                           description="PgVector Configuration",
                                                                           json_schema_extra={'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),

            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Confluence",
                    "icon_url": None,
                    "categories": ["documentation"],
                    "extra_categories": ["confluence", "wiki", "knowledge base", "documentation", "atlassian"]
                }
            })
        )
        model.check_connection = check_connection
        return model

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use confluence_configuration fields
            **kwargs['confluence_configuration'],
            **(kwargs.get('pgvector_configuration') or {}),
        }
        confluence_api_wrapper = ConfluenceAPIWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, ConfluenceToolkit.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = confluence_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=confluence_api_wrapper,
                name=prefix + tool["name"],
                description=f"Confluence space: {confluence_api_wrapper.space}" + tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
