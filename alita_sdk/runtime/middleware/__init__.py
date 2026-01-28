"""
Alita SDK Middleware Module

Middleware provides modular extensions for agents, including:
- Tool injection
- System prompt modifications
- State restoration on conversation resume
- Callbacks for UI/CLI integration

Available middleware:
- PlanningMiddleware: Task planning and progress tracking
- ToolExceptionHandlerMiddleware: Smart tool error handling with retry and LLM-powered error messages

Usage:
    from alita_sdk.runtime.middleware import PlanningMiddleware, ToolExceptionHandlerMiddleware, MiddlewareManager

    # Create middleware
    planning = PlanningMiddleware(
        conversation_id="session-123",
        connection_string="postgresql://...",
    )

    error_handler = ToolExceptionHandlerMiddleware(
        conversation_id="session-123",
        llm=llm,
        use_llm_for_errors=True
    )

    # Use with MiddlewareManager for multiple middleware
    manager = MiddlewareManager()
    manager.add(planning)
    manager.add(error_handler)

    # Get tools and prompts
    tools = manager.get_all_tools()
    prompt = manager.get_combined_prompt()
"""

from .base import Middleware, MiddlewareManager
from .planning import PlanningMiddleware
from .tool_exception_handler import ToolExceptionHandlerMiddleware

__all__ = [
    "Middleware",
    "MiddlewareManager",
    "PlanningMiddleware",
    "ToolExceptionHandlerMiddleware",
]
