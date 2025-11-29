"""
Token estimation utilities for CLI context management.

Uses tiktoken for accurate token counting with fallback to character-based estimation.
"""

from typing import List, Optional, TYPE_CHECKING
from functools import lru_cache

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

if TYPE_CHECKING:
    from .message import CLIMessage


@lru_cache(maxsize=8)
def get_encoding_for_model(model: str = 'gpt-4') -> Optional[object]:
    """
    Get the appropriate tiktoken encoding for a given model.
    Defaults to cl100k_base (used by most modern models) and only specifies exceptions.
    
    Args:
        model: Model name to get encoding for
        
    Returns:
        Tiktoken encoding object or None if not available
    """
    if not TIKTOKEN_AVAILABLE:
        return None

    try:
        # Get model encoding map from tiktoken
        model_encoding_map = tiktoken.model.MODEL_TO_ENCODING
        # Default to cl100k_base for unknown models (most modern models use this)
        encoding_name = model_encoding_map.get(model.lower(), 'cl100k_base')
        return tiktoken.get_encoding(encoding_name)
    except Exception:
        return None


def estimate_tokens(text: str, model: str = 'gpt-4') -> int:
    """
    Accurate token estimation using tiktoken.
    Falls back to character-based estimation if tiktoken is not available.
    
    Args:
        text: Text to estimate tokens for
        model: Model name for encoding selection
        
    Returns:
        Estimated token count
    """
    if not text or not isinstance(text, str):
        return 0

    if TIKTOKEN_AVAILABLE:
        encoder = get_encoding_for_model(model)
        if encoder:
            try:
                return len(encoder.encode(text))
            except Exception:
                pass

    # Fallback: Simple approximation (~4 characters per token for GPT models)
    return max(1, len(text) // 4)


def calculate_total_tokens(
    messages: List['CLIMessage'],
    summaries: Optional[List[dict]] = None,
    include_only: bool = True
) -> int:
    """
    Calculate total tokens from messages and summaries.
    
    Args:
        messages: List of CLIMessage objects
        summaries: Optional list of summary dictionaries with 'token_count' key
        include_only: If True, only count messages where included=True
        
    Returns:
        Total token count
    """
    message_tokens = 0
    for msg in messages:
        if include_only and not msg.included:
            continue
        message_tokens += msg.token_count
    
    summary_tokens = 0
    if summaries:
        for summary in summaries:
            summary_tokens += summary.get('token_count', 0)
    
    return message_tokens + summary_tokens


def estimate_message_tokens(role: str, content: str, model: str = 'gpt-4') -> int:
    """
    Estimate tokens for a chat message including role overhead.
    
    Chat messages have overhead for role tokens and message formatting.
    This provides a more accurate estimate for chat-style messages.
    
    Args:
        role: Message role (user, assistant, system)
        content: Message content
        model: Model name for encoding
        
    Returns:
        Estimated token count including overhead
    """
    # Base content tokens
    content_tokens = estimate_tokens(content, model)
    
    # Add overhead for message formatting (role, separators, etc.)
    # Most chat models add ~4 tokens per message for formatting
    overhead = 4
    
    # Role name tokens (typically 1-2 tokens)
    role_tokens = estimate_tokens(role, model)
    
    return content_tokens + overhead + role_tokens
