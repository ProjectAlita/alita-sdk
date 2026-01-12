from typing import Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, create_model, Field

from .api_wrapper import PythonLinter
from ...base.tool import BaseAction
from ...utils import clean_string, get_max_toolkit_length
from ....runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "python_linter"

def get_tools(tool):
    return PythonLinterToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        error_codes=tool['settings']['error_codes'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class PythonLinterToolkit(BaseToolkit):
    tools: list[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            name,
            error_codes=(str, Field(description="Error codes to be used by the linter")),
            __config__={'json_schema_extra': {'metadata': {"label": "Python Linter", "icon_url": None, "hidden": True,
                                                           "categories": ["development"],
                                                           "extra_categories": ["code linter", "python linter"]}}}
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        python_linter = PythonLinter(**kwargs)
        available_tools = python_linter.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            description = tool["description"]
            if toolkit_name:
                description = f"Toolkit: {toolkit_name}\n{description}"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=python_linter,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools

