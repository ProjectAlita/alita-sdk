from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel, Field, SecretStr

from .yagmail_wrapper import YagmailWrapper, SMTP_SERVER
from ..base.tool import BaseAction

name = "yagmail"

def get_tools(tool):
    return AlitaYagmailToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        host=tool['settings'].get('host', SMTP_SERVER),
        username=tool['settings'].get('username'),
        password=tool['settings'].get("password")
    ).get_tools()


class AlitaYagmailToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in YagmailWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
            host=(Optional[str], Field(default=SMTP_SERVER, description="SMTP Host")),
            username=(str, Field(description="Username")),
            password=(SecretStr, Field(description="Password", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={'json_schema_extra': {'metadata': {"label": "Yet Another Gmail", "icon_url": None, "hidden": True}}}
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        yagmail_wrapper = YagmailWrapper(**kwargs)
        available_tools = yagmail_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=yagmail_wrapper,
                name=tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools