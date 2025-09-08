from typing import List, Optional, Literal
from .api_wrapper import JiraApiWrapper
from langchain_core.tools import BaseTool, BaseToolkit
from ..base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field
import requests

from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length, parse_list, check_connection_response
from ...configurations.jira import JiraConfiguration
from ...configurations.pgvector import PgVectorConfiguration

name = "jira"

def get_tools(tool):
    return JiraToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        base_url=tool['settings'].get('base_url'),
        cloud=tool['settings'].get('cloud', True),
        api_version=tool['settings'].get('api_version', '2'),
        jira_configuration=tool['settings']['jira_configuration'],
        limit=tool['settings'].get('limit', 5),
        labels=parse_list(tool['settings'].get('labels', [])),
        custom_headers=tool['settings'].get('custom_headers', {}),
        additional_fields=tool['settings'].get('additional_fields', []),
        verify_ssl=tool['settings'].get('verify_ssl', True),
        # indexer settings
        llm=tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        collection_name=str(tool['toolkit_name']),
        embedding_model=tool['settings'].get('embedding_model'),
        vectorstore_type="PGVector",
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()
            

class JiraToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in JiraApiWrapper.model_construct().get_available_tools()}
        JiraToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)

        @check_connection_response
        def check_connection(self):
            jira_config = self.jira_configuration or {}
            base_url = jira_config.get('base_url', '')
            url = base_url.rstrip('/') + '/rest/api/2/myself'
            headers = {'Accept': 'application/json'}
            auth = None
            token = jira_config.get('token')
            username = jira_config.get('username')
            api_key = jira_config.get('api_key')

            if token:
                headers['Authorization'] = f'Bearer {token}'
            elif username and api_key:
                auth = (username, api_key)
            else:
                raise ValueError('Jira connection requires either token or username+api_key')
            response = requests.get(url, headers=headers, auth=auth, timeout=5, verify=getattr(self, 'verify_ssl', True))
            return response

        model = create_model(
            name,
            cloud=(bool, Field(description="Hosting Option", json_schema_extra={'configuration': True})),
            limit=(int, Field(description="Limit issues. Default is 5", gt=0, default=5)),
            api_version=(Optional[str], Field(description="Rest API version: optional. Default is 2", default="2")),
            labels=(Optional[str], Field(
                description="List of comma separated labels used for labeling of agent's created or updated entities",
                default=None,
                examples="alita,elitea;another-label"
            )),
            # optional field for custom headers as dictionary
            custom_headers=(Optional[dict], Field(description="Custom headers for API requests", default={})),
            verify_ssl=(bool, Field(description="Verify SSL", default=True)),
            additional_fields=(Optional[str], Field(description="Additional fields", default="")),
            jira_configuration=(JiraConfiguration, Field(description="Jira Configuration", json_schema_extra={'configuration_types': ['jira']})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(default=None,
                                                                           description="PgVector Configuration", json_schema_extra={'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),

            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Jira",
                    "icon_url": "jira-icon.svg",
                    "categories": ["project management"],
                    "extra_categories": ["jira", "atlassian", "issue tracking", "project management", "task management"],
                }
            })
        )
        model.check_connection = check_connection
        return model

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use jira_configuration fields
            **kwargs['jira_configuration'],
            **(kwargs.get('pgvector_configuration') or {}),
        }
        jira_api_wrapper = JiraApiWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = jira_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=jira_api_wrapper,
                name=prefix + tool["name"],
                description=f"Tool for Jira: '{jira_api_wrapper.base_url}'\n{tool['description']}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
