from typing import List, Literal, Optional

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, ConfigDict, Field, create_model, SecretStr

from ..base.tool import BaseAction
from .api_wrapper import FigmaApiWrapper, GLOBAL_LIMIT
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "figma"

def get_tools(tool):
    return (
        FigmaToolkit()
        .get_toolkit(
            selected_tools=tool["settings"].get("selected_tools", []),
            token=tool["settings"].get("token", None),
            oauth2=tool["settings"].get("oauth2", None),
            global_limit=tool["settings"].get("global_limit", GLOBAL_LIMIT),
            global_regexp=tool["settings"].get("global_regexp", None),
            toolkit_name=tool.get('toolkit_name')
        )
        .get_tools()
    )


class FigmaToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {
            x["name"]: x["args_schema"].schema()
            for x in FigmaApiWrapper.model_construct().get_available_tools()
        }
        FigmaToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            token=(Optional[SecretStr], Field(description="Figma Token", json_schema_extra={"secret": True}, default=None)),
            oauth2=(Optional[SecretStr], Field(description="OAuth2 Token", json_schema_extra={"secret": True}, default=None)),
            global_limit=(Optional[int], Field(description="Global limit", default=GLOBAL_LIMIT)),
            global_regexp=(Optional[str], Field(description="Global regex pattern", default=None)),
            selected_tools=(
                List[Literal[tuple(selected_tools)]],
                Field(default=[], json_schema_extra={"args_schemas": selected_tools}),
            ),
            __config__=ConfigDict(
                json_schema_extra={
                     "metadata": {
                         "label": "Figma",
                         "icon_url": "figma-icon.svg",
                         "max_length": FigmaToolkit.toolkit_max_length,
                         "sections": {
                             "auth": {
                                 "required": True,
                                 "subsections": [
                                     {
                                         "name": "Token",
                                         "fields": ["token"]
                                     },
                                     {
                                         "name": "Oath2",
                                         "fields": ["oauth2"]
                                     }
                                 ]
                             }
                         }
                     }
                 }
            ),
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        figma_api_wrapper = FigmaApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = figma_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(
                BaseAction(
                    api_wrapper=figma_api_wrapper,
                    name=prefix + tool["name"],
                    description=tool["description"],
                    args_schema=tool["args_schema"],
                )
            )
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
