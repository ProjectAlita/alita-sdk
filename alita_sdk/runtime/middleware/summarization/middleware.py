"""
SummarizationMiddleware - Automatic context compression for agents.

Based on LangChain's prebuilt SummarizationMiddleware pattern.
Monitors message token counts and automatically summarizes older messages
when a threshold is reached, preserving recent messages.
"""

import uuid
import logging
from typing import Dict, List, Optional, Callable, Union, Literal, cast

from langchain_core.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.utils import (
    count_tokens_approximately,
    get_buffer_string,
    trim_messages,
)
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from ..base import Middleware

logger = logging.getLogger(__name__)

DEFAULT_SUMMARY_PROMPT = """<role>
Context Extraction Assistant
</role>

<primary_objective>
Your sole objective in this task is to extract the highest quality/most relevant context from the conversation history below.
</primary_objective>

<objective_information>
You're nearing the total number of input tokens you can accept, so you must extract the highest quality/most relevant pieces of information from your conversation history.
This context will then overwrite the conversation history presented below. Because of this, ensure the context you extract is only the most important information to continue working toward your overall goal.
</objective_information>

<instructions>
The conversation history below will be replaced with the context you extract in this step.
You want to ensure that you don't repeat any actions you've already completed, so the context you extract from the conversation history should be focused on the most important information to your overall goal.

You should structure your summary using the following sections. Each section acts as a checklist - you must populate it with relevant information or explicitly state "None" if there is nothing to report for that section:

## SESSION INTENT
What is the user's primary goal or request? What overall task are you trying to accomplish? This should be concise but complete enough to understand the purpose of the entire session.

## SUMMARY
Extract and record all of the most important context from the conversation history. Include important choices, conclusions, or strategies determined during this conversation. Include the reasoning behind key decisions. Document any rejected options and why they were not pursued.

## ARTIFACTS
What artifacts, files, or resources were created, modified, or accessed during this conversation? For file modifications, list specific file paths and briefly describe the changes made to each. This section prevents silent loss of artifact information.

## NEXT STEPS
What specific tasks remain to be completed to achieve the session intent? What should you do next?

</instructions>

The user will message you with the full message history from which you'll extract context to create a replacement. Carefully read through it all and think deeply about what information is most important to your overall goal and should be saved:

With all of this in mind, please carefully read over the entire conversation history, and extract the most important and relevant context to replace it so that you can free up space in the conversation history.
Respond ONLY with the extracted context. Do not include any additional information, or text before or after the extracted context.

<messages>
Messages to summarize:
{messages}
</messages>"""

_DEFAULT_MESSAGES_TO_KEEP = 20
_DEFAULT_TRIM_TOKEN_LIMIT = 4000
_DEFAULT_FALLBACK_MESSAGE_COUNT = 15

# Type aliases for context size configuration
ContextFraction = tuple[Literal["fraction"], float]
ContextTokens = tuple[Literal["tokens"], int]
ContextMessages = tuple[Literal["messages"], int]
ContextSize = Union[ContextFraction, ContextTokens, ContextMessages]


