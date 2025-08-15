from typing import Optional, List, Literal

from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel, Field, SecretStr

from .api_wrapper import ZephyrScaleApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, get_max_toolkit_length, TOOLKIT_SPLITTER
from ...configurations.embedding import EmbeddingConfiguration
from ...configurations.pgvector import PgVectorConfiguration
from ...configurations.zephyr import ZephyrConfiguration

name = "zephyr_scale"

def get_tools(tool):
    return ZephyrScaleToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        base_url=tool['settings'].get('base_url', None),
        token=tool['settings'].get('token', None),
        username=tool['settings'].get('username', None),
        password=tool['settings'].get('password', None),
        cookies=tool['settings'].get('cookies', None),
        max_results=tool['settings'].get('max_results', 100),
        toolkit_name=tool.get('toolkit_name'),
        llm=tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),

        # indexer settings
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        collection_name=str(tool['toolkit_name']),
        embedding_model="HuggingFaceEmbeddings",
        embedding_model_params={"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        vectorstore_type="PGVector"
    ).get_tools()


class ZephyrScaleToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ZephyrScaleApiWrapper.model_construct().get_available_tools()}
        ZephyrScaleToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            max_results=(int, Field(default=100, description="Results count to show")),
            zephyr_configuration=(Optional[ZephyrConfiguration], Field(description="Zephyr Configuration", json_schema_extra={'configuration_types': ['zephyr']})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(description="PgVector Configuration",
                                                                           json_schema_extra={
                                                                               'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_configuration=(Optional[EmbeddingConfiguration], Field(default=None, description="Embedding configuration.",
                                                                             json_schema_extra={'configuration_types': [
                                                                                 'embedding']})),
            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={
                'json_schema_extra': {
                    'metadata': {
                        "label": "Zephyr Scale",
                        "icon_url": "zephyr.svg",
                        "categories": ["test management"],
                        "extra_categories": ["test automation", "test case management", "test planning"],
                        "sections": {
                            "auth": {
                                "required": True,
                                "subsections": [
                                    {
                                        "name": "Token",
                                        "fields": ["token"]
                                    },
                                    {
                                        "name": "Password",
                                        "fields": ["username", "password"]
                                    },
                                    {
                                        "name": "Cookie",
                                        "fields": ["cookies"]
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            # Use zephyr_configuration fields
            **kwargs.get('zephyr_configuration', {}),
            **(kwargs.get('pgvector_configuration') or {}),
        }
        zephyr_wrapper = ZephyrScaleApiWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = zephyr_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=zephyr_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
