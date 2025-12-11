"""
Inventory Retrieval Toolkit.

Provides LangChain-compatible toolkit for querying pre-built knowledge graphs.
This is a pure retrieval toolkit - for ingestion, use the IngestionPipeline.

The toolkit can be added to any agent to provide knowledge graph context.
"""

from typing import Any, Optional, List, Dict, Literal, ClassVar

from langchain_core.tools import BaseTool
from langchain_core.tools import BaseToolkit
from pydantic import BaseModel, Field, ConfigDict, create_model

from .retrieval import InventoryRetrievalApiWrapper
from ...tools.base.tool import BaseAction
from ...tools.utils import clean_string, get_max_toolkit_length


class InventoryRetrievalToolkit(BaseToolkit):
    """
    Toolkit for querying pre-built Knowledge Graphs.
    
    This toolkit provides retrieval-only access to a knowledge graph
    that was built using the IngestionPipeline. It can be added to
    any agent to provide codebase context.
    
    Available tools:
    - search_graph: Search entities by name, type, or layer
    - get_entity: Get detailed entity info with relations
    - get_entity_content: Retrieve source code via citation
    - impact_analysis: Analyze upstream/downstream dependencies
    - get_related_entities: Get related entities
    - get_stats: Graph statistics
    - get_citations: Citation summaries
    - list_entities_by_type: List entities of a type
    - list_entities_by_layer: List entities in a layer
    """
    
    tools: List[BaseTool] = []
    toolkit_max_length: ClassVar[int] = 0
    
    # All available tools in this toolkit
    AVAILABLE_TOOLS: ClassVar[List[str]] = [
        "search_graph",
        "get_entity",
        "get_entity_content",
        "impact_analysis",
        "get_related_entities",
        "get_stats",
        "get_citations",
        "list_entities_by_type",
        "list_entities_by_layer",
    ]
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        """Return the configuration schema for this toolkit."""
        selected_tools = {
            x['name']: x['args_schema'].model_json_schema() 
            for x in InventoryRetrievalApiWrapper.model_construct().get_available_tools()
        }
        InventoryRetrievalToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        
        model = create_model(
            'inventory',
            graph_path=(str, Field(
                description="Path to the knowledge graph JSON file (required). "
                           "The graph should be built using IngestionPipeline."
            )),
            base_directory=(Optional[str], Field(
                default=None,
                description="Base directory for local content retrieval. "
                           "If set, get_entity_content will read from local files."
            )),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(
                default=[],
                json_schema_extra={'args_schemas': selected_tools}
            )),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Knowledge Graph Retrieval",
                    "icon_url": "inventory-icon.svg",
                    "max_length": InventoryRetrievalToolkit.toolkit_max_length,
                    "categories": ["knowledge management"],
                    "extra_categories": [
                        "knowledge graph", 
                        "code context", 
                        "impact analysis", 
                        "code search"
                    ],
                    "description": (
                        "Query a pre-built knowledge graph for codebase context. "
                        "Use IngestionPipeline to build the graph first."
                    ),
                }
            })
        )
        return model
    
    @classmethod
    def get_toolkit(
        cls,
        selected_tools: Optional[List[str]] = None,
        toolkit_name: str = "inventory",
        graph_path: Optional[str] = None,
        base_directory: Optional[str] = None,
        source_toolkits: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> "InventoryRetrievalToolkit":
        """
        Create and return an InventoryRetrievalToolkit instance.
        
        Args:
            selected_tools: List of tool names to include (None = all tools)
            toolkit_name: Name for this toolkit instance
            graph_path: Path to the knowledge graph JSON file
            base_directory: Base directory for local content retrieval
            source_toolkits: Dict of source toolkits for remote content retrieval
            **kwargs: Additional configuration
            
        Returns:
            Configured InventoryRetrievalToolkit instance
        """
        # Validate selected tools
        if selected_tools is None:
            selected_tools = cls.AVAILABLE_TOOLS
        else:
            selected_tools = [t for t in selected_tools if t in cls.AVAILABLE_TOOLS]
            if not selected_tools:
                selected_tools = cls.AVAILABLE_TOOLS
        
        # Create API wrapper
        api_wrapper = InventoryRetrievalApiWrapper(
            graph_path=graph_path or kwargs.get('graph_path', ''),
            base_directory=base_directory or kwargs.get('base_directory'),
            source_toolkits=source_toolkits or kwargs.get('source_toolkits', {}),
        )
        
        # Get available tools from wrapper
        available_tools = api_wrapper.get_available_tools()
        
        # Build tool mapping
        tool_map = {t['name']: t for t in available_tools}
        
        # Use clean toolkit name for context (max 1000 chars in description)
        toolkit_context = f" [Toolkit: {clean_string(toolkit_name, 0)}]" if toolkit_name else ''
        
        tools = []
        for tool_name in selected_tools:
            if tool_name in tool_map:
                tool_info = tool_map[tool_name]
                # Add toolkit context to description with character limit
                description = tool_info['description']
                if toolkit_context and len(description + toolkit_context) <= 1000:
                    description = description + toolkit_context
                tools.append(BaseAction(
                    api_wrapper=api_wrapper,
                    name=tool_name,
                    description=description,
                    args_schema=tool_info['args_schema']
                ))
        
        return cls(tools=tools)
    
    def get_tools(self) -> List[BaseTool]:
        """Return list of tools in this toolkit."""
        return self.tools


# Keep backward compatibility alias
InventoryToolkit = InventoryRetrievalToolkit
