"""
Context management for CLI chat history.

Provides token-aware context pruning, summarization, and session management
to optimize LLM context usage during CLI conversations.
"""

from .manager import CLIContextManager, sanitize_message_history
from .message import CLIMessage
from .token_estimation import estimate_tokens, calculate_total_tokens
from .strategies import (
    PruningStrategy,
    OldestFirstStrategy,
    ImportanceBasedStrategy,
    PruningStrategyFactory,
)
from .cleanup import purge_old_sessions

__all__ = [
    'CLIContextManager',
    'CLIMessage',
    'estimate_tokens',
    'calculate_total_tokens',
    'PruningStrategy',
    'OldestFirstStrategy',
    'ImportanceBasedStrategy',
    'PruningStrategyFactory',
    'purge_old_sessions',
    'sanitize_message_history',
]
