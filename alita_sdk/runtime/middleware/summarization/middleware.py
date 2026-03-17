"""
SummarizationMiddleware - Automatic context compression for agents.

Extends LangChain's prebuilt SummarizationMiddleware with Alita-specific features:
- Callback support
- Summarization details tracking for analytics
- Old summary filtering from checkpoints

Note: System messages are excluded from summarization and NOT persisted in chunks.
They should be handled by the agent's system prompt mechanism.
"""

import math
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph.message import REMOVE_ALL_MESSAGES

logger = logging.getLogger(__name__)

# Fixed token estimate per image — mirrors the default in langchain-core's
# upcoming count_tokens_approximately (tokens_per_image=85, aligned with
# OpenAI's low-resolution image token cost). Update when langchain-core
# is upgraded past the version that adds native image support.
_IMAGE_TOKEN_ESTIMATE = 85


def _count_tokens_image_aware(
    messages,
    *,
    chars_per_token: float = 4.0,
    extra_tokens_per_message: float = 3.0,
) -> int:
    """Token counter that skips base64 image data in multimodal messages.

    Replaces LangChain's ``count_tokens_approximately`` which does
    ``repr(message.content)`` for list content — that stringifies the full
    base64 payload and inflates counts by tens of thousands of fake tokens.

    For each ``image_url`` / ``image`` block a fixed estimate of
    ``_IMAGE_TOKEN_ESTIMATE`` tokens is used instead.

    Iterates ``messages`` directly (no ``convert_to_messages``) to avoid
    LangChain treating content-block lists as tuples of ``(role, content)``.
    """
    token_count = 0.0
    for message in messages:
        message_chars = 0
        image_count = 0

        # Normalise to (content, tool_calls, tool_call_id)
        if isinstance(message, BaseMessage):
            content = message.content
            tool_calls = getattr(message, "tool_calls", None) if isinstance(message, AIMessage) else None
            tool_call_id = getattr(message, "tool_call_id", None) if isinstance(message, ToolMessage) else None
        elif isinstance(message, dict):
            content = message.get("content", message.get("text", ""))
            role = message.get("role", message.get("type", ""))
            tool_calls = message.get("tool_calls") if role in ("assistant", "ai") else None
            tool_call_id = message.get("tool_call_id")
        else:
            token_count += math.ceil(len(repr(message)) / chars_per_token) + extra_tokens_per_message
            continue

        if isinstance(content, str):
            message_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    message_chars += len(repr(block))
                    continue
                block_type = block.get("type")
                if block_type == "text":
                    message_chars += len(block.get("text", ""))
                elif block_type in ("image_url", "image"):
                    image_count += 1
                else:
                    message_chars += len(repr(block))
        elif content:
            message_chars += len(repr(content))

        if tool_calls and not isinstance(content, list):
            message_chars += len(repr(tool_calls))

        if tool_call_id:
            message_chars += len(str(tool_call_id))

        token_count += math.ceil(message_chars / chars_per_token)
        token_count += extra_tokens_per_message
        token_count += image_count * _IMAGE_TOKEN_ESTIMATE

    return math.ceil(token_count)


from langchain.agents.middleware.summarization import (
    SummarizationMiddleware as LangChainSummarizationMiddleware,
    ContextSize,
    DEFAULT_SUMMARY_PROMPT,
    _DEFAULT_MESSAGES_TO_KEEP,
)


class SummarizationMiddleware(LangChainSummarizationMiddleware):
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
        trigger: Optional[Union[ContextSize, List[ContextSize]]] = None,
        keep: ContextSize = ("messages", _DEFAULT_MESSAGES_TO_KEEP),
        token_counter: Callable = _count_tokens_image_aware,
        summary_prompt: Optional[str] = None,
        trim_tokens_to_summarize: Optional[int] = 4000,
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        **kwargs
    ):
        # Use DEFAULT_SUMMARY_PROMPT when None or empty string is passed
        effective_summary_prompt = summary_prompt if summary_prompt else DEFAULT_SUMMARY_PROMPT

        # Initialize LangChain's middleware
        super().__init__(
            model=model,
            trigger=trigger,
            keep=keep,
            token_counter=token_counter,
            summary_prompt=effective_summary_prompt,
            trim_tokens_to_summarize=trim_tokens_to_summarize,
        )

        # Alita-specific attributes (no multiple inheritance needed)
        self.conversation_id = conversation_id
        self.callbacks = callbacks or {}
        self.last_context_info = None
        self._last_fitting_count = 0

        logger.info(
            f"SummarizationMiddleware initialized "
            f"(trigger={self.trigger}, keep={self.keep})"
        )

    def get_tools(self) -> List[BaseTool]:
        """No tools - operates on state directly."""
        return []

    def get_system_prompt(self) -> str:
        """No system prompt modification needed."""
        return ""

    def _fire_callback(self, event: str, data: Any) -> None:
        """Fire a callback if registered."""
        if event in self.callbacks:
            try:
                self.callbacks[event](data)
            except Exception as e:
                logger.warning(f"Middleware callback '{event}' failed: {e}")

    def on_conversation_start(self, conversation_id: str) -> Optional[str]:
        """Called when conversation starts. Update conversation_id."""
        self.conversation_id = conversation_id
        return None

    def on_conversation_end(self, conversation_id: str) -> None:
        """Called when conversation ends."""
        pass

    def _is_summary_message(self, msg) -> bool:
        """
        Detect if a message is a summary from previous summarization.

        Checks both:
        - LangChain marker: additional_kwargs['lc_source'] == 'summarization'
        - Content pattern: "Here is a summary of the conversation to date:"
        """
        # Check LangChain marker (for properly typed HumanMessage)
        if isinstance(msg, HumanMessage):
            if msg.additional_kwargs.get('lc_source') == 'summarization':
                return True

        # Check content pattern (for dict messages from backend)
        content = None
        if isinstance(msg, dict):
            content = msg.get('content', '')
        elif hasattr(msg, 'content'):
            content = msg.content

        if content and isinstance(content, str):
            if content.startswith("Here is a summary of the conversation to date:"):
                return True

        return False

    def _find_last_summary_index(self, messages: list) -> int:
        """
        Find the index of the most recent summary message.

        Returns -1 if no summary found.
        """
        for i in range(len(messages) - 1, -1, -1):
            if self._is_summary_message(messages[i]):
                return i
        return -1

    def _determine_cutoff_index(self, messages: list) -> int:
        if self.keep[0] != "messages":
            return super()._determine_cutoff_index(messages)

        preserved_count = self.keep[1]
        if len(messages) <= preserved_count:
            return 0

        preserved_msgs = messages[-preserved_count:]
        pre_preserved = messages[:-preserved_count]

        preserved_tokens = self.token_counter(preserved_msgs)

        trigger_limit = self.trigger[1] if self.trigger and self.trigger[0] == "tokens" else None
        if trigger_limit is None:
            self._last_fitting_count = 0
            return super()._determine_cutoff_index(messages)

        remaining_budget = max(0, trigger_limit - preserved_tokens)

        fitting_count = 0
        tokens_so_far = 0
        for msg in reversed(pre_preserved):
            msg_tokens = self.token_counter([msg])
            if tokens_so_far + msg_tokens <= remaining_budget:
                fitting_count += 1
                tokens_so_far += msg_tokens
            else:
                break

        self._last_fitting_count = fitting_count
        cutoff_index = len(pre_preserved) - fitting_count
        return cutoff_index

    def before_model(self, state: dict, config: dict) -> Optional[dict]:
        """
        Process messages before model invocation.

        Key behavior:
        - Detects existing summaries (from previous summarization)
        - Only processes messages AFTER the last summary
        - Preserves the existing summary in output

        Note: System messages are excluded from summarization but NOT persisted
        in chunks - they should be handled by the agent's system prompt mechanism.
        """
        messages = state.get('messages', [])
        if not messages:
            self.last_context_info = {
                'message_count': 0,
                'token_count': 0,
                'summarized': False,
            }
            return None

        self._ensure_message_ids(messages)

        # Filter out system messages for processing
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        if not non_system_messages:
            self.last_context_info = {
                'message_count': 0,
                'token_count': 0,
                'summarized': False,
            }
            return None

        # Find existing summary - only process messages AFTER it
        last_summary_idx = self._find_last_summary_index(non_system_messages)
        existing_summary = None
        messages_since_summary = non_system_messages

        if last_summary_idx >= 0:
            existing_summary = non_system_messages[last_summary_idx]
            messages_since_summary = non_system_messages[last_summary_idx + 1:]
            logger.info(
                f"Found existing summary at index {last_summary_idx}, "
                f"processing {len(messages_since_summary)} messages since summary"
            )

        if not messages_since_summary:
            # Only summary exists, nothing new to process
            self.last_context_info = {
                'message_count': 1 if existing_summary else 0,
                'token_count': self.token_counter([existing_summary]) if existing_summary else 0,
                'summarized': False,
            }
            return None

        total_tokens = self.token_counter(messages_since_summary)

        # Track context info (messages since last summary only)
        self.last_context_info = {
            'message_count': len(messages_since_summary) + (1 if existing_summary else 0),
            'token_count': total_tokens,
            'summarized': False,
        }

        if not self._should_summarize(messages_since_summary, total_tokens):
            return None

        cutoff_index = self._determine_cutoff_index(messages_since_summary)

        if cutoff_index <= 0:
            return None

        messages_to_summarize, preserved_messages = self._partition_messages(
            messages_since_summary, cutoff_index
        )

        logger.info(
            f"Summarization triggered: {len(messages_since_summary)} new messages since last summary, "
            f"summarizing {len(messages_to_summarize)} (incl. prev summary: {existing_summary is not None}), "
            f"keeping {len(preserved_messages)}"
        )

        # Fire 'started' callback (Alita-specific)
        self._fire_callback('started', {
            'original_count': len(non_system_messages),
            'to_summarize_count': len(messages_to_summarize),
            'to_preserve_count': len(preserved_messages),
        })

        summary = self._create_summary(messages_to_summarize)

        # Calculate token counts for analytics (summary is not in state — only preserved count)
        preserved_tokens = self.token_counter(preserved_messages) if preserved_messages else 0

        # Update context_info with post-summarization state (unified format)
        self.last_context_info = {
            'message_count': len(preserved_messages),
            'token_count': preserved_tokens,
            'summarized': True,
            'summarized_count': len(messages_to_summarize),
            'preserved_count': len(preserved_messages),
            'fitting_count': self._last_fitting_count,
            'summary_content': summary,
        }

        # Fire 'summarized' callback (Alita-specific)
        self._fire_callback('summarized', self.last_context_info)

        # Return preserved messages only — summary is not stored in state.
        # pylon_main persists it in conversation meta and sends it back via chat_history.
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
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

        # Filter out system messages, RemoveMessage operations, and summary messages
        countable_messages = [
            m for m in messages
            if not isinstance(m, SystemMessage)
            and not isinstance(m, RemoveMessage)
            and not self._is_summary_message(m)
        ]

        if not countable_messages:
            self.last_context_info = {
                'message_count': 0,
                'token_count': 0,
                'summarized': False,
            }
            return None

        total_tokens = self.token_counter(countable_messages)

        # Preserve 'summarized' flag from before_model if it was set
        was_summarized = self.last_context_info.get('summarized', False) if self.last_context_info else False

        # Update context_info with FINAL state
        updated_info = {
            'message_count': len(countable_messages),
            'token_count': total_tokens,
            'summarized': was_summarized,
        }

        # Preserve summarization stats if they exist
        if was_summarized and self.last_context_info:
            if 'summarized_count' in self.last_context_info:
                updated_info['summarized_count'] = self.last_context_info['summarized_count']
            if 'preserved_count' in self.last_context_info:
                updated_info['preserved_count'] = self.last_context_info['preserved_count']
            if 'summary_content' in self.last_context_info:
                updated_info['summary_content'] = self.last_context_info['summary_content']

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
            logger.info(f'Summary response has no content or text attribute, using {result}')
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
