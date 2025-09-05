from typing import List, Optional, Literal

import logging

from ..elitea_base import filter_missconfigured_index_tools
from ...configurations.slack import SlackConfiguration

logger = logging.getLogger(__name__)

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, Field
from ..base.tool import BaseAction

from .api_wrapper import SlackApiWrapper
from ..utils import TOOLKIT_SPLITTER, clean_string, get_max_toolkit_length, check_connection_response
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient

name = "slack"

def get_tools(tool):
    return SlackToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        slack_configuration=tool['settings']['slack_configuration'],
        channel_id=tool['settings'].get('channel_id'),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class SlackToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
         selected_tools = {x['name']: x['args_schema'].schema() for x in SlackApiWrapper.model_construct().get_available_tools()}
         SlackToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)

         @check_connection_response
         def check_connection(self):
            """
            Checks the connection to Slack using the provided token.
            Returns the response from Slack's auth.test endpoint.
            """
            try:
                response = WebClient(token=self.slack_token.get_secret_value()).auth_test()
                logger.info("Slack connection successful: %s", response)
                return {"success": True, "response": response}
            except SlackApiError as e:
                logger.error(f"Slack connection failed: {e.response['error']}")
                return {"success": False, "error": e.response['error']}

         model = create_model(
             name,
             slack_configuration=(SlackConfiguration, Field(default=None, description="Slack configuration",
                                                             json_schema_extra={'configuration_types': ['slack']})),
             selected_tools=(List[Literal[tuple(selected_tools)]],
                             Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
             __config__={'json_schema_extra': {
                'metadata': {
                    "label": "Slack",
                    "icon_url": "slack-icon.svg",
                    "categories": ["communication"],
                    "extra_categories": ["slack", "chat", "messaging", "collaboration"],
                }
            }}
         )
         model.check_connection = check_connection
         return model

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: Optional[List[str]] = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use slack_configuration fields
            **kwargs['slack_configuration'],
        }
        slack_api_wrapper = SlackApiWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = slack_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(                
                api_wrapper=slack_api_wrapper,
                name=prefix + tool["name"],
                description=f"Slack Tool: {tool['description']}",
                args_schema=tool["args_schema"],
            ))
        return cls(tools=tools)

    def get_tools(self) -> List[BaseTool]:
        return self.tools
