from typing import Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, create_model, Field

from .api_wrapper import PythonLinter
from ...base.tool import BaseAction
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "python_linter"

def get_tools(tool):
    return PythonLinterToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        error_codes=tool['settings']['error_codes'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class PythonLinterToolkit(BaseToolkit):
    tools: list[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        PythonLinterToolkit.toolkit_max_length = get_max_toolkit_length([])
        return create_model(
            name,
            error_codes=(str, Field(description="Error codes to be used by the linter")),
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        python_linter = PythonLinter(**kwargs)
        available_tools = python_linter.get_available_tools()
        tools = []
        toolkit_max_length = get_max_toolkit_length(selected_tools)
        prefix = clean_string(toolkit_name, PythonLinterToolkit.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=python_linter,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools