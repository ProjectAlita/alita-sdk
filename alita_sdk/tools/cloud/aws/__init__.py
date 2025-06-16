from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, create_model, SecretStr

from langchain_core.tools import BaseToolkit, BaseTool

from .api_wrapper import AWSToolConfig
from ...base.tool import BaseAction
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "aws"

def get_tools(tool):
    return AWSToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        region=tool['settings'].get('region', ''),
        access_key_id=tool['settings'].get('access_key_id', None),
        secret_access_key=tool['settings'].get('secret_access_key', None),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class AWSToolkit(BaseToolkit):
    tools: list[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in AWSToolConfig.model_construct().get_available_tools()}
        AWSToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            region=(str, Field(default="", title="Region", description="AWS region")),
            access_key_id=(Optional[str], Field(default=None, title="Access Key ID", description="AWS access key ID")),
            secret_access_key=(Optional[SecretStr], Field(default=None, title="Secret Access Key", description="AWS secret access key", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Cloud AWS", "icon_url": None, "hidden": True}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        aws_tool_config = AWSToolConfig(**kwargs)
        available_tools = aws_tool_config.get_available_tools()
        tools = []
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=aws_tool_config,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools