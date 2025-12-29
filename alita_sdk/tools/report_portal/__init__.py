from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool

from pydantic import create_model, BaseModel, ConfigDict, Field

from .api_wrapper import ReportPortalApiWrapper
from ..base.tool import BaseAction
from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, get_max_toolkit_length
from ...configurations.report_portal import ReportPortalConfiguration
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "report_portal"

def get_tools(tool):
    return ReportPortalToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        report_portal_configuration=tool['settings']['report_portal_configuration'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class ReportPortalToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ReportPortalApiWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
            report_portal_configuration=(ReportPortalConfiguration, Field(description="Report Portal Configuration", json_schema_extra={'configuration_types': ['report_portal']})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Report Portal", "icon_url": "reportportal-icon.svg",
                                                                  "categories": ["testing"],
                                                                  "extra_categories": ["test reporting", "test automation"]}})
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            **kwargs.get('report_portal_configuration', {}),
        }
        report_portal_api_wrapper = ReportPortalApiWrapper(**wrapper_payload)
        available_tools = report_portal_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            description = tool['description']
            if toolkit_name:
                description = f"Toolkit: {toolkit_name}\n{description}"
            description = f"{description}\nReport portal configuration: 'url - {report_portal_api_wrapper.endpoint}, project - {report_portal_api_wrapper.project}'"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=report_portal_api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools
