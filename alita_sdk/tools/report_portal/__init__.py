from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool

from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

from .api_wrapper import ReportPortalApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "report_portal"

def get_tools(tool):
    return ReportPortalToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        endpoint=tool['settings']['endpoint'],
        api_key=tool['settings']['api_key'],
        project=tool['settings']['project'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class ReportPortalToolkit(BaseToolkit):
    tools: list[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ReportPortalApiWrapper.model_construct().get_available_tools()}
        ReportPortalToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            endpoint=(str, Field(description="Report Portal endpoint", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': ReportPortalToolkit.toolkit_max_length})),
            project=(str, Field(description="Report Portal project")),
            api_key=(SecretStr, Field(description="User API key", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Report Portal", "icon_url": "reportportal-icon.svg"}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        report_portal_api_wrapper = ReportPortalApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = report_portal_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=report_portal_api_wrapper,
                name=prefix + tool["name"],
                description=f"{tool['description']}\nReport portal configuration: 'url - {report_portal_api_wrapper.endpoint}, project - {report_portal_api_wrapper.project}'",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools
