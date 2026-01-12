from typing import List, Literal, Optional
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field

from .api_wrapper import SonarApiWrapper
from ...base.tool import BaseAction
from ...elitea_base import filter_missconfigured_index_tools
from ...utils import clean_string, get_max_toolkit_length
from ....configurations.sonar import SonarConfiguration
from ....runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "sonar"

def get_tools(tool):
    return SonarToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        sonar_project_name=tool['settings']['sonar_project_name'],
        sonar_configuration=tool['settings']['sonar_configuration'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class SonarToolkit(BaseToolkit):
    tools: list[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in SonarApiWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
            sonar_project_name=(str, Field(description="Project name of the desired repository")),
            sonar_configuration=(SonarConfiguration, Field(description="Sonar Configuration", json_schema_extra={'configuration_types': ['sonar']})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra=
                                  {
                                      'metadata':
                                          {
                                              "label": "Sonar", "icon_url": "sonar-icon.svg",
                                              "categories": ["development"],
                                              "extra_categories": ["code quality", "code security", "code coverage", "quality", "sonarqube"]
                                          }
                                  })
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            **kwargs.get('sonar_configuration', {}),
        }
        sonar_api_wrapper = SonarApiWrapper(**wrapper_payload)
        available_tools = sonar_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            description = tool["description"]
            if toolkit_name:
                description = f"Toolkit: {toolkit_name}\n{description}"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=sonar_api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools

