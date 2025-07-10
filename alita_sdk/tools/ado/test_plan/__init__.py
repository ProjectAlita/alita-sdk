from typing import List, Optional, Literal

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import create_model, BaseModel, Field, SecretStr

import requests
from .test_plan_wrapper import TestPlanApiWrapper
from ...base.tool import BaseAction
from ...utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length, check_connection_response


name = "azure_devops_plans"
name_alias = "ado_plans"


class AzureDevOpsPlansToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in TestPlanApiWrapper.model_construct().get_available_tools()}
        AzureDevOpsPlansToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        m = create_model(
            name_alias,
            name=(str, Field(description="Toolkit name", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': AzureDevOpsPlansToolkit.toolkit_max_length})),
            organization_url=(str, Field(title="Organization URL",
                                                   description="ADO organization url",
                                                   json_schema_extra={
                                                       'configuration': True,
                                                       'configuration_title': True
                                                   })),
            project=(str, Field(title="Project", description="ADO project", json_schema_extra={'configuration': True})),
            limit=(Optional[int], Field(description="ADO plans limit used for limitation of the list with results", default=5)),
            token=(SecretStr, Field(description="ADO token", json_schema_extra={'secret': True, 'configuration': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={'json_schema_extra': {'metadata':
                {
                    "label": "ADO plans",
                    "icon_url": "ado-plans.svg",
                    "categories": ["test management"],
                    "extra_categories": ["test case management", "qa"],
                    "sections": {
                        "auth": {
                            "required": True,
                            "subsections": [
                                {
                                    "name": "Token",
                                    "fields": ["token"]
                                }
                            ]
                        }
                    },
                    # connect different toolkits under the same configuration group with the same name,
                    # label and icon
                    "configuration_group": {
                        "name": "ado",
                        "label": "Azure DevOps",
                        "icon_url": "azure-icon.svg",
                    }
                }
            }
            }
        )

        @check_connection_response
        def check_connection(self):
            response = requests.get(
                f'{self.organization_url}/{self.project}/_apis/testplan/plans?api-version=7.0',
                headers = {'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            return response

        m.check_connection = check_connection
        return m

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        from os import environ
        if not environ.get('AZURE_DEVOPS_CACHE_DIR', None):
            environ['AZURE_DEVOPS_CACHE_DIR'] = '/tmp/.azure-devops'
        if selected_tools is None:
            selected_tools = []
        azure_devops_api_wrapper = TestPlanApiWrapper(**kwargs)
        available_tools = azure_devops_api_wrapper.get_available_tools()
        tools = []
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            print(tool)
            tools.append(BaseAction(
                api_wrapper=azure_devops_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"] + f"\nADO instance: {azure_devops_api_wrapper.organization_url}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
