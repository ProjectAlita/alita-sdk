"""
Data Analysis internal tool for Alita SDK.

This tool provides Pandas-based data analysis capabilities as an internal tool,
accessible through the "Enable internal tools" dropdown menu.

It uses the conversation attachment bucket for file storage, providing seamless
integration with drag-and-drop file uploads in chat.
"""
import logging
from typing import Any, List, Literal, Optional, Type

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, ConfigDict, create_model, Field

logger = logging.getLogger(__name__)

name = "data_analysis"


def get_tools(tools_list: list, alita_client=None, llm=None, memory_store=None):
    """
    Get data analysis tools for the provided tool configurations.

    Args:
        tools_list: List of tool configurations
        alita_client: Alita client instance (required for data analysis)
        llm: LLM client instance (required for code generation)
        memory_store: Optional memory store instance (unused)

    Returns:
        List of data analysis tools
    """
    all_tools = []

    for tool in tools_list:
        if (tool.get('type') == 'data_analysis' or
                tool.get('toolkit_name') == 'data_analysis'):
            try:
                if not alita_client:
                    logger.error("Alita client is required for data analysis tools")
                    continue

                settings = tool.get('settings', {})
                bucket_name = settings.get('bucket_name')

                if not bucket_name:
                    logger.error("bucket_name is required for data analysis tools")
                    continue

                toolkit_instance = DataAnalysisToolkit.get_toolkit(
                    alita_client=alita_client,
                    llm=llm,
                    bucket_name=bucket_name,
                    toolkit_name=tool.get('toolkit_name', '')
                )
                all_tools.extend(toolkit_instance.get_tools())
            except Exception as e:
                logger.error(f"Error in data analysis toolkit get_tools: {e}")
                logger.error(f"Tool config: {tool}")
                raise

    return all_tools


class DataAnalysisToolkit(BaseToolkit):
    """
    Data Analysis toolkit providing Pandas-based data analysis capabilities.

    This is an internal tool that uses the conversation attachment bucket
    for file storage, enabling seamless integration with chat file uploads.
    """
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> Type[BaseModel]:
        """Get the configuration schema for the data analysis toolkit."""
        # Import PandasWrapper to get available tools schema
        from alita_sdk.tools.pandas.api_wrapper import PandasWrapper

        selected_tools = {
            x['name']: x['args_schema'].model_json_schema()
            for x in PandasWrapper.model_construct().get_available_tools()
        }

        return create_model(
            'data_analysis',
            bucket_name=(
                Optional[str],
                Field(
                    default=None,
                    title="Bucket name",
                    description="Bucket where files are stored (auto-injected from conversation)"
                )
            ),
            selected_tools=(
                List[Literal[tuple(selected_tools)]],
                Field(
                    default=[],
                    json_schema_extra={'args_schemas': selected_tools}
                )
            ),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Data Analysis",
                    "icon_url": "data-analysis.svg",
                    "hidden": True,  # Hidden from regular toolkit menu
                    "categories": ["internal_tool"],
                    "extra_categories": ["data analysis", "pandas", "dataframes", "data science"],
                }
            })
        )

    @classmethod
    def get_toolkit(
        cls,
        alita_client=None,
        llm=None,
        bucket_name: str = None,
        toolkit_name: Optional[str] = None,
        selected_tools: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Get toolkit with data analysis tools.

        Args:
            alita_client: Alita client instance (required)
            llm: LLM for code generation (optional, uses alita_client.llm if not provided)
            bucket_name: Conversation attachment bucket (required)
            toolkit_name: Optional name prefix for tools
            selected_tools: Optional list of tool names to include (default: all)
            **kwargs: Additional arguments

        Returns:
            DataAnalysisToolkit instance with configured tools

        Raises:
            ValueError: If alita_client or bucket_name is not provided
        """
        if not alita_client:
            raise ValueError("Alita client is required for data analysis")

        if not bucket_name:
            raise ValueError("bucket_name is required for data analysis (should be conversation attachment bucket)")

        # Import the PandasWrapper from existing toolkit
        from alita_sdk.tools.pandas.api_wrapper import PandasWrapper
        from alita_sdk.tools.base.tool import BaseAction

        # Create wrapper with conversation bucket
        wrapper = PandasWrapper(
            alita=alita_client,
            llm=llm,
            bucket_name=bucket_name
        )

        # Get tools from wrapper
        available_tools = wrapper.get_available_tools()
        tools = []

        for tool in available_tools:
            # Filter by selected_tools if provided
            if selected_tools and tool["name"] not in selected_tools:
                continue

            description = tool["description"]
            if toolkit_name:
                description = f"Toolkit: {toolkit_name}\n{description}"
            description = description[:1000]

            tools.append(BaseAction(
                api_wrapper=wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={"toolkit_name": toolkit_name, "toolkit_type": name} if toolkit_name else {}
            ))

        return cls(tools=tools)

    def get_tools(self):
        return self.tools
