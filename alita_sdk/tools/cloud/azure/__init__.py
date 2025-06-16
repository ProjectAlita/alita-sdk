from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

from .api_wrapper import AzureApiWrapper
from ...base.tool import BaseAction
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "azure"

def get_tools(tool):
    return AzureToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        subscription_id=tool['settings'].get('subscription_id', ''),
        tenant_id=tool['settings'].get('tenant_id', ''),
        client_id=tool['settings'].get('client_id', ''),
        client_secret=tool['settings'].get('client_secret', ''),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class AzureToolkit(BaseToolkit):
    tools: list[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in AzureApiWrapper.model_construct().get_available_tools()}
        AzureToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            subscription_id=(str, Field(default="", title="Subscription ID", description="Azure subscription ID")),
            tenant_id=(str, Field(default="", title="Tenant ID", description="Azure tenant ID")),
            client_id=(str, Field(default="", title="Client ID", description="Azure client ID")),
            client_secret=(SecretStr, Field(default="", title="Client secret", description="Azure client secret", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Cloud Azure", "icon_url": "azure-icon.svg", "hidden": True}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        azure_api_wrapper = AzureApiWrapper(**kwargs)
        available_tools = azure_api_wrapper.get_available_tools()
        tools = []
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=azure_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools