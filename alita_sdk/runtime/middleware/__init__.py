"""
Alita SDK Middleware Module

Middleware provides modular extensions for agents, including:
- Tool injection
- System prompt modifications
- State restoration on conversation resume
- Callbacks for UI/CLI integration

Available middleware:
- PlanningMiddleware: Task planning and progress tracking
- ToolExceptionHandlerMiddleware: Smart tool error handling with strategies

Available strategies (for ToolExceptionHandlerMiddleware):
- TransformErrorStrategy: LLM-powered human-readable error messages
- CircuitBreakerStrategy: Disable tools after consecutive failures
- LoggingStrategy: Track error counts and fire callbacks
- CompositeStrategy: Chain multiple strategies sequentially

Usage:
    from alita_sdk.runtime.middleware import (
        PlanningMiddleware,
        ToolExceptionHandlerMiddleware,
        TransformErrorStrategy,
        CircuitBreakerStrategy,
        LoggingStrategy,
        MiddlewareManager
    )

    # Create planning middleware
    planning = PlanningMiddleware(
        conversation_id="session-123",
        connection_string="postgresql://...",
    )

    # Create error handler with default strategies (recommended)
    error_handler = ToolExceptionHandlerMiddleware.create_default(
        llm=llm,
        threshold=3
    )

    # Or create with explicit strategies
    error_handler = ToolExceptionHandlerMiddleware(
        strategies=[
            LoggingStrategy(),
            CircuitBreakerStrategy(threshold=3),
            TransformErrorStrategy(llm=llm, use_llm=True)
        ]
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
from .strategies import (
    ExceptionHandlerStrategy,
    ExceptionContext,
    TransformErrorStrategy,
    CircuitBreakerStrategy,
    LoggingStrategy,
    CompositeStrategy
)

__all__ = [
    "Middleware",
    "MiddlewareManager",
    "PlanningMiddleware",
    "ToolExceptionHandlerMiddleware",
    # Strategies
    "ExceptionHandlerStrategy",
    "ExceptionContext",
    "TransformErrorStrategy",
    "CircuitBreakerStrategy",
    "LoggingStrategy",
    "CompositeStrategy",
]
