from typing import List, Optional, Literal
from .api_wrapper import JiraApiWrapper
from langchain_core.tools import BaseTool, BaseToolkit
from ..base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length, parse_list

name = "jira"

def get_tools(tool):
    return JiraToolkit().get_toolkit(
            selected_tools=tool['settings'].get('selected_tools', []),
            base_url=tool['settings'].get('base_url'),
            cloud=tool['settings'].get('cloud', True),
            api_key=tool['settings'].get('api_key', None),
            username=tool['settings'].get('username', None),
            token=tool['settings'].get('token', None),
            limit=tool['settings'].get('limit', 5),
            labels=parse_list(tool['settings'].get('labels', [])),
            additional_fields=tool['settings'].get('additional_fields', []),
            toolkit_name=tool.get('toolkit_name'),
            verify_ssl=tool['settings'].get('verify_ssl', True),
            llm=tool['settings'].get('llm', None)
            ).get_tools()
            

class JiraToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in JiraApiWrapper.model_construct().get_available_tools()}
        JiraToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            base_url=(
                str,
                Field(
                    description="Jira URL",
                    json_schema_extra={
                        'toolkit_name': True,
                        'max_toolkit_length': JiraToolkit.toolkit_max_length,
                        'configuration': True,
                        'configuration_title': True
                    }
                )
            ),
            cloud=(bool, Field(description="Hosting Option", json_schema_extra={'configuration': True})),
            api_key=(Optional[SecretStr], Field(description="API key", default=None, json_schema_extra={'secret': True, 'configuration': True})),
            username=(Optional[str], Field(description="Jira Username", default=None, json_schema_extra={'configuration': True})),
            token=(Optional[SecretStr], Field(description="Jira token", default=None, json_schema_extra={'secret': True, 'configuration': True})),
            limit=(int, Field(description="Limit issues", default=5)),
            labels=(Optional[str], Field(
                description="List of comma separated labels used for labeling of agent's created or updated entities",
                default=None,
                examples="alita,elitea;another-label"
            )),
            verify_ssl=(bool, Field(description="Verify SSL", default=True)),
            additional_fields=(Optional[str], Field(description="Additional fields", default="")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Jira",
                    "icon_url": "jira-icon.svg",
                    "sections": {
                        "auth": {
                            "required": True,
                            "subsections": [
                                {
                                    "name": "Bearer",
                                    "fields": ["token"]
                                },
                                {
                                    "name": "Basic",
                                    "fields": ["username", "api_key"]
                                }
                            ]
                        }
                    }
                }
            })
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        jira_api_wrapper = JiraApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = jira_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=jira_api_wrapper,
                name=prefix + tool["name"],
                description=f"Tool for Jira: '{jira_api_wrapper.base_url}'\n{tool['description']}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
