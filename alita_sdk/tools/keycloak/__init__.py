from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, ConfigDict, create_model, Field, SecretStr

from .api_wrapper import KeycloakApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, get_max_toolkit_length
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "keycloak"

def get_tools(tool):
    return KeycloakToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        base_url=tool['settings'].get('base_url', ''),
        realm=tool['settings'].get('realm', ''),
        client_id=tool['settings'].get('client_id', ''),
        client_secret=tool['settings'].get('client_secret', ''),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class KeycloakToolkit(BaseToolkit):
    tools: list[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in KeycloakApiWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
            base_url=(str, Field(default="", title="Server URL", description="Keycloak server URL", json_schema_extra={'toolkit_name': True})),
            realm=(str, Field(default="", title="Realm", description="Keycloak realm")),
            client_id=(str, Field(default="", title="Client ID", description="Keycloak client ID")),
            client_secret=(SecretStr, Field(default="", title="Client sercet", description="Keycloak client secret", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Keycloak", "icon_url": None, "hidden": True, "categories": ["authentication", "identity management"]}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None ,**kwargs):
        if selected_tools is None:
            selected_tools = []
        keycloak_api_wrapper = KeycloakApiWrapper(**kwargs)
        available_tools = keycloak_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            description = f"{tool['description']}\nUrl: {keycloak_api_wrapper.base_url}"
            if toolkit_name:
                description = f"{description}\nToolkit: {toolkit_name}"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=keycloak_api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools

