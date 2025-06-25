from typing import List, Literal, Optional

import requests
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

from .api_wrapper import PostmanApiWrapper
from .tool import PostmanAction
from ..utils import clean_string, get_max_toolkit_length, TOOLKIT_SPLITTER, check_connection_response

name = "elitea_postman"


def get_tools(tool):
    toolkit = PostmanToolkit.get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        api_key=tool['settings'].get('api_key', None),
        base_url=tool['settings'].get(
            'base_url', 'https://api.getpostman.com'),
        collection_id=tool['settings'].get('collection_id', None),
        workspace_id=tool['settings'].get('workspace_id', None),
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
            api_key=(SecretStr, Field(description="Postman API key",
                     json_schema_extra={'secret': True, 'configuration': True})),
            base_url=(str, Field(description="Postman API base URL",
                      default="https://api.getpostman.com", json_schema_extra={'configuration': True})),
            collection_id=(str, Field(description="Default collection ID", json_schema_extra={
                           'toolkit_name': True, 'max_toolkit_length': PostmanToolkit.toolkit_max_length})),
            workspace_id=(str, Field(description="Default workspace ID",
                          default="", json_schema_extra={'configuration': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(
                default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {
                                  "label": "Elitea Postman", "icon_url": "postman.svg"}})
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
        postman_api_wrapper = PostmanApiWrapper(**kwargs)
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
