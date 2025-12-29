from typing import List, Literal, Optional

import requests
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

from .api_wrapper import QtestApiWrapper
from .tool import QtestAction
from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, get_max_toolkit_length, check_connection_response
from ...configurations.qtest import QtestConfiguration
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "qtest"


def get_tools(tool):
    toolkit = QtestToolkit.get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        qtest_project_id=tool['settings'].get('qtest_project_id', tool['settings'].get('project_id', None)),
        no_of_tests_shown_in_dql_search=tool['settings'].get('no_of_tests_shown_in_dql_search'),
        qtest_configuration=tool['settings']['qtest_configuration'],
        toolkit_name=tool.get('toolkit_name'),
        llm=tool['settings'].get('llm', None)
    )
    return toolkit.tools


class QtestToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in QtestApiWrapper.model_construct().get_available_tools()}
        m = create_model(
            name,
            qtest_configuration=(QtestConfiguration, Field(description="QTest API token", json_schema_extra={
                'configuration_types': ['qtest']})),
            qtest_project_id=(int, Field(description="QTest project id")),
            no_of_tests_shown_in_dql_search=(Optional[int], Field(description="Max number of items returned by dql search",
                                                                  default=10)),

        selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "QTest", "icon_url": "qtest.svg",
                                                                  "categories": ["test management"],
                                                                  "extra_categories": ["quality assurance",
                                                                                       "test case management",
                                                                                       "test planning"]}})
        )

        @check_connection_response
        def check_connection(self):
            response = requests.get(
                f'{self.base_url}/api/v3/projects',
                headers={
                    'Authorization': f'Bearer {self.qtest_api_token}'
                },
                timeout=5
            )

            return response
        m.check_connection = check_connection
        return m

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # TODO use qtest_configuration fields
            **kwargs['qtest_configuration'],
        }
        qtest_api_wrapper = QtestApiWrapper(**wrapper_payload)
        available_tools = qtest_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            description = f"{tool['description']}\nUrl: {qtest_api_wrapper.base_url}. Project id: {qtest_api_wrapper.qtest_project_id}"
            if toolkit_name:
                description = f"{description}\nToolkit: {toolkit_name}"
            description = description[:1000]
            tools.append(QtestAction(
                api_wrapper=qtest_api_wrapper,
                name=tool["name"],
                mode=tool["mode"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools