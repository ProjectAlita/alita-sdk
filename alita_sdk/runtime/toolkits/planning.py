"""
PlanningToolkit - Runtime toolkit for agent plan management.

Provides tools for creating, tracking, and completing multi-step execution plans.
Supports two storage backends:
1. PostgreSQL - when pgvector_configuration with connection_string is provided
2. Filesystem - when no connection string (local CLI usage)
"""

from typing import ClassVar, List, Any, Literal, Optional, Callable

from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo

from ..tools.planning import PlanningWrapper
from ...tools.base.tool import BaseAction
from ...tools.utils import clean_string, get_max_toolkit_length


class PlanningToolkit(BaseToolkit):
    """
    Toolkit for agent plan management.
    
    Provides tools for creating, updating, and tracking execution plans.
    Supports PostgreSQL (production) and filesystem (local) storage backends.
    Plans are scoped by conversation_id.
    """
    tools: List[BaseTool] = []
    _toolkit_max_length: ClassVar[int] = 50  # Use ClassVar to avoid Pydantic treating it as field
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        """
        Returns the configuration schema for the Planning toolkit.
        
        Used by the UI to generate the toolkit configuration form.
        """
        # Define available tools
        selected_tools = {
            'update_plan': {
                'title': 'UpdatePlanInput',
                'type': 'object',
                'properties': {
                    'title': {'type': 'string', 'description': "Title for the plan"},
                    'steps': {'type': 'array', 'items': {'type': 'string'}, 'description': "List of step descriptions"},
                    'conversation_id': {'type': 'string', 'description': "Conversation ID (auto-injected)"}
                },
                'required': ['title', 'steps', 'conversation_id']
            },
            'complete_step': {
                'title': 'CompleteStepInput', 
                'type': 'object',
                'properties': {
                    'step_number': {'type': 'integer', 'description': "Step number to complete (1-indexed)"},
                    'conversation_id': {'type': 'string', 'description': "Conversation ID (auto-injected)"}
                },
                'required': ['step_number', 'conversation_id']
            },
            'get_plan_status': {
                'title': 'GetPlanStatusInput',
                'type': 'object', 
                'properties': {
                    'conversation_id': {'type': 'string', 'description': "Conversation ID (auto-injected)"}
                },
                'required': ['conversation_id']
            },
            'delete_plan': {
                'title': 'DeletePlanInput',
                'type': 'object',
                'properties': {
                    'conversation_id': {'type': 'string', 'description': "Conversation ID (auto-injected)"}
                },
                'required': ['conversation_id']
            }
        }
        
        PlanningToolkit._toolkit_max_length = get_max_toolkit_length(selected_tools)
        
        return create_model(
            "planning",
            # Tool selection
            selected_tools=(
                List[Literal[tuple(selected_tools)]], 
                Field(
                    default=list(selected_tools.keys()),
                    json_schema_extra={'args_schemas': selected_tools}
                )
            ),
            __config__=ConfigDict(
                json_schema_extra={
                    'metadata': {
                        "label": "Planning",
                        "description": "Tools for managing multi-step execution plans with progress tracking. Uses PostgreSQL when configured, filesystem otherwise.",
                        "icon_url": None,
                        "max_length": PlanningToolkit._toolkit_max_length,
                        "categories": ["planning", "internal_tool"],
                        "extra_categories": ["task management", "todo", "progress tracking"]
                    }
                }
            )
        )
    
    @classmethod
    def get_toolkit(
        cls,
        toolkit_name: Optional[str] = None,
        selected_tools: Optional[List[str]] = None,
        pgvector_configuration: Optional[dict] = None,
        storage_dir: Optional[str] = None,
        plan_callback: Optional[Any] = None,
        conversation_id: Optional[str] = None,
        **kwargs
    ):
        """
        Create a PlanningToolkit instance with configured tools.
        
        Args:
            toolkit_name: Optional name prefix for tools
            selected_tools: List of tool names to include (default: all)
            pgvector_configuration: PostgreSQL configuration dict with connection_string.
                                   If not provided, uses filesystem storage.
            storage_dir: Directory for filesystem storage (when no pgvector_configuration)
            plan_callback: Optional callback function called when plan changes (for CLI UI)
            conversation_id: Conversation ID for scoping plans.
                            For server: from elitea_core payload. For CLI: session_id.
            **kwargs: Additional configuration options
            
        Returns:
            PlanningToolkit instance with configured tools
        """
        if selected_tools is None:
            selected_tools = ['update_plan', 'complete_step', 'get_plan_status', 'delete_plan']
        
        tools = []
        
        # Extract connection string from pgvector configuration (if provided)
        connection_string = None
        if pgvector_configuration:
            connection_string = pgvector_configuration.get('connection_string', '')
            if hasattr(connection_string, 'get_secret_value'):
                connection_string = connection_string.get_secret_value()
        
        # Create wrapper - it will auto-select storage backend
        wrapper = PlanningWrapper(
            connection_string=connection_string if connection_string else None,
            conversation_id=conversation_id,
            storage_dir=storage_dir,
            plan_callback=plan_callback,
        )
        
        # Use clean toolkit name for context (max 1000 chars in description)
        toolkit_context = f" [Toolkit: {clean_string(toolkit_name, 0)}]" if toolkit_name else ''
        
        # Create tools from wrapper
        available_tools = wrapper.get_available_tools()
        for tool in available_tools:
            if tool["name"] not in selected_tools:
                continue
            
            # Add toolkit context to description with character limit
            description = tool["description"]
            if toolkit_context and len(description + toolkit_context) <= 1000:
                description = description + toolkit_context
            
            tools.append(BaseAction(
                api_wrapper=wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"]
            ))
        
        return cls(tools=tools)
    
    def get_tools(self) -> List[BaseTool]:
        """Return the list of configured tools."""
        return self.tools
