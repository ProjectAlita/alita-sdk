"""
SummarizationMiddleware - Automatic context compression for agents.

Extends LangChain's prebuilt SummarizationMiddleware with Alita-specific features:
- Callback support
- Summarization details tracking for analytics
- Old summary filtering from checkpoints

Note: System messages are excluded from summarization and NOT persisted in chunks.
They should be handled by the agent's system prompt mechanism.
"""

import logging
from typing import Callable, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from ..base import Middleware

logger = logging.getLogger(__name__)


from langchain.agents.middleware.summarization import (
    SummarizationMiddleware as LangChainSummarizationMiddleware,
    ContextSize,
    DEFAULT_SUMMARY_PROMPT,
    _DEFAULT_MESSAGES_TO_KEEP,
)


class SummarizationMiddleware(LangChainSummarizationMiddleware, Middleware):
    """
    Extends LangChain's SummarizationMiddleware with Alita-specific features.

    Additional features:
    - conversation_id for session scoping
    - callbacks for UI/CLI integration ('started', 'summarized' events)
    - last_summarization_details tracking for analytics
    - System message preservation
    - Old summary filtering from checkpoints
    """

    def __init__(
        self,
        model: BaseChatModel,
        *,
        trigger: Optional[ContextSize | List[ContextSize]] = None,
        keep: ContextSize = ("messages", _DEFAULT_MESSAGES_TO_KEEP),
        token_counter: Callable = count_tokens_approximately,
        summary_prompt: str = DEFAULT_SUMMARY_PROMPT,
        trim_tokens_to_summarize: Optional[int] = 4000,
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        **kwargs
    ):
        # Initialize LangChain's middleware
        LangChainSummarizationMiddleware.__init__(
            self,
            model=model,
            trigger=trigger,
            keep=keep,
            token_counter=token_counter,
            summary_prompt=summary_prompt,
            trim_tokens_to_summarize=trim_tokens_to_summarize,
        )
        # Initialize Alita's middleware base (for callbacks, conversation_id)
        Middleware.__init__(self, conversation_id=conversation_id, callbacks=callbacks, **kwargs)

        self.last_context_info = None  # Always updated with current context state

        logger.info(
            f"SummarizationMiddleware initialized "
            f"(trigger={self.trigger}, keep={self.keep})"
        )

    def get_tools(self) -> List:
        """No tools - operates on state directly."""
        return []

    def get_system_prompt(self) -> str:
        """No system prompt modification needed."""
        return ""

    def _get_messages_since_last_summary(self, messages: list) -> tuple[list, int]:
        """
        Get messages since the last summarization.

        Only counts messages that appear AFTER the most recent summary message.
        This prevents counting already-summarized messages in subsequent turns.

        Returns:
            Tuple of (messages_since_summary, last_summary_index)
            If no summary found, returns (all_messages, -1)
        """
        last_summary_index = -1
        for i, msg in enumerate(messages):
            if isinstance(msg, HumanMessage) and msg.additional_kwargs.get('lc_source') == 'summarization':
                last_summary_index = i

        if last_summary_index >= 0:
            return messages[last_summary_index + 1:], last_summary_index
        else:
            return messages, -1

    def before_model(self, state: dict, config: dict) -> Optional[dict]:
        """
        Process messages before model invocation.

        Extends LangChain's implementation with:
        - Old summary filtering
        - Callback firing
        - Summarization details tracking

        Note: System messages are excluded from summarization but NOT persisted
        in chunks - they should be handled by the agent's system prompt mechanism.
        """
        messages = state.get('messages', [])
        if not messages:
            # Set context_info even for empty messages
            self.last_context_info = {
                'message_count': 0,
                'token_count': 0,
                'summarized': False,
            }
            return None

        self._ensure_message_ids(messages)

        # Get only messages since the last summary for token counting
        # This prevents counting already-summarized messages in subsequent turns
        messages_since_summary, last_summary_idx = self._get_messages_since_last_summary(messages)

        if last_summary_idx >= 0:
            logger.info(
                f"Found previous summary at index {last_summary_idx}, "
                f"counting {len(messages_since_summary)} messages since then "
                f"(total in checkpoint: {len(messages)})"
            )

        # Filter out system messages for token counting
        non_system_messages = [m for m in messages_since_summary if not isinstance(m, SystemMessage)]

        if not non_system_messages:
            # Set context_info even when only system messages exist
            self.last_context_info = {
                'message_count': 0,
                'token_count': 0,
                'summarized': False,
            }
            return None

        total_tokens = self.token_counter(non_system_messages)

        # Always track current context info (non-system messages/tokens only)
        self.last_context_info = {
            'message_count': len(non_system_messages),
            'token_count': total_tokens,
            'summarized': False,
        }

        if not self._should_summarize(non_system_messages, total_tokens):
            return None

        cutoff_index = self._determine_cutoff_index(non_system_messages)

        if cutoff_index <= 0:
            return None

        messages_to_summarize, preserved_messages = self._partition_messages(
            non_system_messages, cutoff_index
        )

        logger.info(
            f"Summarization triggered: {len(non_system_messages)} messages, "
            f"summarizing {len(messages_to_summarize)}, keeping {len(preserved_messages)}"
        )

        # Fire 'started' callback (Alita-specific)
        self._fire_callback('started', {
            'original_count': len(non_system_messages),
            'to_summarize_count': len(messages_to_summarize),
            'to_preserve_count': len(preserved_messages),
        })

        summary = self._create_summary(messages_to_summarize)
        new_messages = self._build_new_messages(summary)

        # Calculate token counts for analytics (non-system messages only)
        summary_tokens = self.token_counter(new_messages) if new_messages else 0
        preserved_tokens = self.token_counter(preserved_messages) if preserved_messages else 0
        new_total_tokens = summary_tokens + preserved_tokens
        new_message_count = len(new_messages) + len(preserved_messages)

        # Update context_info with post-summarization state (unified format)
        self.last_context_info = {
            'message_count': new_message_count,
            'token_count': new_total_tokens,
            'summarized': True,
            'summarized_count': len(messages_to_summarize),
            'preserved_count': len(preserved_messages),
        }

        # Fire 'summarized' callback (Alita-specific)
        self._fire_callback('summarized', self.last_context_info)

        # Return summarized messages (system messages handled by system prompt, not persisted)
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved_messages,
            ]
        }

    def after_model(self, state: dict, config: dict) -> Optional[dict]:
        """
        Recalculate context info after model response.

        This ensures context_info reflects the FINAL state (including new LLM response)
        that will be saved to the checkpoint.
        """
        messages = state.get('messages', [])
        if not messages:
            self.last_context_info = {
                'message_count': 0,
                'token_count': 0,
                'summarized': False,
            }
            return None

        # Get only messages since the last summary (same logic as before_model)
        messages_since_summary, _ = self._get_messages_since_last_summary(messages)

        # Filter out system messages
        non_system_messages = [m for m in messages_since_summary if not isinstance(m, SystemMessage)]

        if not non_system_messages:
            self.last_context_info = {
                'message_count': 0,
                'token_count': 0,
                'summarized': False,
            }
            return None

        total_tokens = self.token_counter(non_system_messages)

        # Preserve 'summarized' flag from before_model if it was set
        was_summarized = self.last_context_info.get('summarized', False) if self.last_context_info else False

        # Update context_info with FINAL state
        updated_info = {
            'message_count': len(non_system_messages),
            'token_count': total_tokens,
            'summarized': was_summarized,
        }

        # Preserve summarization stats if they exist
        if was_summarized and self.last_context_info:
            if 'summarized_count' in self.last_context_info:
                updated_info['summarized_count'] = self.last_context_info['summarized_count']
            if 'preserved_count' in self.last_context_info:
                updated_info['preserved_count'] = self.last_context_info['preserved_count']

        self.last_context_info = updated_info

        return None  # No state updates needed

    def _create_summary(self, messages_to_summarize: list) -> str:
        """Generate summary for the given messages.

        Override to handle response.content vs response.text compatibility.
        """
        if not messages_to_summarize:
            return "No previous conversation history."

        trimmed_messages = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed_messages:
            return "Previous conversation was too long to summarize."

        # Format messages for summary
        formatted_messages = ""
        try:
            from langchain_core.messages.utils import get_buffer_string
            formatted_messages = get_buffer_string(trimmed_messages)
        except Exception as e:
            logger.warning(f"get_buffer_string failed: {e}")

        # Fallback formatting if get_buffer_string returns empty or fails
        if not formatted_messages or not formatted_messages.strip():
            formatted_parts = []
            for msg in trimmed_messages:
                if isinstance(msg, SystemMessage):
                    continue
                role = type(msg).__name__.replace("Message", "")
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if content and content.strip():
                    formatted_parts.append(f"{role}: {content}")
            formatted_messages = "\n\n".join(formatted_parts)

        if not formatted_messages.strip():
            return "No conversation content to summarize."

        try:
            if '{messages}' in self.summary_prompt:
                prompt_content = self.summary_prompt.format(messages=formatted_messages).rstrip()
            else:
                # Template doesn't have placeholder, append messages
                prompt_content = f"{self.summary_prompt}\n\n<messages>\n{formatted_messages}\n</messages>"

            # Wrap in HumanMessage for model compatibility
            response = self.model.invoke([HumanMessage(content=prompt_content)])

            # Handle both .text and .content
            if hasattr(response, 'content'):
                content = response.content
                result = content.strip() if isinstance(content, str) else str(content)
            elif hasattr(response, 'text'):
                result = response.text.strip()
            else:
                result = str(response)
            return result
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Error generating summary: {e!s}"

    def _trim_messages_for_summary(self, messages: list) -> list:
        """Trim messages to fit within summary generation limits.

        Override to not require starting on human message.
        """
        from langchain_core.messages.utils import trim_messages

        try:
            if self.trim_tokens_to_summarize is None:
                return messages
            return list(trim_messages(
                messages,
                max_tokens=self.trim_tokens_to_summarize,
                token_counter=self.token_counter,
                strategy="last",
                allow_partial=True,
                include_system=True,
            ))
        except Exception as e:
            logger.warning(f"trim_messages failed: {e}, using fallback")
            return messages[-15:]
