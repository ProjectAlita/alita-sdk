from typing import List, Literal, Optional, Dict, Any
import os
import tempfile
import logging
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field
from .pptx_wrapper import PPTXWrapper

from ..base.tool import BaseAction
from ..utils import clean_string, get_max_toolkit_length
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

logger = logging.getLogger(__name__)

name = "pptx"


def get_tools(tool):
    """
    Returns the PPTX toolkit tools based on configuration.
    """
    return PPTXToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        bucket_name=tool['settings'].get('bucket_name', ''),
        alita=tool['settings'].get('alita', None),
        llm=tool['settings'].get('llm', None),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class PPTXToolkit(BaseToolkit):
    """
    PowerPoint (PPTX) manipulation toolkit for Alita.
    Provides tools for working with PPTX files stored in buckets.
    """
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        """
        Define the configuration schema for the toolkit.
        """
        selected_tools = {x['name']: x['args_schema'].schema() for x in PPTXWrapper.model_construct().get_available_tools()}
        
        return create_model(
            name,
            bucket_name=(str, Field(description="Bucket name where PPTX files are stored")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "PPTX",
                    "icon_url": "pptx.svg",
                    "categories": ["office"],
                    "extra_categories": ["presentation", "office automation", "document"]
                }
            })
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        """
        Get the toolkit with the specified tools.
        
        Args:
            selected_tools: List of tool names to include
            toolkit_name: Name of the toolkit
            **kwargs: Additional arguments for the API wrapper
            
        Returns:
            Configured toolkit
        """
        if selected_tools is None:
            selected_tools = []
            
        pptx_api_wrapper = PPTXWrapper(**kwargs)
        available_tools = pptx_api_wrapper.get_available_tools()
        tools = []
        
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            description = tool["description"]
            if toolkit_name:
                description = f"Toolkit: {toolkit_name}\n{description}"
            description = description[:1000]
            tools.append(BaseAction(
                api_wrapper=pptx_api_wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
            ))
            
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        """
        Return all tools in the toolkit.
        """
        return self.tools

