from typing import List, Literal, Optional
from langchain_community.agent_toolkits.base import BaseToolkit

from .api_wrapper import ServiceNowAPIWrapper
from langchain_core.tools import BaseTool
from ..base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field

from ..elitea_base import filter_missconfigured_index_tools
from ...configurations.service_now import ServiceNowConfiguration
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META


name = "service_now"

def get_tools(tool):
    settings = tool.get('settings') or {}

    return ServiceNowToolkit().get_toolkit(
        selected_tools=settings.get('selected_tools', []),
        instance_alias=settings.get('instance_alias', None),
        servicenow_configuration=settings.get('servicenow_configuration', None),
        response_fields=settings.get('response_fields', None),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class ServiceNowToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          ServiceNowAPIWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
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
    @filter_missconfigured_index_tools
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
        available_tools = servicenow_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            base_url = getattr(servicenow_api_wrapper, "base_url", "") or ""
            description = tool.get("description", "") if isinstance(tool, dict) else ""
            if toolkit_name:
                description = f"Toolkit: {toolkit_name}\n{description}"
            description = f"ServiceNow: {base_url}\n{description}".strip()
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=servicenow_api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
