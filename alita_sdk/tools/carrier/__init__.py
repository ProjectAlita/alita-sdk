import logging
from typing import Dict, List, Optional, Literal
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field
from functools import lru_cache

from .api_wrapper import CarrierAPIWrapper
from .tools import __all__
from ..elitea_base import filter_missconfigured_index_tools
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from ...configurations.carrier import CarrierConfiguration

logger = logging.getLogger(__name__)

name = 'carrier'


class AlitaCarrierToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 100

    @classmethod
    @lru_cache(maxsize=32)
    def toolkit_config_schema(cls) -> BaseModel:
        selected_tools = {}
        for t in __all__:
            default = t['tool'].__pydantic_fields__['args_schema'].default
            selected_tools[t['name']] = default.schema() if default else default
        cls.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            project_id=(Optional[str], Field(None, description="Optional project ID for scoped operations")),
            carrier_configuration=(CarrierConfiguration, Field(description="Carrier Configuration", json_schema_extra={'configuration_types': ['carrier']})),
            selected_tools=(
                List[Literal[tuple(selected_tools)]],
                Field(default=[], json_schema_extra={"args_schemas": selected_tools}),
            ),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Carrier",
                    "version": "2.0.1",
                    "icon_url": "carrier.svg",
                    "categories": ["testing"],
                    "extra_categories": ["carrier", "ticket management", "log management"],
                }
            })
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(
            cls,
            selected_tools: Optional[List[str]] = None,
            toolkit_name: Optional[str] = None,
            **kwargs
    ) -> 'AlitaCarrierToolkit':
        selected_tools = selected_tools or []
        logger.info(f"[AlitaCarrierToolkit] Initializing toolkit with selected tools: {selected_tools}")

        wrapper_payload = {
            **kwargs,
            **kwargs.get('carrier_configuration', {}),
        }

        try:
            carrier_api_wrapper = CarrierAPIWrapper(**wrapper_payload)
            logger.info(
                f"[AlitaCarrierToolkit] CarrierAPIWrapper initialized successfully with URL: {wrapper_payload.get('url')}")
        except Exception as e:
            logger.exception(f"[AlitaCarrierToolkit] Error initializing CarrierAPIWrapper: {e}")
            raise ValueError(f"CarrierAPIWrapper initialization error: {e}")

        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''

        tools = []
        for tool_def in __all__:
            if selected_tools and tool_def['name'] not in selected_tools:
                continue
            try:
                tool_instance = tool_def['tool'](api_wrapper=carrier_api_wrapper)
                tool_instance.name = prefix + tool_instance.name
                tools.append(tool_instance)
                logger.info(f"[AlitaCarrierToolkit] Successfully initialized tool '{tool_instance.name}'")
            except Exception as e:
                logger.warning(f"[AlitaCarrierToolkit] Could not initialize tool '{tool_def['name']}': {e}")

        logger.info(f"[AlitaCarrierToolkit] Total tools initialized: {len(tools)}")
        return cls(tools=tools)

    def get_tools(self) -> List[BaseTool]:
        logger.info(f"[AlitaCarrierToolkit] Retrieving {len(self.tools)} initialized tools")
        return self.tools


# Simplified utility method for toolkit retrieval
def get_tools(tool_config: Dict) -> List[BaseTool]:
    return AlitaCarrierToolkit.get_toolkit(
        selected_tools=tool_config.get('selected_tools', []),
        project_id=tool_config['settings'].get('project_id'),
        carrier_configuration=tool_config['settings']['carrier_configuration'],
        toolkit_name=tool_config.get('toolkit_name')
    ).get_tools()
