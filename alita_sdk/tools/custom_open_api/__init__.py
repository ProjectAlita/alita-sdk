from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field

from .api_wrapper import OpenApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER

name = "openapi"


def get_tools(tool):
    return OpenApiToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        spec=tool['settings'].get('spec', ''),
        api_key=tool['settings'].get('api_key', ''),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class OpenApiToolkit(BaseToolkit):
    tools: list[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in OpenApiWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
            spec=(str, Field(default="", title="Specification", description="OpenAPI specification")),
            api_key=(str, Field(default="", title="API key", description="API key", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata':
                                                         {"label": "OpenAPI", "icon_url": None,
                                                          "categories": ["testing"],
                                                          "extra_categories": [ "openapi", "swagger"]}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        openapi_api_wrapper = OpenApiWrapper(**kwargs)
        available_tools = openapi_api_wrapper.get_available_tools()
        tools = []
        prefix = clean_string(toolkit_name + TOOLKIT_SPLITTER) if toolkit_name else ''
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=openapi_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools