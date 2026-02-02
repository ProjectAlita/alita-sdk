"""
Exception Handler Strategies for Tool Error Handling

Provides pluggable strategies for handling tool execution exceptions.
Strategies can be composed to create sophisticated error handling pipelines.

Available strategies:
- TransformErrorStrategy: Transform errors into human-readable messages using LLM
- CircuitBreakerStrategy: Disable tools after consecutive failures
- LoggingStrategy: Track error statistics and fire callbacks
- CompositeStrategy: Chain multiple strategies sequentially

Example:
    from alita_sdk.runtime.middleware.strategies import (
        TransformErrorStrategy,
        CircuitBreakerStrategy,
        LoggingStrategy
    )

    strategies = [
        LoggingStrategy(callbacks={'tool_error': my_callback}),
        CircuitBreakerStrategy(threshold=3),
        TransformErrorStrategy(llm=my_llm, use_llm=True)
    ]

    middleware = ToolExceptionHandlerMiddleware(strategies=strategies)
"""

import logging
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, ToolException

logger = logging.getLogger(__name__)


@dataclass
class ExceptionContext:
    """
    Context object passed through strategy chain.

    Each strategy can read/modify this context, particularly the error_message.
    """
    tool: BaseTool
    error: Exception
    args: tuple
    kwargs: dict
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def tool_name(self) -> str:
        """Get tool name."""
        return self.tool.name

    @property
    def error_type(self) -> str:
        """Get error type name."""
        return type(self.error).__name__

    @property
    def error_str(self) -> str:
        """Get error message string."""
        return str(self.error)

    @property
    def error_traceback(self) -> str:
        """Get full error traceback."""
        return ''.join(
            traceback.format_exception(
                type(self.error),
                self.error,
                self.error.__traceback__
            )
        )


class ExceptionHandlerStrategy(ABC):
    """
    Abstract base class for exception handling strategies.

    Strategies process exceptions in sequence, with each strategy
    potentially modifying the ExceptionContext.
    """

    @abstractmethod
    def handle_exception(self, context: ExceptionContext) -> ExceptionContext:
        """
        Handle an exception and potentially modify the context.

        Args:
            context: Exception context with tool, error, and message info

        Returns:
            Modified context (typically with updated error_message)

        Raises:
            ToolException: If the strategy decides to abort (e.g., circuit breaker)
        """
        pass

    def on_success(self, tool_name: str) -> None:
        """
        Called when a tool execution succeeds.

        Allows strategies to reset state (e.g., consecutive error counters).

        Args:
            tool_name: Name of the successful tool
        """
        pass

    def reset(self) -> None:
        """
        Reset strategy state.

        Called when conversation starts/ends to clear per-conversation state.
        """
        pass


class TransformErrorStrategy(ExceptionHandlerStrategy):
    """
    Transform technical errors into human-readable messages.

    Uses LLM to generate user-friendly error explanations with
    actionable guidance.
    """

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        use_llm: bool = True,
        return_detailed_errors: bool = False
    ):
        """
        Initialize transform strategy.

        Args:
            llm: LLM instance for generating human-readable errors
            use_llm: Whether to use LLM for error transformation
            return_detailed_errors: Include stack traces in errors (debug mode)
        """
        self.llm = llm
        self.use_llm = use_llm and llm is not None
        self.return_detailed_errors = return_detailed_errors

        logger.info(
            f"TransformErrorStrategy initialized: use_llm={self.use_llm}, "
            f"detailed={self.return_detailed_errors}"
        )

    def handle_exception(self, context: ExceptionContext) -> ExceptionContext:
        """Generate user-friendly error message."""
        # Try LLM transformation first if enabled
        if self.use_llm:
            try:
                human_error = self._generate_llm_error(context)
                if human_error:
                    context.error_message = f'Possible root cases:\n"""\n{human_error}\n"""\n----------\n\nTool execution error:\n"""\n{context.error_str}"""\n\n*IMPORTANT*: if fixing logic is clear - you can re-try tool execution according to fix.'
                    logger.debug(
                        f"Generated LLM error for '{context.tool_name}': "
                        f"{human_error[:100]}..."
                    )
                    return context
            except Exception as e:
                logger.warning(
                    f"Failed to generate LLM error message: {e}, falling back"
                )

        # Fallback to template-based message
        context.error_message = self._generate_template_error(context)
        return context

    def _generate_llm_error(self, context: ExceptionContext) -> Optional[str]:
        """Use LLM to generate human-readable error."""
        if not self.llm:
            return None

        tool_description = context.tool.description if hasattr(context.tool, 'description') else None
        tool_metadata = context.tool.metadata if hasattr(context.tool, 'metadata') else {}

        system_prompt = """You are a helpful assistant that explains technical errors in simple terms.
Your job is to translate technical error messages into clear, actionable guidance for users.

You have access to:
1. The original error and full traceback
2. Toolkit-specific FAQ documentation
3. The actual tool implementation source code

IMPORTANT:
- Usually the errors are related to 3rd party APIs used by the tools (don't suggest code changes to the tool itself)
- If the error suggests a fix (e.g., missing or invalid parameter), reply with suggested fix
- Avoid suggesting actions that are not related to API configuration (like browser cache clearing, etc) since it is not sessions related
- Analyze the tool source code to understand what it's trying to do and what might have gone wrong
- Check if the FAQ addresses this specific error pattern

Guidelines:
- Be concise and clear
- Explain what went wrong in simple terms based on code analysis
- Suggest concrete next steps or fixes
- Avoid technical jargon unless necessary
- Be empathetic and helpful
- Keep response under 200 words
- Suggest contacting support if issue persists: https://elitea.ai/docs/support/contact-support/
"""

        # Get FAQ for toolkit type from GitHub documentation
        from .faq_fetcher import get_toolkit_faq, get_fallback_faq

        toolkit_type = tool_metadata.get('toolkit_type') if tool_metadata else None
        faq_content = get_toolkit_faq(toolkit_type)

        # Use fallback FAQ if toolkit-specific FAQ unavailable
        if not faq_content:
            faq_content = get_fallback_faq()

        # Extract tool source code with dependencies
        from .tool_code_extractor import extract_tool_code

        tool_code = None
        try:
            tool_code = extract_tool_code(context.tool_name, toolkit_type)
        except Exception as e:
            logger.warning(f"Failed to extract tool code for '{context.tool_name}': {e}")

        # Build user prompt with all available context
        user_prompt_parts = [
            f'A tool called "{context.tool_name}" failed with the following error:',
            "",
            "Error Information:",
            f"Error Type: {context.error_type}",
            f"Error Message: {context.error_str}",
            "",
            "Full Traceback:",
            context.error_traceback,
            "",
            "Tool Arguments:",
            self._format_args(context.args, context.kwargs),
            "",
            "Tool Description:",
            tool_description or "N/A",
            "",
        ]

        # Add toolkit FAQ if available
        if faq_content:
            user_prompt_parts.extend([
                "Toolkit FAQ:",
                faq_content,
                "",
            ])

        # Add tool source code if available
        if tool_code:
            user_prompt_parts.extend([
                "Tool Implementation Code:",
                tool_code,
                "",
            ])

        user_prompt_parts.append("Please analyze the error, tool implementation, and FAQ to explain what went wrong and suggest what the user should do next.")

        user_prompt = "\n".join(user_prompt_parts)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = self.llm.invoke(messages)

        if hasattr(response, 'content'):
            return response.content.strip()

        return None

    def _generate_template_error(self, context: ExceptionContext) -> str:
        """Generate template-based error message."""
        base_msg = f"Tool '{context.tool_name}' failed"

        if self.return_detailed_errors:
            # Debug mode: include full stack trace
            stack_trace = ''.join(
                traceback.format_exception(
                    type(context.error),
                    context.error,
                    context.error.__traceback__
                )
            )
            return (
                f"{base_msg}.\n\n"
                f"Error Type: {context.error_type}\n"
                f"Error Message: {context.error_str}\n\n"
                f"Stack Trace:\n{stack_trace}\n\n"
                f"Arguments: args={context.args}, kwargs={context.kwargs}"
            )
        else:
            # User-friendly mode
            return (
                f"{base_msg}.\n\n"
                f"Error: {context.error_str}\n\n"
                f"Please check the input parameters and try again, "
                f"or use an alternative approach."
            )

    def _format_args(self, args: tuple, kwargs: dict) -> str:
        """Format arguments for LLM prompt."""
        parts = []

        if args:
            args_str = str(args)
            if len(args_str) > 200:
                args_str = args_str[:200] + "..."
            parts.append(f"Positional: {args_str}")

        if kwargs:
            kwargs_str = str(kwargs)
            if len(kwargs_str) > 200:
                kwargs_str = kwargs_str[:200] + "..."
            parts.append(f"Keyword: {kwargs_str}")

        return "\n".join(parts) if parts else "(no arguments)"


class CircuitBreakerStrategy(ExceptionHandlerStrategy):
    """
    Circuit breaker pattern for tool error handling.

    Tracks consecutive failures per tool and raises ToolException
    when threshold is exceeded, effectively disabling the tool.

    Callback Payload (circuit_breaker_opened):
        - tool_name: Name of the tool that exceeded threshold
        - consecutive_failures: Number of consecutive failures
        - error: Original exception message
        - error_type: Exception class name
        - error_message: (optional) Transformed human-readable error if available
    """

    def __init__(
        self,
        threshold: int = 5,
        callbacks: Optional[Dict[str, Callable]] = None
    ):
        """
        Initialize circuit breaker strategy.

        Args:
            threshold: Number of consecutive failures before opening circuit
            callbacks: Optional callbacks for circuit breaker events
        """
        self.threshold = threshold
        self.callbacks = callbacks or {}

        # State tracking per tool
        self.consecutive_errors: Dict[str, int] = {}
        self.circuit_open: Dict[str, bool] = {}

        logger.info(f"CircuitBreakerStrategy initialized: threshold={threshold}")

    def handle_exception(self, context: ExceptionContext) -> ExceptionContext:
        """Track error and check circuit breaker."""
        tool_name = context.tool_name

        # Increment consecutive error count
        self.consecutive_errors[tool_name] = self.consecutive_errors.get(tool_name, 0) + 1
        consecutive = self.consecutive_errors[tool_name]

        logger.warning(
            f"Tool '{tool_name}' failed {consecutive} consecutive times "
            f"(threshold: {self.threshold})"
        )

        # Check if threshold exceeded
        if consecutive >= self.threshold:
            self.circuit_open[tool_name] = True

            logger.error(
                f"Circuit breaker OPENED for tool '{tool_name}' after "
                f"{consecutive} consecutive failures"
            )

            # Fire callback
            if 'circuit_breaker_opened' in self.callbacks:
                try:
                    callback_data = {
                        'tool_name': tool_name,
                        'consecutive_failures': consecutive,
                        'error': context.error_str,
                        'error_type': context.error_type,
                    }

                    # Safely add optional fields
                    if context.error_message:
                        callback_data['error_message'] = context.error_message

                    self.callbacks['circuit_breaker_opened'](callback_data)
                except Exception as e:
                    logger.error(f"Circuit breaker callback failed: {e}")

            # Raise ToolException to disable tool
            raise ToolException(
                f"Tool '{tool_name}' is temporarily disabled due to repeated failures "
                f"({consecutive} consecutive errors). "
                f"Please use an alternative approach or contact support."
            )

        return context

    def on_success(self, tool_name: str) -> None:
        """Reset consecutive error counter on success."""
        if tool_name in self.consecutive_errors:
            prev_errors = self.consecutive_errors[tool_name]
            self.consecutive_errors[tool_name] = 0
            self.circuit_open[tool_name] = False

            if prev_errors > 0:
                logger.info(
                    f"Tool '{tool_name}' recovered after {prev_errors} "
                    f"consecutive errors (circuit closed)"
                )

    def reset(self) -> None:
        """Reset all circuit breaker state."""
        self.consecutive_errors.clear()
        self.circuit_open.clear()
        logger.info("Circuit breaker state reset")


class LoggingStrategy(ExceptionHandlerStrategy):
    """
    Error logging and statistics tracking strategy.

    Tracks total error counts per tool and fires callbacks
    for monitoring and observability.

    Callback Payload (tool_error):
        - tool_name: Name of the tool that failed
        - error: Original exception message
        - error_type: Exception class name
        - total_errors: Total error count for this tool
        - error_message: (optional) Transformed human-readable error from TransformErrorStrategy
        - args: (optional) Tool positional arguments if present
        - kwargs: (optional) Tool keyword arguments if present
        - metadata: (optional) Additional context metadata if present

    Note: For callbacks to receive error_message, LoggingStrategy must run AFTER
    TransformErrorStrategy in the strategy chain.
    """

    def __init__(self, callbacks: Optional[Dict[str, Callable]] = None):
        """
        Initialize logging strategy.

        Args:
            callbacks: Optional callbacks for error events
        """
        self.callbacks = callbacks or {}

        # Total error count per tool (never resets)
        self.error_counts: Dict[str, int] = {}

        logger.info("LoggingStrategy initialized")

    def handle_exception(self, context: ExceptionContext) -> ExceptionContext:
        """Log error and update statistics."""
        tool_name = context.tool_name

        # Update error count
        self.error_counts[tool_name] = self.error_counts.get(tool_name, 0) + 1
        total_errors = self.error_counts[tool_name]

        logger.error(
            f"Tool '{tool_name}' error #{total_errors}: "
            f"{context.error_type}: {context.error_str}"
        )

        # Fire callback with both original and transformed errors
        if 'tool_error' in self.callbacks:
            try:
                callback_data = {
                    'tool_name': tool_name,
                    'error': context.error_str,
                    'error_type': context.error_type,
                    'total_errors': total_errors,
                }

                # Safely add optional fields
                if context.error_message:
                    callback_data['error_message'] = context.error_message

                if context.args:
                    callback_data['args'] = context.args

                if context.kwargs:
                    callback_data['kwargs'] = context.kwargs

                if context.metadata:
                    callback_data['metadata'] = context.metadata

                self.callbacks['tool_error'](callback_data)
            except Exception as e:
                logger.error(f"Logging callback failed: {e}")

        return context

    def get_error_summary(self) -> Dict[str, int]:
        """Get error count summary."""
        return dict(self.error_counts)

    def reset(self) -> None:
        """Reset error counts."""
        self.error_counts.clear()
        logger.info("Logging strategy state reset")


class CompositeStrategy(ExceptionHandlerStrategy):
    """
    Composite strategy that chains multiple strategies sequentially.

    Executes strategies in order, passing the modified context from
    one strategy to the next.
    """

    def __init__(self, strategies: List[ExceptionHandlerStrategy]):
        """
        Initialize composite strategy.

        Args:
            strategies: List of strategies to execute in sequence
        """
        self.strategies = strategies
        logger.info(f"CompositeStrategy initialized with {len(strategies)} strategies")

    def handle_exception(self, context: ExceptionContext) -> ExceptionContext:
        """Execute all strategies in sequence."""
        for i, strategy in enumerate(self.strategies):
            try:
                context = strategy.handle_exception(context)
                logger.debug(
                    f"Strategy {i+1}/{len(self.strategies)} "
                    f"({strategy.__class__.__name__}) completed"
                )
            except ToolException:
                # Strategy decided to abort (e.g., circuit breaker)
                logger.warning(
                    f"Strategy {i+1}/{len(self.strategies)} "
                    f"({strategy.__class__.__name__}) raised ToolException"
                )
                raise

        return context

    def on_success(self, tool_name: str) -> None:
        """Notify all strategies of success."""
        for strategy in self.strategies:
            try:
                strategy.on_success(tool_name)
            except Exception as e:
                logger.error(
                    f"Strategy {strategy.__class__.__name__} on_success failed: {e}"
                )

    def reset(self) -> None:
        """Reset all strategies."""
        for strategy in self.strategies:
            try:
                strategy.reset()
            except Exception as e:
                logger.error(
                    f"Strategy {strategy.__class__.__name__} reset failed: {e}"
                )

