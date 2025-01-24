# log.py

**Path:** `src/alita_sdk/langchain/tools/log.py`

## Data Flow

The data flow within the `log.py` file is centered around logging messages at various levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) and initializing the logging configuration. The data originates from the log messages passed to the logging functions (`debug`, `info`, `warning`, `error`, `critical`, `log`, `exception`). These messages are then processed by the `get_outer_logger` function, which retrieves the appropriate logger based on the caller's context. The log messages are then output to the configured logging handlers. Additionally, the `DebugLogStream` class provides a custom IO stream that writes to the `log.debug` method. The `print_log` function emulates the `print` function by sending messages to both `log.info` and the standard output.

Example:
```python
import logging

def init(level=logging.INFO):
    """ Initialize logging """
    logging.getLogger().setLevel(level)

init()
logging.info("This is an info message")
```
In this example, the `init` function sets the logging level to INFO, and the `logging.info` function logs an info message.

## Functions Descriptions

1. `init(level=logging.INFO)`: Initializes the logging configuration with the specified logging level. It sets the logging level for the root logger.

2. `get_logger()`: Retrieves the logger for the caller's context using the `inspect` module to get the caller's module name.

3. `get_outer_logger()`: Similar to `get_logger`, but retrieves the logger for the caller's caller context.

4. `debug(msg, *args, **kwargs)`: Logs a message with the DEBUG level using the `get_outer_logger` function.

5. `info(msg, *args, **kwargs)`: Logs a message with the INFO level using the `get_outer_logger` function.

6. `warning(msg, *args, **kwargs)`: Logs a message with the WARNING level using the `get_outer_logger` function.

7. `error(msg, *args, **kwargs)`: Logs a message with the ERROR level using the `get_outer_logger` function.

8. `critical(msg, *args, **kwargs)`: Logs a message with the CRITICAL level using the `get_outer_logger` function.

9. `log(lvl, msg, *args, **kwargs)`: Logs a message with the specified logging level using the `get_outer_logger` function.

10. `exception(msg, *args, **kwargs)`: Logs a message with the ERROR level inside an exception handler using the `get_outer_logger` function.

11. `DebugLogStream`: A custom IO stream class that writes to `log.debug`.

12. `print_log(*args)`: Emulates the `print` function by sending messages to both `log.info` and the standard output.

## Dependencies Used and Their Descriptions

1. `io`: Provides the `RawIOBase` class used for creating the `DebugLogStream` class.

2. `logging`: The core logging module used for configuring and writing log messages.

3. `inspect`: Used to retrieve the caller's context for logging purposes.

## Functional Flow

1. The `init` function is called to set the logging level.

2. Logging functions (`debug`, `info`, `warning`, `error`, `critical`, `log`, `exception`) are called with log messages.

3. Each logging function calls `get_outer_logger` to retrieve the appropriate logger based on the caller's context.

4. The log message is processed and output to the configured logging handlers.

5. The `DebugLogStream` class provides a custom IO stream that writes to `log.debug`.

6. The `print_log` function emulates the `print` function by sending messages to both `log.info` and the standard output.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints.