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

    def before_model(self, state: dict, config: dict) -> Optional[dict]:
        """
        Called before model invocation. Can modify state (messages).

        Override this to implement pre-model logic like:
        - Summarization (compress old messages)
        - Context editing (clear old tool outputs)
        - Token management

        Args:
            state: Current graph state with 'messages' key
            config: Runtime configuration (thread_id, etc.)

        Returns:
            State updates dict (e.g., {'messages': [...]}) or None
        """
        return None

    def after_model(self, state: dict, config: dict) -> Optional[dict]:
        """
        Called after model invocation. Can modify state.

        Args:
            state: Current graph state after model response
            config: Runtime configuration

        Returns:
            State updates dict or None
        """
        return None

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

    def run_before_model(self, state: dict, config: dict) -> tuple[dict, list]:
        """
        Run all middleware before_model hooks.

        Hooks can modify state, especially messages (for summarization, context editing).
        Returns both the processed state (for LLM to use) and RemoveMessage operations
        (for LangGraph checkpoint).

        Args:
            state: Current graph state with 'messages' key
            config: Runtime configuration

        Returns:
            Tuple of (updated_state, remove_ops)
            - updated_state: State with processed messages for LLM
            - remove_ops: Only RemoveMessage operations for checkpoint (not actual messages)
        """
        try:
            from langchain_core.messages import RemoveMessage
        except ImportError:
            RemoveMessage = None

        remove_ops = []
        for mw in self._middleware:
            try:
                updates = mw.before_model(state, config)
                if updates and 'messages' in updates:
                    # Only collect RemoveMessage operations for checkpoint
                    # The actual messages are already in state after processing
                    if RemoveMessage is not None:
                        for msg in updates['messages']:
                            if isinstance(msg, RemoveMessage):
                                remove_ops.append(msg)
                    # Apply updates in-memory for LLM processing
                    original_count = len(state.get('messages', []))
                    state = {**state, 'messages': self._apply_message_updates(
                        state.get('messages', []), updates['messages']
                    )}
                    new_count = len(state.get('messages', []))
                    logger.info(
                        f"[MiddlewareManager] {type(mw).__name__} applied: "
                        f"{original_count} -> {new_count} messages, RemoveMessage ops: {len(remove_ops)}"
                    )
            except Exception as e:
                logger.error(f"Middleware {type(mw).__name__} before_model failed: {e}")
        return state, remove_ops

    def run_after_model(self, state: dict, config: dict) -> dict:
        """
        Run all middleware after_model hooks.

        Args:
            state: Current graph state after model response
            config: Runtime configuration

        Returns:
            Updated state dict
        """
        for mw in self._middleware:
            try:
                updates = mw.after_model(state, config)
                if updates:
                    state = {**state, **updates}
            except Exception as e:
                logger.error(f"Middleware {type(mw).__name__} after_model failed: {e}")
        return state

    def get_context_info(self) -> Dict[str, Any]:
        """
        Get current context info (always available, not just after summarization).

        Returns:
            Dict with message_count, token_count, summarized (always present)
        """
        for mw in self._middleware:
            if hasattr(mw, 'last_context_info') and mw.last_context_info:
                return mw.last_context_info

        return {
            'message_count': 0,
            'token_count': 0,
            'summarized': False,
        }

    @staticmethod
    def _apply_message_updates(current_messages: list, updates: list) -> list:
        """
        Apply message updates including RemoveMessage operations.

        Handles LangGraph's RemoveMessage pattern for clearing old messages.

        Args:
            current_messages: Current list of messages
            updates: List of messages/RemoveMessage operations

        Returns:
            Updated message list
        """
        try:
            from langchain_core.messages import RemoveMessage
            from langgraph.graph.message import REMOVE_ALL_MESSAGES
        except ImportError:
            # If imports fail, just return updates as-is
            return updates

        new_messages = []
        for msg in updates:
            if isinstance(msg, RemoveMessage):
                if msg.id == REMOVE_ALL_MESSAGES:
                    current_messages = []
                else:
                    current_messages = [m for m in current_messages if m.id != msg.id]
            else:
                new_messages.append(msg)

        return current_messages + new_messages
