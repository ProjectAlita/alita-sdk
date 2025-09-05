from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, Field, SecretStr

from .api_wrapper import ZephyrSquadApiWrapper
from ..base.tool import BaseAction
from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "zephyr_squad"

def get_tools(tool):
    return ZephyrSquadToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        account_id=tool['settings']["account_id"],
        access_key=tool['settings']["access_key"],
        secret_key=tool['settings']["secret_key"],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class ZephyrSquadToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ZephyrSquadApiWrapper.model_construct().get_available_tools()}
        ZephyrSquadToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            account_id=(str, Field(description="AccountID for the user that is going to be authenticating")),
            access_key=(SecretStr, Field(description="Generated access key", json_schema_extra={'secret': True})),
            secret_key=(SecretStr, Field(description="Generated secret key", json_schema_extra={'secret': True})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={'json_schema_extra': {'metadata': {"label": "Zephyr Squad", "icon_url": "zephyr.svg",
                            "categories": ["test management"],
                            "extra_categories": ["test automation", "test case management", "test planning"]
                        }}}
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        zephyr_api_wrapper = ZephyrSquadApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = zephyr_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=zephyr_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools

