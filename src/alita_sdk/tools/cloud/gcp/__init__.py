from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

from .api_wrapper import GCPApiWrapper
from ...base.tool import BaseAction
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "gcp"

def get_tools(tool):
    return GCPToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        api_key=tool['settings'].get('api_key', ''),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class GCPToolkit(BaseToolkit):
    tools: list[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in GCPApiWrapper.model_construct().get_available_tools()}
        GCPToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            api_key=(SecretStr, Field(default="", title="API key", description="GCP API key", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Cloud GCP", "icon_url": "google.svg", "hidden": True}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        gcp_api_wrapper = GCPApiWrapper(**kwargs)
        available_tools = gcp_api_wrapper.get_available_tools()
        tools = []
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=gcp_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools