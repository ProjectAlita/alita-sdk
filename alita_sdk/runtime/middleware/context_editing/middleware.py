"""
ContextEditingMiddleware - Clears old tool outputs to reduce context size.

Similar to PlanningMiddleware, this middleware:
1. Wraps LangChain's prebuilt ContextEditingMiddleware
2. Provides before_model hook to clear old tool results
3. Supports configuration via constructor

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
from typing import Any, Dict, List, Optional, Callable

from langchain_core.tools import BaseTool

from ..base import Middleware

logger = logging.getLogger(__name__)


class _MinimalRuntime:
    """Minimal runtime interface for LangChain AgentMiddleware."""
    def __init__(self, config: dict):
        self.config = config


class ContextEditingMiddleware(Middleware):
    """
    Middleware that clears old tool outputs to reduce context size.

    Wraps LangChain's ContextEditingMiddleware with ClearToolUsesEdit.
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

        # Lazy-initialize LangChain middleware
        self._lc_middleware = None

        logger.info(
            f"ContextEditingMiddleware initialized "
            f"(trigger={trigger_tokens} tokens, keep={keep_tool_results} results)"
        )

    def _ensure_middleware(self):
        """Lazy initialization of LangChain middleware."""
        if self._lc_middleware is None:
            try:
                from langchain.agents.middleware import (
                    ContextEditingMiddleware as LCContextEditingMiddleware,
                    ClearToolUsesEdit,
                )

                self._lc_middleware = LCContextEditingMiddleware(
                    edits=[
                        ClearToolUsesEdit(
                            trigger=self.trigger_tokens,
                            keep=self.keep_tool_results,
                            placeholder=self.placeholder,
                        ),
                    ],
                )
            except ImportError as e:
                logger.error(f"Failed to import LangChain ContextEditingMiddleware: {e}")
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
        self._ensure_middleware()

        try:
            runtime = _MinimalRuntime(config)
            updates = self._lc_middleware.before_model(state, runtime)

            if updates:
                cleared_count = self._count_cleared(updates)
                self._fire_callback('context_edited', {
                    'cleared_count': cleared_count,
                })
                logger.info(f"Context editing triggered: cleared {cleared_count} tool outputs")

            return updates

        except Exception as e:
            logger.warning(f"ContextEditingMiddleware.before_model failed: {e}")
            return None

    def _count_cleared(self, updates: dict) -> int:
        """Count how many tool outputs were cleared."""
        messages = updates.get('messages', [])
        return sum(
            1 for m in messages
            if hasattr(m, 'content') and m.content == self.placeholder
        )
