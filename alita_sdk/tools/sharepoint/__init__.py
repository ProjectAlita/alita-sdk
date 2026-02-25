import logging
from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field

from .api_wrapper import SharepointApiWrapper
from ..base.tool import BaseAction
from ..elitea_base import filter_missconfigured_index_tools
from ...configurations.pgvector import PgVectorConfiguration
from ...configurations.sharepoint import SharepointConfiguration
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

logger = logging.getLogger(__name__)

name = "sharepoint"

def get_tools(tool):
    return (SharepointToolkit()
            .get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        sharepoint_configuration=tool['settings']['sharepoint_configuration'],
        tokens = tool['settings'].get('tokens', {}),
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

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in SharepointApiWrapper.model_construct().get_available_tools()}
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
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            **kwargs.get('sharepoint_configuration', {}),
            **(kwargs.get('pgvector_configuration') or {}),
        }

        # handle OAuth flow: specific for Sharepoint (dependent on oauth_discovery_endpoint), can be extended to other tools in the future if needed
        if kwargs.get('tokens') and kwargs['sharepoint_configuration'].get('oauth_discovery_endpoint'):
            logger.debug(f"Sharepoint configuration includes OAuth discovery endpoint and tokens are provided. Attempting to retrieve access token.")
            token = kwargs['tokens'].get(kwargs['sharepoint_configuration']['oauth_discovery_endpoint'])
            wrapper_payload['token'] = token.get('access_token')

        sharepoint_api_wrapper = SharepointApiWrapper(**wrapper_payload)
        available_tools = sharepoint_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            description = f"Sharepoint {sharepoint_api_wrapper.site_url}\n{tool['description']}"
            if toolkit_name:
                description = f"{description}\nToolkit: {toolkit_name}"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=sharepoint_api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools