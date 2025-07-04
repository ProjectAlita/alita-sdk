from typing import List, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, Field, SecretStr
from ..base.tool import BaseAction

from .api_wrapper import SlackApiWrapper
from ..utils import TOOLKIT_SPLITTER, clean_string, get_max_toolkit_length

name = "slack"

def get_tools(tool):
    return SlackToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        slack_token=tool['settings'].get('slack_token'),
        channel_id=tool['settings'].get('channel_id'),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class SlackToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
         selected_tools = {x['name']: x['args_schema'].schema() for x in SlackApiWrapper.model_construct().get_available_tools()}
         SlackToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
         return create_model(
            name,
            slack_token=(SecretStr, Field( description="Slack Bot/User OAuth Token like XOXB-*****-*****-*****-*****")),
            channel_id=(str, Field(title="Channel ID", description="Channel ID, user ID, or conversation ID to send the message to. (like C12345678 for public channels, D12345678 for DMs)")),
            selected_tools=(list[str], Field(title="Selected Tools", description="List of tools to enable", default=[])),
             __config__={'json_schema_extra': {'metadata': {"label": "slack", "icon_url": None, "hidden": True}}}
        )

    @classmethod
    def get_toolkit(cls, selected_tools: Optional[List[str]] = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        slack_api_wrapper = SlackApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = slack_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(                
                api_wrapper=slack_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"],
                func=tool["ref"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> List[BaseTool]:
        return self.tools

