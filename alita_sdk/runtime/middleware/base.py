"""
Base Middleware class for agent extensions.

Middleware pattern allows modular injection of:
- Tools (with automatic discovery)
- System prompt modifications
- State restoration on conversation resume
- Callbacks for UI/CLI integration

Inspired by LangChain's middleware pattern but adapted for Alita's architecture.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict, Callable

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class Middleware(ABC):
    """
    Base class for agent middleware.

    Middleware can:
    1. Provide tools to the agent
    2. Inject system prompts/instructions
    3. Restore state when resuming conversations
    4. Register callbacks for state changes

    Subclasses must implement:
    - get_tools(): Return list of tools to add to agent
    - get_system_prompt(): Return system prompt addition (or empty string)

    Optionally override:
    - on_conversation_start(): Called when conversation begins/resumes
    - on_conversation_end(): Called when conversation ends
    """

    def __init__(
        self,
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        **kwargs
    ):
        """
        Initialize middleware.

        Args:
            conversation_id: Conversation ID for state scoping
            callbacks: Optional dict of callback functions for events
            **kwargs: Additional configuration passed to subclasses
        """
        self.conversation_id = conversation_id
        self.callbacks = callbacks or {}
        self._initialized = False

    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """
        Return list of tools to add to the agent.

        Returns:
            List of BaseTool instances
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Return system prompt addition for this middleware.

        The returned string will be appended to the agent's base prompt.
        Return empty string if no prompt modification needed.

        Returns:
            System prompt string to append
        """
        pass

    def on_conversation_start(self, conversation_id: str) -> Optional[str]:
        """
        Called when a conversation starts or resumes.

        Use this to restore state, load previous plans, etc.

        Args:
            conversation_id: The conversation ID being started/resumed

        Returns:
            Optional message to include in conversation context
        """
        self.conversation_id = conversation_id
        return None

    def on_conversation_end(self, conversation_id: str) -> None:
        """
        Called when a conversation ends.

        Use this for cleanup, state persistence, etc.

        Args:
            conversation_id: The conversation ID ending
        """
        pass

    def _fire_callback(self, event: str, data: Any) -> None:
        """
        Fire a callback if registered.

        Args:
            event: Event name (e.g., 'plan_updated', 'step_completed')
            data: Event data to pass to callback
        """
        if event in self.callbacks:
            try:
                self.callbacks[event](data)
            except Exception as e:
                logger.warning(f"Middleware callback '{event}' failed: {e}")


class MiddlewareManager:
    """
    Manages middleware instances for an agent session.

    Collects tools and prompts from all registered middleware,
    and coordinates lifecycle events.
    """

    def __init__(self):
        self._middleware: List[Middleware] = []

    def add(self, middleware: Middleware) -> 'MiddlewareManager':
        """
        Add middleware to the manager.

        Args:
            middleware: Middleware instance to add

        Returns:
            Self for chaining
        """
        self._middleware.append(middleware)
        return self

    def get_all_tools(self) -> List[BaseTool]:
        """
        Collect tools from all middleware.

        Returns:
            Combined list of tools from all middleware
        """
        tools = []
        for mw in self._middleware:
            try:
                tools.extend(mw.get_tools())
            except Exception as e:
                logger.error(f"Failed to get tools from middleware {type(mw).__name__}: {e}")
        return tools

    def get_combined_prompt(self) -> str:
        """
        Combine system prompts from all middleware.

        Returns:
            Combined system prompt additions
        """
        prompts = []
        for mw in self._middleware:
            try:
                prompt = mw.get_system_prompt()
                if prompt:
                    prompts.append(prompt)
            except Exception as e:
                logger.error(f"Failed to get prompt from middleware {type(mw).__name__}: {e}")
        return "\n\n---\n\n".join(prompts)

    def start_conversation(self, conversation_id: str) -> List[str]:
        """
        Notify all middleware of conversation start.

        Args:
            conversation_id: The conversation ID starting

        Returns:
            List of context messages from middleware
        """
        messages = []
        for mw in self._middleware:
            try:
                msg = mw.on_conversation_start(conversation_id)
                if msg:
                    messages.append(msg)
            except Exception as e:
                logger.error(f"Middleware {type(mw).__name__} failed on_conversation_start: {e}")
        return messages

    def end_conversation(self, conversation_id: str) -> None:
        """
        Notify all middleware of conversation end.

        Args:
            conversation_id: The conversation ID ending
        """
        for mw in self._middleware:
            try:
                mw.on_conversation_end(conversation_id)
            except Exception as e:
                logger.error(f"Middleware {type(mw).__name__} failed on_conversation_end: {e}")
