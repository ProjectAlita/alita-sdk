from typing import Any, List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, ConfigDict, create_model, Field

from .api_wrapper import PandasWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, get_max_toolkit_length
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "pandas"

def get_tools(tool):
    return PandasToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        bucket_name=tool['settings'].get('bucket_name', None),
        alita=tool['settings'].get('alita', None),
        llm=tool['settings'].get('llm', None),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class PandasToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in PandasWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
            bucket_name=(str, Field(default=None, title="Bucket name", description="Bucket where the content file is stored")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {
                "label": "Pandas (Deprecated)",
                "icon_url": "pandas-icon.svg",
                "categories": ["analysis"],
                "deprecated": True,
                "deprecation_message": "This toolkit is deprecated. Use the 'Data Analysis' internal tool instead. Enable it via the 'Internal Tools' menu in chat.",
                "extra_categories": ["data science", "data manipulation", "dataframes"]
            }})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        csv_tool_api_wrapper = PandasWrapper(**kwargs)
        available_tools = csv_tool_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            description = tool["description"]
            if toolkit_name:
                description = f"Toolkit: {toolkit_name}\n{description}"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=pandas_api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools

