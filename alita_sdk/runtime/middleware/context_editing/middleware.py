"""
ContextEditingMiddleware - Clears old tool outputs to reduce context size.

Uses LangChain's ClearToolUsesEdit strategy to automatically clear old tool
outputs when token thresholds are exceeded.

Usage:
    from alita_sdk.runtime.middleware.context_editing import ContextEditingMiddleware

    middleware = ContextEditingMiddleware(
        trigger_tokens=100000,
        keep_tool_results=3,
    )

    assistant = Assistant(
        alita=client,
        data=agent_data,
        client=llm,
        middleware=[middleware]
    )
"""

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Callable

from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.tools import BaseTool

from ..base import Middleware

logger = logging.getLogger(__name__)


class ContextEditingMiddleware(Middleware):
    """
    Middleware that clears old tool outputs to reduce context size.

    Uses LangChain's ClearToolUsesEdit strategy directly (no wrapper needed).
    Triggers when total context exceeds token threshold.

    Args:
        trigger_tokens: Token threshold to trigger clearing (default: 100000)
        keep_tool_results: Number of recent tool results to keep (default: 3)
        placeholder: Text to replace cleared outputs (default: "[cleared]")
        conversation_id: Conversation ID for scoping
        callbacks: Optional callbacks dict:
            - 'context_edited': Called when context editing occurs
    """

    def __init__(
        self,
        trigger_tokens: int = 100000,
        keep_tool_results: int = 3,
        placeholder: str = "[cleared]",
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        **kwargs
    ):
        super().__init__(conversation_id=conversation_id, callbacks=callbacks, **kwargs)

        self.trigger_tokens = trigger_tokens
        self.keep_tool_results = keep_tool_results
        self.placeholder = placeholder

        # Lazy-initialize the edit strategy
        self._edit_strategy = None

        logger.info(
            f"ContextEditingMiddleware initialized "
            f"(trigger={trigger_tokens} tokens, keep={keep_tool_results} results)"
        )

    def _ensure_edit_strategy(self):
        """Lazy initialization of ClearToolUsesEdit strategy."""
        if self._edit_strategy is None:
            try:
                from langchain.agents.middleware.context_editing import ClearToolUsesEdit

                self._edit_strategy = ClearToolUsesEdit(
                    trigger=self.trigger_tokens,
                    keep=self.keep_tool_results,
                    placeholder=self.placeholder,
                )
            except ImportError as e:
                logger.error(f"Failed to import ClearToolUsesEdit: {e}")
                raise

    def get_tools(self) -> List[BaseTool]:
        """No tools - operates on state directly."""
        return []

    def get_system_prompt(self) -> str:
        """No system prompt modification needed."""
        return ""

    def before_model(self, state: dict, config: dict) -> Optional[dict]:
        """
        Apply context editing before model call if threshold exceeded.

        Clears old tool outputs while keeping recent ones.

        Args:
            state: Current graph state with 'messages' key
            config: Runtime configuration

        Returns:
            State updates with modified messages, or None
        """
        self._ensure_edit_strategy()

        messages = state.get('messages', [])
        if not messages:
            return None

        try:
            # Create a deep copy to avoid mutating original state
            edited_messages = deepcopy(list(messages))
            original_contents = {id(m): getattr(m, 'content', None) for m in edited_messages}

            # Apply the edit strategy directly (modifies in place)
            self._edit_strategy.apply(
                edited_messages,
                count_tokens=count_tokens_approximately,
            )

            # Check if any messages were actually cleared
            cleared_count = sum(
                1 for m in edited_messages
                if hasattr(m, 'content') and m.content == self.placeholder
                and original_contents.get(id(m)) != self.placeholder
            )

            if cleared_count > 0:
                self._fire_callback('context_edited', {
                    'cleared_count': cleared_count,
                })
                logger.info(f"Context editing triggered: cleared {cleared_count} tool outputs")
                return {'messages': edited_messages}

            return None

        except Exception as e:
            logger.warning(f"ContextEditingMiddleware.before_model failed: {e}")
            return None
