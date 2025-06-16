from typing import List, Literal, Optional
from langchain_core.tools import BaseToolkit
from pydantic import BaseModel, ConfigDict, Field, create_model, SecretStr
from .api_wrapper import RallyApiWrapper
from langchain_core.tools import BaseTool
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "rally"

def get_tools(tool):
    return RallyToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        server=tool['settings']['server'],
        api_key=tool['settings'].get('api_key'),
        username=tool['settings'].get('username'),
        password=tool['settings'].get('password'),
        workspace=tool['settings'].get('workspace', None),
        project=tool['settings'].get('project', None),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class RallyToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in RallyApiWrapper.model_construct().get_available_tools()}
        RallyToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            server=(str, Field(description="Rally server url", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': RallyToolkit.toolkit_max_length})),
            api_key=(Optional[SecretStr], Field(default=None, description="User's API key", json_schema_extra={'secret': True})),
            username=(Optional[str], Field(default=None, description="Username")),
            password=(Optional[SecretStr], Field(default=None, description="User's password", json_schema_extra={'secret': True})),
            workspace=(Optional[str], Field(default=None, description="Rally workspace")),
            project=(Optional[str], Field(default=None, description="Rally project")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Rally",
                    "icon_url": "rally.svg",
                    "sections": {
                        "auth": {
                            "required": True,
                            "subsections": [
                                {
                                    "name": "Password",
                                    "fields": ["username", "password"]
                                },
                                {
                                    "name": "API Key",
                                    "fields": ["api_key"]
                                }
                            ]
                        }
                    }
                }
            })
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        rally_api_wrapper = RallyApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = rally_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=rally_api_wrapper,
                name=prefix + tool["name"],
                description=f"{tool['description']}\nWorkspace: {rally_api_wrapper.workspace}. Project: {rally_api_wrapper.project}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools