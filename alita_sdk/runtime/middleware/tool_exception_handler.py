"""
Tool Exception Handler Middleware

Provides intelligent error handling for tool execution using pluggable strategies:
- Transform errors into human-readable messages (LLM-powered)
- Circuit breaker pattern for repeatedly failing tools
- Error tracking and monitoring
- Composable strategy pipeline

Example:
    from alita_sdk.runtime.middleware import (
        ToolExceptionHandlerMiddleware,
        TransformErrorStrategy,
        CircuitBreakerStrategy,
        LoggingStrategy
    )

    # Using factory method (recommended)
    middleware = ToolExceptionHandlerMiddleware.create_default(
        llm=my_llm,
        threshold=3
    )

    # Or explicit strategies
    middleware = ToolExceptionHandlerMiddleware(
        strategies=[
            LoggingStrategy(),
            CircuitBreakerStrategy(threshold=3),
            TransformErrorStrategy(llm=my_llm, use_llm=True)
        ]
    )
"""

import logging
from functools import wraps
from typing import List, Optional, Dict, Any, Callable

from alita_sdk.runtime.utils.mcp_oauth import McpAuthorizationRequired
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_core.language_models import BaseChatModel

from .base import Middleware
from .strategies import (
    ExceptionHandlerStrategy,
    ExceptionContext,
    TransformErrorStrategy,
    CircuitBreakerStrategy,
    LoggingStrategy
)
from ..tools.application import Application

logger = logging.getLogger(__name__)


class ToolExceptionHandlerMiddleware(Middleware):
    """
    Wraps agent tools with intelligent exception handling using pluggable strategies.

    Uses a strategy pattern to allow flexible error handling configurations.
    Each strategy processes exceptions in sequence, allowing composition of
    behaviors like logging, circuit breaking, and error transformation.

    Example:
        ```python
        # Using factory method (recommended)
        middleware = ToolExceptionHandlerMiddleware.create_default(
            llm=my_llm,
            threshold=3
        )

        # Or explicit strategies
        middleware = ToolExceptionHandlerMiddleware(
            strategies=[
                LoggingStrategy(),
                CircuitBreakerStrategy(threshold=3),
                TransformErrorStrategy(llm=my_llm, use_llm=True)
            ]
        )

        assistant = client.application(
            application_id='app_123',
            middleware=[middleware]
        )
        ```
    """

    def __init__(
        self,
        strategies: List[ExceptionHandlerStrategy],
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        excluded_tools: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize Tool Exception Handler Middleware.

        Args:
            strategies: List of exception handler strategies to apply (in sequence)
            conversation_id: Conversation ID for state tracking
            callbacks: Optional dict of callback functions for events
            excluded_tools: List of tool names to not wrap with error handling
        """
        super().__init__(conversation_id, callbacks, **kwargs)

        if not strategies:
            raise ValueError(
                "At least one strategy is required. "
                "Use ToolExceptionHandlerMiddleware.create_default() for default configuration."
            )

        self.strategies = strategies
        self.excluded_tools = set(excluded_tools or [])

        # Wrapped tools cache to avoid double-wrapping (keyed by object id)
        self._wrapped_tools_cache: Dict[int, BaseTool] = {}

        logger.info(
            f"ToolExceptionHandlerMiddleware initialized with {len(strategies)} strategies: "
            f"{[s.__class__.__name__ for s in strategies]}"
        )

    @classmethod
    def create_default(
        cls,
        llm: Optional[BaseChatModel] = None,
        threshold: int = 5,
        use_llm: bool = True,
        return_detailed_errors: bool = False,
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        excluded_tools: Optional[List[str]] = None,
        **kwargs
    ) -> "ToolExceptionHandlerMiddleware":
        """
        Create middleware with default strategy configuration.

        This factory method provides a convenient way to create middleware
        with standard logging, circuit breaker, and error transformation strategies.

        Strategy execution order:
        1. TransformErrorStrategy - Generates human-readable error messages (runs first)
        2. CircuitBreakerStrategy - Checks failure threshold
        3. LoggingStrategy - Logs both original and transformed errors (runs last)

        Args:
            llm: LLM instance for generating human-readable error messages
            threshold: Number of consecutive failures before opening circuit breaker
            use_llm: Whether to use LLM for error transformation
            return_detailed_errors: Include stack traces in error messages (debug mode)
            conversation_id: Conversation ID for state tracking
            callbacks: Optional dict of callback functions for events
            excluded_tools: List of tool names to not wrap with error handling
            **kwargs: Additional arguments passed to middleware

        Returns:
            Configured ToolExceptionHandlerMiddleware instance
        """
        strategies = [
            TransformErrorStrategy(
                llm=llm,
                use_llm=use_llm,
                return_detailed_errors=return_detailed_errors
            ),
            CircuitBreakerStrategy(threshold=threshold, callbacks=callbacks),
            LoggingStrategy(callbacks=callbacks),
        ]

        return cls(
            strategies=strategies,
            conversation_id=conversation_id,
            callbacks=callbacks,
            excluded_tools=excluded_tools,
            **kwargs
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
        # Don't wrap Application tools - they have their own invocation logic
        # and wrapping causes state variables to be lost due to args_schema filtering
        if isinstance(tool, Application):
            logger.debug(f"Tool '{tool.name}' is an Application, skipping error handling wrapper")
            return tool

        # Don't wrap if tool is in exclusion list
        if tool.name in self.excluded_tools:
            logger.debug(f"Tool '{tool.name}' is excluded from error handling")
            return tool

        # Check if already wrapped (avoid double-wrapping)
        # Use object identity (id) as cache key, not tool.name, because different toolkits
        # can have tools with the same name (e.g., index_data in both GitHub and Confluence).
        # Name-based caching would return the same wrapped object for both, breaking
        # the dedup logic in Assistant.__init__ which relies on distinct objects.
        cache_key = id(tool)
        if cache_key in self._wrapped_tools_cache:
            logger.debug(f"Tool '{tool.name}' already wrapped, returning cached version")
            return self._wrapped_tools_cache[cache_key]

        # Get the original function to wrap
        original_func = self._get_tool_function(tool)

        # Create wrapped function
        @wraps(original_func)
        def error_handled_func(*args, **kwargs) -> str:
            """Wrapped function with error handling."""
            try:
                # Execute original tool
                result = original_func(*args, **kwargs)

                # Check if result is a ToolException object (not raised, but returned)
                if isinstance(result, ToolException):
                    logger.warning(
                        f"Tool '{tool.name}' returned ToolException object instead of raising it, raising now"
                    )
                    raise result

                # Success - notify all strategies
                for strategy in self.strategies:
                    try:
                        strategy.on_success(tool.name)
                    except Exception as e:
                        logger.error(
                            f"Strategy {strategy.__class__.__name__} on_success failed: {e}"
                        )

                return result

            except McpAuthorizationRequired:
                # MCP authorization required - re-raise to be handled by agent
                # This is a cross-cutting auth concern, not delegated to strategies
                raise

            except Exception as e:
                # Create exception context
                context = ExceptionContext(
                    tool=tool,
                    error=e,
                    args=args,
                    kwargs=kwargs
                )

                # Execute strategies in sequence
                try:
                    for strategy in self.strategies:
                        context = strategy.handle_exception(context)
                except ToolException:
                    # Strategy raised ToolException (e.g., circuit breaker)
                    # Re-raise as-is
                    raise

                # Return formatted error message from context
                return context.error_message or str(e)

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

            # Preserve a reference to the original tool so that downstream code
            # (e.g., swarm agent detection) can inspect the unwrapped type and
            # attributes like Application.client, Application.args_runnable, etc.
            wrapped_tool._original_tool = tool

            # Cache the wrapped tool by object identity
            self._wrapped_tools_cache[cache_key] = wrapped_tool

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

    def on_conversation_start(self, conversation_id: str) -> Optional[str]:
        """Reset strategy state on conversation start."""
        super().on_conversation_start(conversation_id)

        # Reset all strategies
        for strategy in self.strategies:
            try:
                strategy.reset()
            except Exception as e:
                logger.error(
                    f"Strategy {strategy.__class__.__name__} reset failed: {e}",
                    exc_info=True
                )

        # Clear wrapped tools cache
        self._wrapped_tools_cache.clear()

        logger.info(
            f"Reset error handling state for conversation {conversation_id}, "
            f"cleared {len(self.strategies)} strategies"
        )
        return None

    def on_conversation_end(self, conversation_id: str) -> None:
        """Log error statistics on conversation end."""
        super().on_conversation_end(conversation_id)

        # Try to get error summary from LoggingStrategy if present
        for strategy in self.strategies:
            if isinstance(strategy, LoggingStrategy):
                error_summary = strategy.get_error_summary()
                if error_summary:
                    logger.info(
                        f"Tool error summary for conversation {conversation_id}: "
                        f"{error_summary}"
                    )

                    # Fire summary callback
                    self._fire_callback('conversation_error_summary', {
                        'conversation_id': conversation_id,
                        'error_counts': error_summary,
                    })
                break

