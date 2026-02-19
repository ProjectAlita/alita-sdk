"""
Context Editing Middleware - Automatic tool output clearing for agents.

Wraps LangChain's ContextEditingMiddleware to automatically clear old tool
outputs when token thresholds are exceeded.

Usage:
    from alita_sdk.runtime.middleware.context_editing import ContextEditingMiddleware

    middleware = ContextEditingMiddleware(
        trigger_tokens=100000,
        keep_tool_results=3,
    )
"""

from .middleware import ContextEditingMiddleware

__all__ = [
    "ContextEditingMiddleware",
]
