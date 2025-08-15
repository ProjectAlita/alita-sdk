from typing import List, Literal, Optional, Type

import requests
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field, field_validator
from ..base.tool import BaseAction

from .api_wrapper import PostmanApiWrapper
from ..utils import clean_string, get_max_toolkit_length, TOOLKIT_SPLITTER, check_connection_response
from ...configurations.postman import PostmanConfiguration

name = "postman"

class PostmanAction(BaseAction):
    """Tool for interacting with the Postman API."""

    api_wrapper: PostmanApiWrapper = Field(default_factory=PostmanApiWrapper)
    name: str
    mode: str = ""
    description: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return v.replace(' ', '')

def get_tools(tool):
    # Parse environment_config if it's a string (from UI)
    environment_config = tool['settings'].get('environment_config', {})
    toolkit = PostmanToolkit.get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        postman_configuration=tool['settings']['postman_configuration'],
        base_url=tool['settings'].get(
            'base_url', 'https://api.getpostman.com'),
        collection_id=tool['settings'].get('collection_id', None),
        workspace_id=tool['settings'].get('workspace_id', None),
        environment_config=environment_config,
        toolkit_name=tool.get('toolkit_name')
    )
    return toolkit.tools


class PostmanToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema(
        ) for x in PostmanApiWrapper.model_construct().get_available_tools()}
        PostmanToolkit.toolkit_max_length = get_max_toolkit_length(
            selected_tools)
        m = create_model(
            name,
            postman_configuration=(Optional[PostmanConfiguration], Field(description="Postman Configuration",
                                                                         json_schema_extra={'configuration_types': ['postman']})),
            collection_id=(str, Field(description="Default collection ID", json_schema_extra={
                           'toolkit_name': True, 'max_toolkit_length': PostmanToolkit.toolkit_max_length})),
            environment_config=(dict, Field(
                description="JSON configuration for request execution (auth headers, project IDs, base URLs, etc.)",
                default={})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(
                default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {
                                  "label": "Postman", "icon_url": "postman.svg"}})
        )

        @check_connection_response
        def check_connection(self):
            response = requests.get(
                f'{self.base_url}/collections',
                headers={
                    'X-API-Key': self.api_key.get_secret_value(),
                    'Content-Type': 'application/json'
                },
                timeout=5
            )
            return response
        m.check_connection = check_connection
        return m

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use postman_configuration fields
            **kwargs['postman_configuration'],
        }
        postman_api_wrapper = PostmanApiWrapper(**wrapper_payload)
        prefix = clean_string(str(toolkit_name), cls.toolkit_max_length) + \
            TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = postman_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(PostmanAction(
                api_wrapper=postman_api_wrapper,
                name=prefix + tool["name"],
                mode=tool["mode"],
                description=f"{tool['description']}\nAPI URL: {postman_api_wrapper.base_url}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools