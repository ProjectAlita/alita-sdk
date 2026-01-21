"""
Alita SDK Middleware Module

Middleware provides modular extensions for agents, including:
- Tool injection
- System prompt modifications
- State restoration on conversation resume
- Callbacks for UI/CLI integration

Available middleware:
- PlanningMiddleware: Task planning and progress tracking

Usage:
    from alita_sdk.runtime.middleware import PlanningMiddleware, MiddlewareManager

    # Create middleware
    planning = PlanningMiddleware(
        conversation_id="session-123",
        connection_string="postgresql://...",
    )

    # Use with MiddlewareManager for multiple middleware
    manager = MiddlewareManager()
    manager.add(planning)

    # Get tools and prompts
    tools = manager.get_all_tools()
    prompt = manager.get_combined_prompt()
"""

from .base import Middleware, MiddlewareManager
from .planning import PlanningMiddleware

__all__ = [
    "Middleware",
    "MiddlewareManager",
    "PlanningMiddleware",
]