class SummarizationMiddleware(Middleware):
    """
    Middleware that automatically summarizes conversation history.

    Monitors message token counts and automatically summarizes older messages
    when a threshold is reached, preserving recent messages and maintaining
    context continuity by ensuring AI/Tool message pairs remain together.

    Args:
        model: LLM instance for generating summaries
        trigger: Threshold(s) that trigger summarization (tokens, messages, or fraction)
        keep: How much context to retain after summarization
        token_counter: Function to count tokens in messages
        summary_prompt: Prompt template for generating summaries
        trim_tokens_to_summarize: Maximum tokens when preparing messages for summarization
        conversation_id: Conversation ID for scoping
        callbacks: Optional callbacks dict for events
    """

    def __init__(
        self,
        model: BaseChatModel,
        *,
        trigger: Optional[Union[ContextSize, List[ContextSize]]] = None,
        keep: ContextSize = ("messages", _DEFAULT_MESSAGES_TO_KEEP),
        token_counter: Callable = count_tokens_approximately,
        summary_prompt: str = DEFAULT_SUMMARY_PROMPT,
        trim_tokens_to_summarize: Optional[int] = _DEFAULT_TRIM_TOKEN_LIMIT,
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        **kwargs
    ):
        super().__init__(conversation_id=conversation_id, callbacks=callbacks, **kwargs)

        self.model = model

        # Process trigger configuration
        if trigger is None:
            self.trigger: Optional[Union[ContextSize, List[ContextSize]]] = None
            self._trigger_conditions: List[ContextSize] = []
        elif isinstance(trigger, list):
            validated_list = [self._validate_context_size(item, "trigger") for item in trigger]
            self.trigger = validated_list
            self._trigger_conditions = validated_list
        else:
            validated = self._validate_context_size(trigger, "trigger")
            self.trigger = validated
            self._trigger_conditions = [validated]

        self.keep = self._validate_context_size(keep, "keep")
        self.token_counter = token_counter
        self.summary_prompt = summary_prompt
        self.trim_tokens_to_summarize = trim_tokens_to_summarize

        logger.info(
            f"SummarizationMiddleware initialized "
            f"(trigger={self.trigger}, keep={self.keep})"
        )

    @staticmethod
    def _validate_context_size(context: ContextSize, parameter_name: str) -> ContextSize:
        """Validate context configuration tuples."""
        kind, value = context
        if kind == "fraction":
            if not 0 < value <= 1:
                raise ValueError(f"Fractional {parameter_name} values must be between 0 and 1, got {value}.")
        elif kind in {"tokens", "messages"}:
            if value <= 0:
                raise ValueError(f"{parameter_name} thresholds must be greater than 0, got {value}.")
        else:
            raise ValueError(f"Unsupported context size type {kind} for {parameter_name}.")
        return context

    def get_tools(self) -> List[BaseTool]:
        """No tools - operates on state directly."""
        return []

    def get_system_prompt(self) -> str:
        """No system prompt modification needed."""
        return ""

    def before_model(self, state: dict, config: dict) -> Optional[dict]:
        """
        Process messages before model invocation, potentially triggering summarization.

        Args:
            state: The agent state with 'messages' key
            config: Runtime configuration

        Returns:
            Updated state with summarized messages if summarization was performed
        """
        messages = state.get('messages', [])
        if not messages:
            return None

        self._ensure_message_ids(messages)

        # Collect system messages first (before any filtering)
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]

        # Filter out old summaries (messages with lc_source=summarization)
        # to prevent summary accumulation
        def is_old_summary(msg):
            return (isinstance(msg, HumanMessage) and
                    msg.additional_kwargs.get('lc_source') == 'summarization')

        old_summaries = [m for m in messages if is_old_summary(m)]
        messages = [m for m in messages if not is_old_summary(m)]

        if old_summaries:
            logger.info(f"Filtered out {len(old_summaries)} old summaries from checkpoint")
        if system_messages:
            logger.info(f"Preserving {system_messages} system messages")

        if not messages:
            return None

        # Filter out system messages for token counting
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        total_tokens = self.token_counter(non_system_messages)

        # Log context status for debugging
        logger.info(
            f"[SummarizationMiddleware] Context check: {len(non_system_messages)} messages, "
            f"~{total_tokens} tokens, trigger={self.trigger}"
        )

        if not self._should_summarize(non_system_messages, total_tokens):
            logger.info("[SummarizationMiddleware] Threshold not reached, skipping summarization")
            return None

        cutoff_index = self._determine_cutoff_index(non_system_messages)

        if cutoff_index <= 0:
            return None

        # Partition non-system messages
        messages_to_summarize, preserved_messages = self._partition_messages(non_system_messages, cutoff_index)

        logger.info(
            f"Summarization triggered: {len(non_system_messages)} messages (excluding {len(system_messages)} system), "
            f"summarizing {len(messages_to_summarize)}, keeping {len(preserved_messages)}"
        )

        summary = self._create_summary(messages_to_summarize)
        logger.info(f"Summarization result: {summary}")
        new_messages = self._build_new_messages(summary)
        logger.info(f"Generated {len(new_messages)} new messages")

        # Store summary for later extraction
        from datetime import datetime, timezone
        state['_middleware_summary'] = {
            'text': summary,
            'original_count': len(non_system_messages),
            'summarized_count': len(messages_to_summarize),
            'preserved_count': len(preserved_messages),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'summarized_from_index': 0,
            'summarized_to_index': cutoff_index,
        }

        # Enhanced callback with summary data
        self._fire_callback('summarized', state['_middleware_summary'])

        # Use REMOVE_ALL_MESSAGES to clear checkpoint, then add system messages, summary, and preserved
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *system_messages,
                *new_messages,
                *preserved_messages,
            ]
        }

    def _should_summarize(self, messages: List[AnyMessage], total_tokens: int) -> bool:
        """Determine whether summarization should run for the current state."""
        if not self._trigger_conditions:
            return False

        for kind, value in self._trigger_conditions:
            if kind == "messages" and len(messages) >= value:
                logger.info(f"Trigger: message count {len(messages)} >= {value}")
                return True
            if kind == "tokens" and total_tokens >= value:
                logger.info(f"Trigger: token count {total_tokens} >= {value}")
                return True
            if kind == "fraction":
                # For fraction, we'd need model profile info
                # For now, skip fraction-based triggers
                pass

        return False

    def _determine_cutoff_index(self, messages: List[AnyMessage]) -> int:
        """Choose cutoff index respecting retention configuration."""
        kind, value = self.keep
        if kind == "tokens":
            token_based_cutoff = self._find_token_based_cutoff(messages, int(value))
            if token_based_cutoff is not None:
                return token_based_cutoff
            return self._find_safe_cutoff(messages, _DEFAULT_MESSAGES_TO_KEEP)
        elif kind == "messages":
            return self._find_safe_cutoff(messages, int(value))
        return self._find_safe_cutoff(messages, _DEFAULT_MESSAGES_TO_KEEP)

    def _find_token_based_cutoff(self, messages: List[AnyMessage], target_token_count: int) -> Optional[int]:
        """Find cutoff index based on target token retention."""
        if not messages:
            return 0

        if target_token_count <= 0:
            target_token_count = 1

        if self.token_counter(messages) <= target_token_count:
            return 0

        # Binary search for cutoff point
        left, right = 0, len(messages)
        cutoff_candidate = len(messages)
        max_iterations = len(messages).bit_length() + 1

        for _ in range(max_iterations):
            if left >= right:
                break

            mid = (left + right) // 2
            if self.token_counter(messages[mid:]) <= target_token_count:
                cutoff_candidate = mid
                right = mid
            else:
                left = mid + 1

        if cutoff_candidate == len(messages):
            cutoff_candidate = left

        if cutoff_candidate >= len(messages):
            if len(messages) == 1:
                return 0
            cutoff_candidate = len(messages) - 1

        # Advance past any ToolMessages to avoid splitting AI/Tool pairs
        return self._find_safe_cutoff_point(messages, cutoff_candidate)

    def _find_safe_cutoff(self, messages: List[AnyMessage], messages_to_keep: int) -> int:
        """Find safe cutoff point that preserves AI/Tool message pairs."""
        if len(messages) <= messages_to_keep:
            return 0

        target_cutoff = len(messages) - messages_to_keep
        return self._find_safe_cutoff_point(messages, target_cutoff)

    @staticmethod
    def _find_safe_cutoff_point(messages: List[AnyMessage], cutoff_index: int) -> int:
        """Find a safe cutoff point that doesn't split AI/Tool message pairs.

        If the message at cutoff_index is a ToolMessage, search backward for the
        AIMessage containing the corresponding tool_calls and adjust the cutoff.
        """
        if cutoff_index >= len(messages) or not isinstance(messages[cutoff_index], ToolMessage):
            return cutoff_index

        # Collect tool_call_ids from consecutive ToolMessages at/after cutoff
        tool_call_ids: set = set()
        idx = cutoff_index
        while idx < len(messages) and isinstance(messages[idx], ToolMessage):
            tool_msg = cast(ToolMessage, messages[idx])
            if tool_msg.tool_call_id:
                tool_call_ids.add(tool_msg.tool_call_id)
            idx += 1

        # Search backward for AIMessage with matching tool_calls
        for i in range(cutoff_index - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, AIMessage) and msg.tool_calls:
                ai_tool_call_ids = {tc.get("id") for tc in msg.tool_calls if tc.get("id")}
                if tool_call_ids & ai_tool_call_ids:
                    return i

        # Fallback: advance past ToolMessages
        return idx

    @staticmethod
    def _ensure_message_ids(messages: List[AnyMessage]) -> None:
        """Ensure all messages have unique IDs for the add_messages reducer."""
        for msg in messages:
            if msg.id is None:
                msg.id = str(uuid.uuid4())

    @staticmethod
    def _partition_messages(
        conversation_messages: List[AnyMessage],
        cutoff_index: int,
    ) -> tuple:
        """Partition messages into those to summarize and those to preserve."""
        messages_to_summarize = conversation_messages[:cutoff_index]
        preserved_messages = conversation_messages[cutoff_index:]
        return messages_to_summarize, preserved_messages

    @staticmethod
    def _build_new_messages(summary: str) -> List[HumanMessage]:
        """Build the summary message(s) to add to state."""
        return [
            HumanMessage(
                content=f"Here is a summary of the conversation to date:\n\n{summary}",
                additional_kwargs={"lc_source": "summarization"},
            )
        ]

    def _create_summary(self, messages_to_summarize: List[AnyMessage]) -> str:
        """Generate summary for the given messages."""
        if not messages_to_summarize:
            return "No previous conversation history."

        logger.info(f"Messages to summarize: {len(messages_to_summarize)}")
        for i, msg in enumerate(messages_to_summarize[:5]):
            logger.info(f"  [{i}] {type(msg).__name__}: {str(msg.content)[:100]}...")

        trimmed_messages = self._trim_messages_for_summary(messages_to_summarize)
        logger.info(f"Trimmed messages: {len(trimmed_messages)}")
        if not trimmed_messages:
            return "Previous conversation was too long to summarize."

        # Format messages manually to ensure content is included
        formatted_messages = self._format_messages_for_summary(trimmed_messages)
        logger.info(f"Formatted messages length: {len(formatted_messages)}")

        if not formatted_messages.strip():
            return "No conversation content to summarize."

        try:
            # Check if the prompt template has {messages} placeholder
            if '{messages}' in self.summary_prompt:
                prompt_content = self.summary_prompt.format(messages=formatted_messages).rstrip()
            else:
                # If no placeholder, append messages to the custom instructions
                prompt_content = f"{self.summary_prompt}\n\n<messages>\n{formatted_messages}\n</messages>"
            logger.info(f"Full prompt length: {len(prompt_content)}")
            # Wrap prompt in HumanMessage for proper LLM invocation
            response = self.model.invoke([
                HumanMessage(content=prompt_content)
            ])
            content = response.content if hasattr(response, 'content') else str(response)
            return content.strip() if isinstance(content, str) else str(content)
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Error generating summary: {e!s}"

    @staticmethod
    def _format_messages_for_summary(messages: List[AnyMessage]) -> str:
        """Format messages into a string for summarization, skipping system messages."""
        formatted_parts = []
        for msg in messages:
            # Skip system messages
            if isinstance(msg, SystemMessage):
                continue
            role = type(msg).__name__.replace("Message", "")
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if content and content.strip():
                formatted_parts.append(f"{role}: {content}")
        return "\n\n".join(formatted_parts)

    def _trim_messages_for_summary(self, messages: List[AnyMessage]) -> List[AnyMessage]:
        """Trim messages to fit within summary generation limits."""
        try:
            if self.trim_tokens_to_summarize is None:
                return messages
            return cast(
                List[AnyMessage],
                trim_messages(
                    messages,
                    max_tokens=self.trim_tokens_to_summarize,
                    token_counter=self.token_counter,
                    start_on="human",
                    strategy="last",
                    allow_partial=True,
                    include_system=True,
                ),
            )
        except Exception:
            return messages[-_DEFAULT_FALLBACK_MESSAGE_COUNT:]
