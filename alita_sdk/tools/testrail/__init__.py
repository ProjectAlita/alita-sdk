from typing import List, Literal, Optional

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import create_model, BaseModel, ConfigDict, Field
import requests

from .api_wrapper import TestrailAPIWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length, check_connection_response
from ...configurations.testrail import TestRailConfiguration
from ...configurations.pgvector import PgVectorConfiguration

name = "testrail"

def get_tools(tool):
    return TestrailToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        url=tool['settings']['url'],
        testrail_configuration=tool['settings']['testrail_configuration'],
        toolkit_name=tool.get('toolkit_name'),
        llm=tool['settings'].get('llm', None),

        # indexer settings
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        collection_name=f"{tool.get('toolkit_name')}",
        embedding_model="HuggingFaceEmbeddings",
        embedding_model_params={"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        vectorstore_type="PGVector"
    ).get_tools()


class TestrailToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in TestrailAPIWrapper.model_construct().get_available_tools()}
        TestrailToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        m = create_model(
            name,
            url=(
                str,
                Field(
                    description="Testrail URL",
                    json_schema_extra={
                        "max_length": TestrailToolkit.toolkit_max_length,
                        "configuration": True,
                        "configuration_title": True
                    }
                )
            ),
            testrail_configuration=(Optional[TestRailConfiguration], Field(description="TestRail Configuration", json_schema_extra={'configuration_types': ['testrail']})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(description="PgVector Configuration", json_schema_extra={'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_model=(str, Field(description="Embedding model: i.e. 'HuggingFaceEmbeddings', etc.", default="HuggingFaceEmbeddings")),
            embedding_model_params=(dict, Field(description="Embedding model parameters: i.e. `{'model_name': 'sentence-transformers/all-MiniLM-L6-v2'}", default={"model_name": "sentence-transformers/all-MiniLM-L6-v2"})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata':
                                                         {"label": "Testrail", "icon_url": "testrail-icon.svg",
                                                          "categories": ["test management"],
                                                          "extra_categories": ["quality assurance", "test case management", "test planning"]
                                                          }})
        )

        @check_connection_response
        def check_connection(self):
            response = requests.get(
                f'{self.url}/index.php?/api/v2/get_projects',
                auth=requests.auth.HTTPBasicAuth(self.email, self.password),
                timeout=5
            )

            return response
        m.check_connection = check_connection
        return m

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use testrail_configuration fields
            **kwargs['testrail_configuration'],
            **(kwargs.get('pgvector_configuration') or {}),
        }
        testrail_api_wrapper = TestrailAPIWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = testrail_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=testrail_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"] + "\nTestrail instance: " + testrail_api_wrapper.url,
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
