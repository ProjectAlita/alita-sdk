# log.py

**Path:** `src/alita_sdk/langchain/tools/log.py`

## Data Flow

The data flow within `log.py` revolves around logging messages at various levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) and initializing the logging configuration. The data originates from the function calls that generate log messages. These messages are then processed by the logging functions, which determine the appropriate logging level and format. The final destination of the data is the logging output, which could be a console, file, or any other logging handler configured in the logging setup. Intermediate variables such as `msg`, `args`, and `kwargs` are used to temporarily store the log message and its associated arguments before they are passed to the logging functions.

Example:
```python
import logging

def init(level=logging.INFO):
    """ Initialize logging """
    logging.getLogger().setLevel(level)

init()
```
In this example, the `init` function sets the logging level to INFO, affecting how subsequent log messages are processed and displayed.

## Functions Descriptions

1. **init(level=logging.INFO)**: Initializes the logging configuration with the specified logging level. It sets the logging level for the root logger.

2. **get_logger()**: Retrieves a logger for the caller's context using the caller's module name. It uses the `inspect` module to find the caller's frame and obtain the module name.

3. **get_outer_logger()**: Similar to `get_logger()`, but retrieves the logger for the caller's caller context. This is useful for logging within the logging module itself.

4. **debug(msg, *args, **kwargs)**: Logs a message with the DEBUG level. It uses `get_outer_logger()` to get the appropriate logger and then logs the message.

5. **info(msg, *args, **kwargs)**: Logs a message with the INFO level. It uses `get_outer_logger()` to get the appropriate logger and then logs the message.

6. **warning(msg, *args, **kwargs)**: Logs a message with the WARNING level. It uses `get_outer_logger()` to get the appropriate logger and then logs the message.

7. **error(msg, *args, **kwargs)**: Logs a message with the ERROR level. It uses `get_outer_logger()` to get the appropriate logger and then logs the message.

8. **critical(msg, *args, **kwargs)**: Logs a message with the CRITICAL level. It uses `get_outer_logger()` to get the appropriate logger and then logs the message.

9. **log(lvl, msg, *args, **kwargs)**: Logs a message with a specified integer level. It uses `get_outer_logger()` to get the appropriate logger and then logs the message.

10. **exception(msg, *args, **kwargs)**: Logs a message with the ERROR level within an exception handler. It uses `get_outer_logger()` to get the appropriate logger and then logs the message.

11. **DebugLogStream**: A class that extends `io.RawIOBase` to create an IO stream that writes to the DEBUG log level. It overrides the `read`, `readall`, `readinto`, and `write` methods to handle logging.

12. **print_log(*args)**: Emulates the `print` function by sending the message to both `log.info` and the standard `print` function. It tries to log the message using the `info` function and falls back to `print` if logging fails.

## Dependencies Used and Their Descriptions

1. **io**: Used for creating the `DebugLogStream` class, which provides an IO stream interface for logging.

2. **logging**: The core Python logging module used for all logging operations, including setting logging levels, retrieving loggers, and logging messages at various levels.

3. **inspect**: Used to retrieve the caller's context for logging purposes. It helps in dynamically obtaining the module name of the caller to create context-specific loggers.

## Functional Flow

The functional flow of `log.py` starts with the initialization of the logging configuration using the `init` function. Once initialized, various logging functions (`debug`, `info`, `warning`, `error`, `critical`, `log`, `exception`) can be called to log messages at different levels. These functions use `get_outer_logger()` to retrieve the appropriate logger based on the caller's context. The `DebugLogStream` class provides an IO stream interface for logging, and the `print_log` function emulates the `print` function by logging messages at the INFO level.

Example:
```python
def example_function():
    logger = get_logger()
    logger.info("This is an info message")
    logger.error("This is an error message")

example_function()
```
In this example, `example_function` retrieves a logger using `get_logger()` and logs an INFO and an ERROR message.

## Endpoints Used/Created

There are no explicit endpoints used or created in `log.py`. The file focuses on providing logging functionality within the application.