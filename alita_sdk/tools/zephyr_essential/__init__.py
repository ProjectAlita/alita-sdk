from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, Field

from .api_wrapper import ZephyrEssentialApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from ...configurations.pgvector import PgVectorConfiguration
from ...configurations.zephyr_essential import ZephyrEssentialConfiguration

name = "zephyr_essential"

def get_tools(tool):
    return ZephyrEssentialToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        zephyr_essential_configuration=tool['settings']['zephyr_essential_configuration'],
        toolkit_name=tool.get('toolkit_name'),
        llm = tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),

        # indexer settings
        collection_name=str(tool['toolkit_name']),
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        embedding_model=tool['settings'].get('embedding_model'),
        vectorstore_type = "PGVector"
    ).get_tools()

class ZephyrEssentialToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ZephyrEssentialApiWrapper.model_construct().get_available_tools()}
        ZephyrEssentialToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            zephyr_essential_configuration=(ZephyrEssentialConfiguration, Field(description="Zephyr Essential Configuration", json_schema_extra={'configuration_types': ['zephyr_essential']})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(default=None,
                                                                           description="PgVector Configuration",
                                                                           json_schema_extra={
                                                                               'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),
            __config__={'json_schema_extra': {'metadata': {"label": "Zephyr Essential", "icon_url": "zephyr.svg",
                            "categories": ["test management"],
                            "extra_categories": ["test automation", "test case management", "test planning"]
                        }}}
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            **kwargs.get('zephyr_essential_configuration', {}),
            **(kwargs.get('pgvector_configuration') or {}),
        }
        zephyr_api_wrapper = ZephyrEssentialApiWrapper(**wrapper_payload)
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
