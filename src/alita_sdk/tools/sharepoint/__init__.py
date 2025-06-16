from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr
from .api_wrapper import SharepointApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "sharepoint"

def get_tools(tool):
    return (SharepointToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        site_url=tool['settings'].get('site_url', None),
        client_id=tool['settings'].get('client_id', None),
        client_secret=tool['settings'].get('client_secret', None),
        toolkit_name=tool.get('toolkit_name'))
            .get_tools())


class SharepointToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in SharepointApiWrapper.model_construct().get_available_tools()}
        SharepointToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            site_url=(str, Field(description="Sharepoint site's URL", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': SharepointToolkit.toolkit_max_length})),
            client_id=(str, Field(description="Client ID")),
            client_secret=(SecretStr, Field(description="Client Secret", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Sharepoint", "icon_url": "sharepoint.svg"}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        sharepoint_api_wrapper = SharepointApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = sharepoint_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=sharepoint_api_wrapper,
                name=prefix + tool["name"],
                description=f"Sharepoint {sharepoint_api_wrapper.site_url}\n{tool['description']}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
