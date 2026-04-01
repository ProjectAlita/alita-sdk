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
        sp_config = kwargs.get('sharepoint_configuration', {})
        logger.debug(f"[SP OAuth] tokens keys={list(kwargs.get('tokens', {}).keys())}, sp_config site_url={sp_config.get('site_url')}, oauth_endpoint={sp_config.get('oauth_discovery_endpoint')}, config_uuid={sp_config.get('configuration_uuid')}")
        if kwargs.get('tokens') and sp_config.get('oauth_discovery_endpoint'):
            logger.debug(f"Sharepoint configuration includes OAuth discovery endpoint and tokens are provided. Attempting to retrieve access token.")
            oauth_endpoint = sp_config['oauth_discovery_endpoint']
            config_uuid = sp_config.get('configuration_uuid')
            # Try credential-specific key first ("<configuration_uuid>:<oauth_discovery_endpoint>").
            # The frontend stores tokens under this composite key so that two SharePoint
            # credentials sharing the same oauth_discovery_endpoint (same Azure AD tenant)
            # keep their OAuth sessions isolated.
            token = None
            if config_uuid:
                token = kwargs['tokens'].get(f"{config_uuid}:{oauth_endpoint}")
            # Fallback to plain oauth_discovery_endpoint for backwards compatibility
            # (legacy sessions or toolkit-level flows that don't use credential UUIDs).
            if token is None:
                token = kwargs['tokens'].get(oauth_endpoint)
            # Fallback to site_url key: the frontend may store the token under the
            # SharePoint site URL when tokenStorageKey is not explicitly overridden
            # (e.g. when the auth modal opens without a pre-configured storage key).
            if token is None:
                site_url_key = sp_config.get('site_url', '')
                if site_url_key:
                    token = kwargs['tokens'].get(site_url_key)
            if token is not None:
                wrapper_payload['token'] = token.get('access_token') if isinstance(token, dict) else token
                # Delegated tokens from mcp_tokens are always Azure AD Graph tokens.
                # Ensure 'scopes' is non-empty so validate_toolkit selects
                # SharepointGraphWrapper (token + scopes path) rather than
                # SharepointRestWrapper (token-only path), which does not use the
                # delegated token for Graph calls and falls back to app-only auth.
                if not wrapper_payload.get('scopes'):
                    wrapper_payload['scopes'] = ['https://graph.microsoft.com/.default']

        # Proactive OAuth guard: if delegated flow is configured but no token was resolved,
        # raise McpAuthorizationRequired immediately so Chat/agents surface a clean login
        # prompt instead of failing deep inside a tool call with a cryptic error.
        if sp_config.get('oauth_discovery_endpoint') and not wrapper_payload.get('token'):
            logger.debug("SharePoint OAuth mode active but no token found — raising McpAuthorizationRequired.")
            raise SharepointConfiguration._build_mcp_authorization_required(
                message=(
                    f"SharePoint site {sp_config.get('site_url', '')} requires OAuth authorization. "
                    "Please log in to continue."
                ),
                site_url=sp_config.get('site_url', ''),
                oauth_discovery_endpoint=sp_config['oauth_discovery_endpoint'],
                scopes=sp_config.get('scopes'),
                configuration_uuid=sp_config.get('configuration_uuid'),
            )

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