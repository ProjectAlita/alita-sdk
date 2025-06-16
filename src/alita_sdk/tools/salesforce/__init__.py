from typing import List, Optional, Literal
from .api_wrapper import SalesforceApiWrapper
from langchain_core.tools import BaseTool, BaseToolkit
from ..base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr
from ..utils import clean_string, TOOLKIT_SPLITTER,get_max_toolkit_length

name = "salesforce"

def get_tools(tool):
    return SalesforceToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        base_url=tool['settings'].get('base_url'),
        client_id=tool['settings'].get('client_id'),
        client_secret=tool['settings'].get('client_secret'),
        api_version=tool['settings'].get('api_version', 'v59.0')
    ).get_tools()

class SalesforceToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        available_tools = {x['name']: x['args_schema'].schema() for x in SalesforceApiWrapper.model_construct().get_available_tools()}
        SalesforceToolkit.toolkit_max_length = get_max_toolkit_length(available_tools)
        return create_model(
            name,
            base_url=(str, Field(description="Salesforce instance URL", json_schema_extra={'toolkit_name': True})),
            client_id=(str, Field(description="Salesforce Connected App Client ID")),
            client_secret=(SecretStr, Field(description="Salesforce Connected App Client Secret", json_schema_extra={'secret': True})),
            api_version=(str, Field(description="Salesforce API Version", default='v59.0')),
            selected_tools=(List[Literal[tuple(available_tools)]], Field(default=[], json_schema_extra={'args_schemas': available_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Salesforce", "icon_url": "salesforce-icon.svg"}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []

        api_wrapper = SalesforceApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        tools = []

        for tool in api_wrapper.get_available_tools():
            if selected_tools and tool["name"] not in selected_tools:
                continue

            tools.append(BaseAction(
                api_wrapper=api_wrapper,
                name=prefix + tool["name"],
                description=f"Salesforce Tool: {tool['description']}",
                args_schema=tool["args_schema"]
            ))

        return cls(tools=tools)

    def get_tools(self):
        return self.tools
