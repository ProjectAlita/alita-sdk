from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, Field, SecretStr

from .data_mining_wrapper import AdvancedJiraMiningWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "advanced_jira_mining"

def get_tools(tool):
    return AdvancedJiraMiningToolkit().get_toolkit(
            selected_tools=tool['settings'].get('selected_tools', []),
            jira_base_url=tool['settings'].get('jira_base_url', ''),
            confluence_base_url=tool['settings'].get('confluence_base_url', ''),
            model_type=tool['settings'].get('model_type', ''),
            summarization_prompt=tool['settings'].get('summarization_prompt', None),
            gaps_analysis_prompt=tool['settings'].get('gaps_analysis_prompt', None),
            jira_api_key=tool['settings'].get('jira_api_key', None),
            jira_username=tool['settings'].get('jira_username', None),
            jira_token=tool['settings'].get('jira_token', None),
            is_jira_cloud=tool['settings'].get('is_jira_cloud', True),
            verify_ssl=tool['settings'].get('verify_ssl', True),
            toolkit_name=tool.get('toolkit_name'),
            ).get_tools()

class AdvancedJiraMiningToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in AdvancedJiraMiningWrapper.model_construct().get_available_tools()}
        AdvancedJiraMiningToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            jira_base_url=(str, Field(default="", title="Jira URL", description="Jira URL", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': AdvancedJiraMiningToolkit.toolkit_max_length})),
            confluence_base_url=(str, Field(default="", title="Confluence URL", description="Confluence URL")),
            model_type=(str, Field(default="", title="Model type", description="Model type")),
            summarization_prompt=(Optional[str], Field(default=None, title="Summarization prompt", description="Summarization prompt")),
            gaps_analysis_prompt=(Optional[str], Field(default=None, title="Gap analysis prompt", description="Gap analysis prompt")),
            jira_api_key=(Optional[SecretStr], Field(default=None, title="API key", description="JIRA API key", json_schema_extra={'secret': True})),
            jira_username=(Optional[str], Field(default=None, title="Username", description="JIRA Username")),
            jira_token=(Optional[SecretStr], Field(default=None, title="Token", description="JIRA Token", json_schema_extra={'secret': True})),
            is_jira_cloud=(bool, Field(default=True, title="Cloud", description="JIRA Cloud")),
            verify_ssl=(bool, Field(default=True, title="Verify SSL", description="Verify SSL")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={'json_schema_extra': {'metadata': {"label": "Advanced JIRA mining", "icon_url": "jira-icon.svg", "hidden": True}}}
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        jira_mining_wrapper = AdvancedJiraMiningWrapper(**kwargs)
        available_tools = jira_mining_wrapper.get_available_tools()
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=jira_mining_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
