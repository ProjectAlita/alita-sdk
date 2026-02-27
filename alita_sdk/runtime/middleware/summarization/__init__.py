"""
Summarization Middleware - Automatic context compression for agents.

Wraps LangChain's SummarizationMiddleware to provide automatic conversation
summarization when token thresholds are exceeded.

Usage:
    from alita_sdk.runtime.middleware.summarization import SummarizationMiddleware

    middleware = SummarizationMiddleware(
        model="openai:gpt-4o-mini",
        trigger_tokens=50000,
        keep_messages=10,
    )
"""

from .middleware import SummarizationMiddleware

__all__ = [
    "SummarizationMiddleware",
]
