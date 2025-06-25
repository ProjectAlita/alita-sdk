import logging
from functools import wraps

try:
    from langchain_core.callbacks import dispatch_custom_event
except ImportError:
    # Fallback stub if langchain_core is unavailable
    def dispatch_custom_event(name: str, data: dict):  # pragma: no cover
        pass


class StreamlitCallbackHandler(logging.Handler):
    """Custom logging handler to send logs to Streamlit."""

    def __init__(self, tool_name: str = "logging"):
        super().__init__()
        self.tool_name = tool_name

    def emit(self, record):
        """Emit a log record."""
        if record.levelno < logging.INFO:
            return  # Ignore debug logs

        log_entry = self.format(record)
        dispatch_custom_event(
            name="thinking_step",
            data={
                "message": log_entry,
                "tool_name": self.tool_name,
                "toolkit": "logging",  # ? or pass the toolkit name
            },
        )


def setup_streamlit_logging(
    logger_name: str = "", tool_name="logging"
) -> StreamlitCallbackHandler:
    """
    Attach a StreamlitCallbackHandler to the given logger (default: root).
    Returns the handler so you can remove it later if needed.
    """
    logger = logging.getLogger(logger_name)
    handler = StreamlitCallbackHandler(tool_name)

    # Avoid duplicate handlers
    if not any(isinstance(h, StreamlitCallbackHandler) for h in logger.handlers):
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return handler


# Decorator version
def with_streamlit_logs(logger_name: str = "", tool_name="logging"):
    """
    Decorator to temporarily attach a StreamlitCallbackHandler to a function's logger.

    Args:
        logger_name (str): Name of the logger to attach the handler to.
            Use an empty string "" for the root logger.
        tool_name (str): Name of the tool to display in Streamlit logs.

    Behavior:
        - Attaches a StreamlitCallbackHandler before the function runs.
        - Forwards all INFO and higher log messages—including those
            from 3rd-party libraries using the specified logger—to Streamlit 
            via dispatch_custom_event.
        - Automatically removes the handler after the function completes, 
            even if an exception occurs.

    Example:
        @with_streamlit_logs(logger_name="my_logger", tool_name="my_tool")
        def my_function():
            logging.info("This is a log message.")
            # Logs from 3rd-party libraries using "my_logger" will also be sent to Streamlit.

    Returns:
        The decorated function with Streamlit logging enabled during its execution.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name)
            handler = StreamlitCallbackHandler(tool_name=tool_name)
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(handler)
            try:
                return func(*args, **kwargs)
            finally:
                logger.removeHandler(handler)

        return wrapper

    return decorator
