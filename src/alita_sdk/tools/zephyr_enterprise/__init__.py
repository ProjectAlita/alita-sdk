from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr
from typing import List, Literal, Optional

from .api_wrapper import ZephyrApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, get_max_toolkit_length, TOOLKIT_SPLITTER

name = "zephyr_enterprise"

def get_tools(tool):
    return ZephyrEnterpriseToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        base_url=tool['settings']['base_url'],
        token=tool['settings']['token'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class ZephyrEnterpriseToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          ZephyrApiWrapper.model_construct().get_available_tools()}
        ZephyrEnterpriseToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            base_url=(str, Field(description="Zephyr Enterprise base URL", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': ZephyrEnterpriseToolkit.toolkit_max_length })),
            token=(SecretStr, Field(description="API token", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], []),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Zephyr Enterprise", "icon_url": "zephyr.svg"}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        zephyr_api_wrapper = ZephyrApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = zephyr_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=zephyr_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"] + "\nZephyr Enterprise instance: " + zephyr_api_wrapper.base_url,
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> List[BaseTool]:
        return self.tools