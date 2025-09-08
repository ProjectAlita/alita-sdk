from typing import Dict, List, Literal, Optional

from requests.auth import HTTPBasicAuth

from .api_wrapper import BitbucketAPIWrapper
from langchain_core.tools import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict, create_model

from ..base.tool import BaseAction
from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length, check_connection_response
from ...configurations.bitbucket import BitbucketConfiguration
from ...configurations.pgvector import PgVectorConfiguration
import requests


name = "bitbucket"


def get_tools(tool):
    return AlitaBitbucketToolkit.get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        project=tool['settings']['project'],
        repository=tool['settings']['repository'],
        bitbucket_configuration=tool['settings']['bitbucket_configuration'],
        branch=tool['settings']['branch'],
        cloud=tool['settings'].get('cloud'),
        llm=tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        collection_name=str(tool['toolkit_name']),
        doctype='code',
        embedding_model=tool['settings'].get('embedding_model'),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class AlitaBitbucketToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          BitbucketAPIWrapper.model_construct().get_available_tools()}
        AlitaBitbucketToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        m = create_model(
            name,
            project=(str, Field(description="Project/Workspace", json_schema_extra={'configuration': True})),
            repository=(str, Field(description="Repository", json_schema_extra={'max_toolkit_length': AlitaBitbucketToolkit.toolkit_max_length, 'configuration': True})),
            branch=(str, Field(description="Main branch", default="main")),
            cloud=(Optional[bool], Field(description="Hosting Option", default=None)),
            bitbucket_configuration=(BitbucketConfiguration, Field(description="Bitbucket Configuration", json_schema_extra={'configuration_types': ['bitbucket']})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(default=None, description="PgVector Configuration", json_schema_extra={'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra=
            {
                'metadata':
                    {
                        "label": "Bitbucket", "icon_url": "bitbucket-icon.svg",
                        "categories": ["code repositories"],
                        "extra_categories": ["bitbucket", "git", "repository", "code", "version control"],
                    }
            })
        )

        @check_connection_response
        def check_connection(self):
            bitbucket_config = self.bitbucket_configuration or {}
            url = bitbucket_config.get('url', '')
            username = bitbucket_config.get('username', '')
            password = bitbucket_config.get('password', '')

            if self.cloud:
                request_url = f"{url}/2.0/repositories/{self.project}/{self.repository}"
            else:
                request_url = f"{url}/rest/api/1.0/projects/{self.project}/repos/{self.repository}"
            response = requests.get(request_url, auth=HTTPBasicAuth(username, password))
            return response

        m.check_connection = check_connection
        return m

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        if kwargs["cloud"] is None:
            kwargs["cloud"] = True if "bitbucket.org" in kwargs.get('url') else False
        wrapper_payload = {
            **kwargs,
            # TODO use bitbucket_configuration fields
            **kwargs['bitbucket_configuration'],
            **(kwargs.get('pgvector_configuration') or {}),
        }
        bitbucket_api_wrapper = BitbucketAPIWrapper(**wrapper_payload)
        available_tools: List[Dict] = bitbucket_api_wrapper.get_available_tools()
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool['name'] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=bitbucket_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"] + f"\nrepo: {bitbucket_api_wrapper.repository}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
