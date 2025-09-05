from typing import List, Literal, Optional
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field

from .api_wrapper import SonarApiWrapper
from ...base.tool import BaseAction
from ...elitea_base import filter_missconfigured_index_tools
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from ....configurations.sonar import SonarConfiguration

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
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in SonarApiWrapper.model_construct().get_available_tools()}
        SonarToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            sonar_project_name=(str, Field(description="Project name of the desired repository", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': SonarToolkit.toolkit_max_length})),
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
        prefix = clean_string(toolkit_name, SonarToolkit.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=sonar_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools

