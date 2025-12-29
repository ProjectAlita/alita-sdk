from typing import List, Optional, Literal
from .api_wrapper import SalesforceApiWrapper
from langchain_core.tools import BaseTool, BaseToolkit
from ..base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field

from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, get_max_toolkit_length
from ...configurations.salesforce import SalesforceConfiguration
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "salesforce"

def get_tools(tool):
    return SalesforceToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        salesforce_configuration=tool['settings']['salesforce_configuration'],
        api_version=tool['settings'].get('api_version', 'v59.0')
    ).get_tools()

class SalesforceToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        available_tools = {x['name']: x['args_schema'].schema() for x in SalesforceApiWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
            api_version=(str, Field(description="Salesforce API Version", default='v59.0')),
            salesforce_configuration=(SalesforceConfiguration, Field(description="Salesforce Configuration", json_schema_extra={'configuration_types': ['salesforce']})),
            selected_tools=(List[Literal[tuple(available_tools)]], Field(default=[], json_schema_extra={'args_schemas': available_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {
                "label": "Salesforce", "icon_url": "salesforce-icon.svg",
                "categories": ["other"],
                "extra_categories": ["customer relationship management", "cloud computing", "marketing automation", "salesforce"]
                                                                  }})
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []

        wrapper_payload = {
            **kwargs,
            **kwargs.get('salesforce_configuration', {}),
        }
        api_wrapper = SalesforceApiWrapper(**wrapper_payload)
        tools = []

        for tool in api_wrapper.get_available_tools():
            if selected_tools and tool["name"] not in selected_tools:
                continue
            description = f"Salesforce Tool: {tool['description']}"
            if toolkit_name:
                description = f"{description}\nToolkit: {toolkit_name}"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))

        return cls(tools=tools)

    def get_tools(self):
        return self.tools
