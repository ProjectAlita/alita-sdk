from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field
from .api_wrapper import SharepointApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from ...configurations.pgvector import PgVectorConfiguration
from ...configurations.sharepoint import SharepointConfiguration

name = "sharepoint"

def get_tools(tool):
    return (SharepointToolkit()
            .get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        sharepoint_configuration=tool['settings']['sharepoint_configuration'],
        toolkit_name=tool.get('toolkit_name'),
        llm=tool['settings'].get('llm'),
        alita=tool['settings'].get('alita', None),
        # indexer settings
        pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
        embedding_model=tool['settings'].get('embedding_model'),
        collection_name=str(tool['toolkit_name']),
        vectorstore_type="PGVector")
            .get_tools())


class SharepointToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in SharepointApiWrapper.model_construct().get_available_tools()}
        SharepointToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            sharepoint_configuration=(SharepointConfiguration, Field(description="SharePoint Configuration", json_schema_extra={'configuration_types': ['sharepoint']})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            # indexer settings
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(default=None,
                                                                           description="PgVector Configuration",
                                                                           json_schema_extra={'configuration_types': ['pgvector']})),
            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Sharepoint", "icon_url": "sharepoint.svg",
                    "categories": ["office"],
                    "extra_categories": ["microsoft", "cloud storage", "team collaboration", "content management"]
        }})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            **kwargs.get('sharepoint_configuration', {}),
            **(kwargs.get('pgvector_configuration') or {}),
        }
        sharepoint_api_wrapper = SharepointApiWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = sharepoint_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=sharepoint_api_wrapper,
                name=prefix + tool["name"],
                description=f"Sharepoint {sharepoint_api_wrapper.site_url}\n{tool['description']}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
