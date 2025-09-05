from logging import getLogger
from typing import List, Optional, Literal
from .api_wrapper import AzureSearchApiWrapper
from ...base.tool import BaseAction
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field

from ...elitea_base import filter_missconfigured_index_tools
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length, check_connection_response
from ....configurations.azure_search import AzureSearchConfiguration
import requests

logger = getLogger(__name__)

name = "azure_search"

def get_tools(tool):
    return AzureSearchToolkit().get_toolkit(
            selected_tools=tool['settings'].get('selected_tools', []),
            azure_search_configuration=tool['settings']['azure_search_configuration'],
            index_name=tool['settings'].get('index_name', None),
            api_version=tool['settings'].get('api_version', None),
            openai_api_key=tool['settings'].get('access_token', None),
            model_name=tool['settings'].get('model_name', None),
            toolkit_name=tool.get('toolkit_name')
            ).get_tools()
    
def get_toolkit():
    return AzureSearchToolkit.toolkit_config_schema()


class AzureSearchToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in AzureSearchApiWrapper.model_construct().get_available_tools()}
        AzureSearchToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        m = create_model(
            name,
            index_name=(str, Field(description="Azure Search index name")),
            azure_search_configuration=(
                AzureSearchConfiguration,
                Field(description="Azure Search Configuration", json_schema_extra={'configuration_types': ['azure_search']})
            ),
            api_version=(Optional[str], Field(description="API version", default=None)),
            openai_api_key=(Optional[str], Field(description="Azure OpenAI API Key", default=None, json_schema_extra={'secret': True})),
            model_name=(str, Field(description="Model name for Embeddings model", default=None)),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Azure Search", "icon_url": None, "hidden": True,
                    "categories": ["other"],
                    "extra_categories": ["azure cognitive search", "vector database", "knowledge base"]
                }
            })
        )

        @check_connection_response
        def check_connection(self):
            response = requests.get(f"{self.api_base}/openai/deployments", headers={
                "api-key": self.api_key
            })
            return response

        m.check_connection = check_connection
        return m

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use azure_search_configuration fields
            **kwargs['azure_search_configuration'],
        }
        azure_search_api_wrapper = AzureSearchApiWrapper(**wrapper_payload)
        available_tools = azure_search_api_wrapper.get_available_tools()
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=azure_search_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
