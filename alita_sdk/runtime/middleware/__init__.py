"""
Alita SDK Middleware Module

Middleware provides modular extensions for agents, including:
- Tool injection
- System prompt modifications
- State restoration on conversation resume
- Callbacks for UI/CLI integration
- Context management (summarization)

Available middleware:
- PlanningMiddleware: Task planning and progress tracking
- SummarizationMiddleware: Automatic context compression when token limits approached
- ToolExceptionHandlerMiddleware: Smart tool error handling with strategies

Available strategies (for ToolExceptionHandlerMiddleware):
- TransformErrorStrategy: LLM-powered human-readable error messages with context
  * Includes original error traceback
  * Toolkit-specific FAQ documentation
  * Tool source code and dependencies (with LRU caching)
- CircuitBreakerStrategy: Disable tools after consecutive failures
- LoggingStrategy: Track error counts and fire callbacks
- CompositeStrategy: Chain multiple strategies sequentially

Usage:
    from alita_sdk.runtime.middleware import (
        PlanningMiddleware,
        SummarizationMiddleware,
        ToolExceptionHandlerMiddleware,
        MiddlewareManager
    )

    # Create planning middleware
    planning = PlanningMiddleware(
        conversation_id="session-123",
        connection_string="postgresql://...",
    )

    # Create summarization middleware (compresses old messages)
    summarization = SummarizationMiddleware(
        model=llm,  # BaseChatModel instance
        trigger=("tokens", 50000),
        keep=("messages", 10),
    )

    # Create error handler with default strategies (recommended)
    error_handler = ToolExceptionHandlerMiddleware.create_default(
        llm=llm,
        threshold=3
    )

    # Use with MiddlewareManager for multiple middleware
    manager = MiddlewareManager()
    manager.add(planning)
    manager.add(summarization)
    manager.add(error_handler)

    # Get tools and prompts
    tools = manager.get_all_tools()
    prompt = manager.get_combined_prompt()
"""

from .base import (
    Middleware,
    MiddlewareManager,
)
from .planning import PlanningMiddleware
from .summarization import SummarizationMiddleware
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
    "SummarizationMiddleware",
    "ToolExceptionHandlerMiddleware",
    # Strategies
    "ExceptionHandlerStrategy",
    "ExceptionContext",
    "TransformErrorStrategy",
    "CircuitBreakerStrategy",
    "LoggingStrategy",
    "CompositeStrategy",
]
