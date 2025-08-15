from sys import prefix
from typing import List, Optional, Literal

from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel, Field, SecretStr

from .api_wrapper import XrayApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, get_max_toolkit_length, TOOLKIT_SPLITTER
from ...configurations.embedding import EmbeddingConfiguration
from ...configurations.pgvector import PgVectorConfiguration
from ...configurations.xray import XrayConfiguration

name = "xray_cloud"


def get_tools(tool):
    return XrayToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        base_url=tool['settings'].get('base_url', None),
        client_id=tool['settings'].get('client_id', None),
        client_secret=tool['settings'].get('client_secret', None),
        limit=tool['settings'].get('limit', 20),
        verify_ssl=tool['settings'].get('verify_ssl', True),
        toolkit_name=tool.get('toolkit_name'),
        alita=tool['settings'].get('alita', None),

        # indexer settings
        connection_string=tool['settings'].get('connection_string', None),
        collection_name=str(tool['toolkit_name']),
        embedding_model="HuggingFaceEmbeddings",
        embedding_model_params={"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        vectorstore_type="PGVector"
    ).get_tools()


class XrayToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in XrayApiWrapper.model_construct().get_available_tools()}
        XrayToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            limit=(Optional[int], Field(description="Limit", default=100)),
            xray_configuration=(Optional[XrayConfiguration], Field(description="Xray Configuration", json_schema_extra={'configuration_types': ['xray']})),
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(description="PgVector Configuration",
                                                                           json_schema_extra={
                                                                               'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_configuration=(Optional[EmbeddingConfiguration], Field(default=None, description="Embedding configuration.",
                                                                             json_schema_extra={'configuration_types': [
                                                                                 'embedding']})),

            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__={'json_schema_extra':
                            {
                                'metadata': {
                                    "label": "XRAY cloud", "icon_url": "xray.svg",
                                "categories": ["test management"],
                                    "extra_categories": ["test automation", "test case management", "test planning"]
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
            # Use xray_configuration fields
            **kwargs.get('xray_configuration', {}),
            **(kwargs.get('pgvector_configuration') or {}),
        }
        xray_api_wrapper = XrayApiWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = xray_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=xray_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"] + "\nXray instance: " + xray_api_wrapper.base_url,
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
