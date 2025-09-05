from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field
from typing import List, Literal, Optional

from .api_wrapper import ZephyrApiWrapper
from ..base.tool import BaseAction
from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, get_max_toolkit_length, TOOLKIT_SPLITTER
from ...configurations.pgvector import PgVectorConfiguration
from ...configurations.zephyr_enterprise import ZephyrEnterpriseConfiguration

name = "zephyr_enterprise"

def get_tools(tool):
    return ZephyrEnterpriseToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        zephyr_configuration=tool['settings'].get('zephyr_configuration', {}),
        toolkit_name=tool.get('toolkit_name'),
        llm=tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),

        # indexer settings
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        embedding_model=tool['settings'].get('embedding_model'),
        collection_name=str(tool['toolkit_name']),
        vectorstore_type="PGVector"
    ).get_tools()

class ZephyrEnterpriseToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          ZephyrApiWrapper.model_construct().get_available_tools()}
        ZephyrEnterpriseToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            zephyr_configuration=(ZephyrEnterpriseConfiguration, Field(description="Zephyr Configuration", json_schema_extra={'configuration_types': ['zephyr_enterprise']})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(description="PgVector Configuration",
                                                                           json_schema_extra={
                                                                               'configuration_types': ['pgvector']},
                                                                           default=None)),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),
            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Zephyr Enterprise", "icon_url": "zephyr.svg",
                    "categories": ["test management"],
                    "extra_categories": ["test automation", "test case management", "test planning"]
                }})
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # Use zephyr_configuration fields
            **kwargs.get('zephyr_configuration', {}),
            **(kwargs.get('pgvector_configuration') or {}),
            **(kwargs.get('embedding_configuration') or {}),
        }
        zephyr_api_wrapper = ZephyrApiWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = zephyr_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=zephyr_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"] + "\nZephyr Enterprise instance: " + zephyr_api_wrapper.base_url,
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> List[BaseTool]:
        return self.tools
