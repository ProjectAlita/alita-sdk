from typing import List, Literal, Optional
from langchain_community.agent_toolkits.base import BaseToolkit

from .api_wrapper import ServiceNowAPIWrapper
from langchain_core.tools import BaseTool
from ..base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from ...configurations.service_now import ServiceNowConfiguration


name = "service_now"

def get_tools(tool):
    return ServiceNowToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        instance_alias=tool['settings'].get('instance_alias', None),
        base_url=tool['settings']['base_url'],
        servicenow_configuration=tool['settings']['servicenow_configuration'],
        response_fields=tool['settings'].get('response_fields', None),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class ServiceNowToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          ServiceNowAPIWrapper.model_construct().get_available_tools()}
        ServiceNowToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            name=(str, Field(description="Toolkit name",
                             json_schema_extra={
                                 'toolkit_name': True, 'max_toolkit_length': ServiceNowToolkit.toolkit_max_length})),
            response_fields=(Optional[str], Field(description="Response fields", default=None)),
            servicenow_configuration=(ServiceNowConfiguration, Field(description="ServiceNow Configuration",
                                                                               json_schema_extra={
                                                                                   'configuration_types': [
                                                                                       'service_now']})),
            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "ServiceNow",
                    "icon_url": "service-now.svg",
                    "hidden": False,
                    "sections": {
                        "auth": {
                            "required": True,
                            "subsections": [
                                {
                                    "name": "Basic",
                                    "fields": ["username", "password"]
                                }
                            ]
                        }
                    },
                    "categories": ["other"],
                    "extra_categories": ["incident management", "problem management", "change management", "service catalog"]
                }
            })
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        if 'response_fields' in kwargs and isinstance(kwargs['response_fields'], str):
            kwargs['fields'] = [field.strip().lower() for field in kwargs['response_fields'].split(',') if field.strip()]
        wrapper_payload = {
            **kwargs,
            # TODO use servicenow_configuration fields
            **kwargs['servicenow_configuration'],
        }
        servicenow_api_wrapper = ServiceNowAPIWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = servicenow_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=servicenow_api_wrapper,
                name=prefix + tool["name"],
                description=f"ServiceNow: {servicenow_api_wrapper.base_url} " + tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
