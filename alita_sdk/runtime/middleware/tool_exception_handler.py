"""
Tool Exception Handler Middleware

Provides intelligent error handling for tool execution with:
- LLM-powered human-readable error messages
- Circuit breaker pattern for repeatedly failing tools
- Error tracking and monitoring
- Graceful degradation strategies
"""

import logging
import traceback
from functools import wraps
from typing import List, Optional, Dict, Any, Callable, Type, Union

from alita_sdk.runtime.langchain.constants import FAQ_BY_TOOLKIT_TYPE
from alita_sdk.runtime.utils.mcp_oauth import McpAuthorizationRequired
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from .base import Middleware

logger = logging.getLogger(__name__)


class ToolExceptionHandlerMiddleware(Middleware):
    """
    Wraps agent tools with intelligent exception handling.

    Features:
    - LLM-powered human-readable error messages
    - Circuit breaker to prevent repeated failures
    - Error logging and callbacks
    - Configurable exception handling strategies

    Example:
        ```python
        error_handler = ToolExceptionHandlerMiddleware(
            conversation_id=conv_id,
            llm=llm,  # LLM for generating human-readable errors
            use_llm_for_errors=True,
            circuit_breaker_threshold=5
        )

        assistant = client.application(
            application_id='app_123',
            middleware=[error_handler]
        )
        ```
    """

    def __init__(
        self,
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        llm: Optional[BaseChatModel] = None,
        use_llm_for_errors: bool = True,
        return_detailed_errors: bool = False,
        circuit_breaker_threshold: int = 5,
        excluded_tools: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize Tool Exception Handler Middleware.

        Args:
            conversation_id: Conversation ID for state tracking
            callbacks: Optional dict of callback functions for events
            llm: LLM instance for generating human-readable error messages
            use_llm_for_errors: Use LLM to generate human-readable error messages
            return_detailed_errors: Include stack traces in error messages (for debugging)
            circuit_breaker_threshold: Number of consecutive failures before disabling tool
            excluded_tools: List of tool names to not wrap with error handling
        """
        super().__init__(conversation_id, callbacks, **kwargs)

        self.llm = llm
        self.use_llm_for_errors = use_llm_for_errors and llm is not None
        self.return_detailed_errors = return_detailed_errors
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.excluded_tools = set(excluded_tools or [])

        # Error tracking
        self.error_counts: Dict[str, int] = {}  # Total errors per tool
        self.consecutive_errors: Dict[str, int] = {}  # Consecutive errors (resets on success)
        self.circuit_breakers: Dict[str, bool] = {}  # Circuit breaker state per tool

        # Wrapped tools cache to avoid double-wrapping
        self._wrapped_tools_cache: Dict[str, BaseTool] = {}

        logger.info(
            f"ToolExceptionHandlerMiddleware initialized: "
            f"use_llm={self.use_llm_for_errors}, "
            f"circuit_breaker_threshold={circuit_breaker_threshold}"
        )

    def get_tools(self) -> List[BaseTool]:
        """
        This middleware doesn't add new tools.
        Tools are wrapped via the wrap_tool() method called by the agent.
        """
        return []

    def get_system_prompt(self) -> str:
        """Add instructions for handling tool errors."""
        return """### Tool Error Handling

When a tool fails with an error:
* Read the error message carefully - it contains guidance on what went wrong
* All the issues are mostly related to 3rd party APIs used by the tools (corresponding exceptions will be raised)
* If the error suggests a fix (e.g., missing or invalid parameter), reply with suggested fix
* If no alternative exists, inform the user about the issue and ask for help from support team (https://elitea.ai/docs/support/contact-support/)
"""

    def wrap_tool(self, tool: BaseTool) -> BaseTool:
        """
        Wrap a tool with exception handling logic.

        Args:
            tool: Original tool to wrap

        Returns:
            Wrapped tool with error handling, or original if excluded/already wrapped
        """
        # Don't wrap if tool is in exclusion list
        if tool.name in self.excluded_tools:
            logger.debug(f"Tool '{tool.name}' is excluded from error handling")
            return tool

        # Check if already wrapped (avoid double-wrapping)
        if tool.name in self._wrapped_tools_cache:
            logger.debug(f"Tool '{tool.name}' already wrapped, returning cached version")
            return self._wrapped_tools_cache[tool.name]

        # Check circuit breaker
        if self.circuit_breakers.get(tool.name, False):
            logger.warning(f"Circuit breaker open for tool '{tool.name}', returning disabled version")
            return self._create_disabled_tool(tool)

        # Get the original function to wrap
        original_func = self._get_tool_function(tool)

        # Create wrapped function
        @wraps(original_func)
        def error_handled_func(*args, **kwargs) -> str:
            """Wrapped function with error handling."""
            try:
                # Execute original tool
                result = original_func(*args, **kwargs)

                # Success - reset consecutive error counter
                if tool.name in self.consecutive_errors:
                    prev_errors = self.consecutive_errors[tool.name]
                    self.consecutive_errors[tool.name] = 0
                    if prev_errors > 0:
                        logger.info(f"Tool '{tool.name}' recovered after {prev_errors} consecutive errors")

                return result

            except McpAuthorizationRequired:
                # MCP authorization required - re-raise to be handled by agent
                raise

            except Exception as e:
                # Track error
                self._track_error(tool.name)

                logger.error(
                    f"Tool '{tool.name}' failed: {type(e).__name__}: {e}"
                )

                # Fire callback
                self._fire_callback('tool_error', {
                    'tool_name': tool.name,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'args': args,
                    'kwargs': kwargs,
                })

                # Check circuit breaker
                self._check_circuit_breaker(tool.name)

                # Return formatted error message
                return self._format_error_message(tool, e, args, kwargs)

        # Create wrapped tool with same metadata
        try:
            wrapped_tool = StructuredTool.from_function(
                func=error_handled_func,
                name=tool.name,
                description=tool.description,
                args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None,
                return_direct=getattr(tool, 'return_direct', False),
            )

            # Preserve metadata if present
            if hasattr(tool, 'metadata'):
                wrapped_tool.metadata = tool.metadata

            # Cache the wrapped tool
            self._wrapped_tools_cache[tool.name] = wrapped_tool

            logger.debug(f"Successfully wrapped tool '{tool.name}' with error handling")
            return wrapped_tool

        except Exception as e:
            logger.error(f"Failed to wrap tool '{tool.name}': {e}", exc_info=True)
            return tool  # Return original tool if wrapping fails

    def _get_tool_function(self, tool: BaseTool) -> Callable:
        """Extract the callable function from a tool."""
        if hasattr(tool, 'func') and callable(tool.func):
            return tool.func
        elif hasattr(tool, '_run') and callable(tool._run):
            return tool._run
        elif callable(tool):
            return tool
        else:
            raise ValueError(f"Cannot extract callable from tool '{tool.name}'")

    def _track_error(self, tool_name: str) -> None:
        """Track error occurrence for a tool."""
        # Increment total error count
        self.error_counts[tool_name] = self.error_counts.get(tool_name, 0) + 1

        # Increment consecutive error count
        self.consecutive_errors[tool_name] = self.consecutive_errors.get(tool_name, 0) + 1

    def _check_circuit_breaker(self, tool_name: str) -> None:
        """Check if circuit breaker should be opened for a tool."""
        consecutive = self.consecutive_errors.get(tool_name, 0)

        if consecutive >= self.circuit_breaker_threshold:
            self.circuit_breakers[tool_name] = True
            logger.error(
                f"Circuit breaker OPENED for tool '{tool_name}' after "
                f"{consecutive} consecutive failures"
            )
            self._fire_callback('circuit_breaker_opened', {
                'tool_name': tool_name,
                'consecutive_failures': consecutive,
            })

    def _format_error_message(
        self,
        tool,
        error: Exception,
        args: tuple,
        kwargs: dict
    ) -> str:
        """
        Format user-friendly error message, optionally using LLM.

        Args:
            tool_name: Name of failed tool
            error: Exception that occurred
            args: Positional arguments passed to tool
            kwargs: Keyword arguments passed to tool

        Returns:
            Formatted error message
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # If LLM-powered error messages are enabled, use LLM
        if self.use_llm_for_errors:
            try:
                human_error = self._generate_human_readable_error(
                    tool.name, tool.description, tool.metadata, error_type, error_msg, args, kwargs
                )
                if human_error:
                    return human_error
            except Exception as llm_error:
                logger.warning(
                    f"Failed to generate LLM error message: {llm_error}, falling back to default"
                )

        # Default error message format
        base_msg = f"Tool '{tool.name}' failed"

        if self.return_detailed_errors:
            # Include full stack trace (for debugging)
            stack_trace = ''.join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            return (
                f"{base_msg}.\n\n"
                f"Error Type: {error_type}\n"
                f"Error Message: {error_msg}\n\n"
                f"Stack Trace:\n{stack_trace}\n\n"
                f"Arguments: args={args}, kwargs={kwargs}"
            )
        else:
            # User-friendly message without stack trace
            return (
                f"{base_msg}.\n\n"
                f"Error: {error_msg}\n\n"
                f"Please check the input parameters and try again, "
                f"or use an alternative approach."
            )

    def _generate_human_readable_error(
        self,
        tool_name: str,
        tool_description: Optional[str],
        tool_metadata: Optional[Dict[str, Any]],
        error_type: str,
        error_msg: str,
        args: tuple,
        kwargs: dict
    ) -> Optional[str]:
        """
        Use LLM to generate a human-readable error message.

        Args:
            tool_name: Name of failed tool
            error_type: Type of exception
            error_msg: Exception message
            args: Tool arguments
            kwargs: Tool keyword arguments

        Returns:
            Human-readable error message, or None if generation fails
        """
        if not self.llm:
            return None

        try:
            # Create prompt for LLM
            system_prompt = """You are a helpful assistant that explains technical errors in simple terms.
Your job is to translate technical error messages into clear, actionable guidance for users.

IMPORTANT:
- Usually the errors are related to 3rd party APIs used by the tools (don't suggest code changes)
- If the error suggests a fix (e.g., missing or invalid parameter), reply with suggested fix
- Avoid suggesting actions that are not related API configuration (like browser cache clearing, etc) since it is not sessions related


Guidelines:
- Be concise and clear
- Explain what went wrong in simple terms
- Suggest concrete next steps or fixes
- Avoid technical jargon unless necessary
- Be empathetic and helpful
- Keep response under 150 words
- Suggest contacting support if issue persists: https://elitea.ai/docs/support/contact-support/
"""

            user_prompt = f"""A tool called "{tool_name}" failed with the following error:

Error Type: {error_type}
Error Message: {error_msg}

Tool Arguments:
{self._format_args_for_llm(args, kwargs)}

Tool Description:
{tool_description or "N/A"}

Tool Metadata:
{tool_metadata or "N/A"}

FAQ by a tool type:
{FAQ_BY_TOOLKIT_TYPE.get(tool_metadata.get('toolkit_type') if tool_metadata else None, 'general')}

Please explain this error in simple terms and suggest what the user should do next."""

            # Invoke LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = self.llm.invoke(messages)

            # Extract content from response
            if hasattr(response, 'content'):
                human_error = response.content.strip()
                logger.debug(f"Generated human-readable error for '{tool_name}': {human_error[:100]}...")
                return human_error

            return None

        except Exception as e:
            logger.error(f"Error generating human-readable message: {e}", exc_info=True)
            return None

    def _format_args_for_llm(self, args: tuple, kwargs: dict) -> str:
        """Format tool arguments for LLM prompt."""
        parts = []

        if args:
            # Truncate long args
            args_str = str(args)
            if len(args_str) > 200:
                args_str = args_str[:200] + "..."
            parts.append(f"Positional: {args_str}")

        if kwargs:
            # Truncate long kwargs
            kwargs_str = str(kwargs)
            if len(kwargs_str) > 200:
                kwargs_str = kwargs_str[:200] + "..."
            parts.append(f"Keyword: {kwargs_str}")

        return "\n".join(parts) if parts else "(no arguments)"

    def _create_disabled_tool(self, tool: BaseTool) -> BaseTool:
        """Create a disabled version of a tool (for circuit breaker)."""
        def disabled_func(*args, **kwargs) -> str:
            return (
                f"Tool '{tool.name}' is temporarily disabled due to repeated failures. "
                f"Please use an alternative approach or contact support if the issue persists."
            )

        disabled_tool = StructuredTool.from_function(
            func=disabled_func,
            name=tool.name,
            description=f"[DISABLED] {tool.description}",
            args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None,
        )

        return disabled_tool

    def on_conversation_start(self, conversation_id: str) -> Optional[str]:
        """Reset error tracking on conversation start."""
        super().on_conversation_start(conversation_id)

        # Reset error counters for new conversation
        self.error_counts.clear()
        self.consecutive_errors.clear()
        self.circuit_breakers.clear()
        self._wrapped_tools_cache.clear()

        logger.info(f"Reset error tracking for conversation {conversation_id}")
        return None

    def on_conversation_end(self, conversation_id: str) -> None:
        """Log error statistics on conversation end."""
        super().on_conversation_end(conversation_id)

        if self.error_counts:
            logger.info(
                f"Tool error summary for conversation {conversation_id}: "
                f"{dict(self.error_counts)}"
            )

            # Fire summary callback
            self._fire_callback('conversation_error_summary', {
                'conversation_id': conversation_id,
                'error_counts': dict(self.error_counts),
                'circuit_breakers': dict(self.circuit_breakers),
            })

