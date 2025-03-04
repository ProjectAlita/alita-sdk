# log.py

**Path:** `src/alita_sdk/langchain/tools/log.py`

## Data Flow

The data flow within `log.py` revolves around logging messages at various levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) and initializing the logging configuration. The data originates from the logging messages passed to the logging functions (`debug`, `info`, `warning`, `error`, `critical`, `log`, `exception`). These messages are then processed by the `get_outer_logger` function, which retrieves the appropriate logger based on the caller's context. The messages are finally logged using the logger's methods.

Example:
```python
# Example of logging an info message
info("This is an info message")
```
In this example, the `info` function is called with a message. The `get_outer_logger` function retrieves the logger, and the message is logged at the INFO level.

## Functions Descriptions

1. **init(level=logging.INFO):**
   - Initializes the logging configuration with the specified level.
   - **Parameters:**
     - `level`: The logging level to set (default is `logging.INFO`).
   - **Example:**
   ```python
   init(logging.DEBUG)
   ```
   This sets the logging level to DEBUG.

2. **get_logger():**
   - Retrieves the logger for the caller's context.
   - **Returns:** The logger instance.
   - **Example:**
   ```python
   logger = get_logger()
   ```
   This retrieves the logger for the current context.

3. **get_outer_logger():**
   - Retrieves the logger for the caller's caller context.
   - **Returns:** The logger instance.
   - **Example:**
   ```python
   logger = get_outer_logger()
   ```
   This retrieves the logger for the caller's caller context.

4. **debug(msg, *args, **kwargs):**
   - Logs a message with level DEBUG.
   - **Parameters:**
     - `msg`: The message to log.
     - `*args`, `**kwargs`: Additional arguments for the logger.
   - **Example:**
   ```python
debug("This is a debug message")
   ```
   This logs a debug message.

5. **info(msg, *args, **kwargs):**
   - Logs a message with level INFO.
   - **Parameters:**
     - `msg`: The message to log.
     - `*args`, `**kwargs`: Additional arguments for the logger.
   - **Example:**
   ```python
info("This is an info message")
   ```
   This logs an info message.

6. **warning(msg, *args, **kwargs):**
   - Logs a message with level WARNING.
   - **Parameters:**
     - `msg`: The message to log.
     - `*args`, `**kwargs`: Additional arguments for the logger.
   - **Example:**
   ```python
warning("This is a warning message")
   ```
   This logs a warning message.

7. **error(msg, *args, **kwargs):**
   - Logs a message with level ERROR.
   - **Parameters:**
     - `msg`: The message to log.
     - `*args`, `**kwargs`: Additional arguments for the logger.
   - **Example:**
   ```python
error("This is an error message")
   ```
   This logs an error message.

8. **critical(msg, *args, **kwargs):**
   - Logs a message with level CRITICAL.
   - **Parameters:**
     - `msg`: The message to log.
     - `*args`, `**kwargs`: Additional arguments for the logger.
   - **Example:**
   ```python
critical("This is a critical message")
   ```
   This logs a critical message.

9. **log(lvl, msg, *args, **kwargs):**
   - Logs a message with the specified level.
   - **Parameters:**
     - `lvl`: The logging level.
     - `msg`: The message to log.
     - `*args`, `**kwargs`: Additional arguments for the logger.
   - **Example:**
   ```python
log(logging.DEBUG, "This is a debug message")
   ```
   This logs a message with the DEBUG level.

10. **exception(msg, *args, **kwargs):**
    - Logs a message with level ERROR inside an exception handler.
    - **Parameters:**
      - `msg`: The message to log.
      - `*args`, `**kwargs`: Additional arguments for the logger.
    - **Example:**
    ```python
try:
    1 / 0
except ZeroDivisionError:
    exception("An exception occurred")
    ```
    This logs an error message inside an exception handler.

11. **DebugLogStream:**
    - A class representing an IO stream that writes to `log.debug`.
    - **Methods:**
      - `read(size=-1)`: Returns `None`.
      - `readall()`: Returns `None`.
      - `readinto(b)`: Returns `None`.
      - `write(b)`: Writes the decoded bytes to `log.debug`.
    - **Example:**
    ```python
stream = DebugLogStream()
stream.write(b"Debug message")
    ```
    This writes a debug message to the log.

12. **print_log(*args):**
    - Emulates the `print` function by sending the message to `log.info` and `print` simultaneously.
    - **Parameters:**
      - `*args`: The messages to log and print.
    - **Example:**
    ```python
print_log("This is a log message")
    ```
    This logs and prints a message.

## Dependencies Used and Their Descriptions

1. **io:**
   - Provides the base classes for working with streams.
   - Used in the `DebugLogStream` class to create a custom IO stream that writes to the log.

2. **logging:**
   - Provides a flexible framework for emitting log messages from Python programs.
   - Used throughout the file to log messages at various levels and to configure the logging system.

3. **inspect:**
   - Provides several useful functions to help get information about live objects such as modules, classes, methods, functions, tracebacks, frame objects, and code objects.
   - Used in the `get_logger` and `get_outer_logger` functions to retrieve the logger for the caller's context.

## Functional Flow

1. The `init` function is called to initialize the logging configuration with the specified level.
2. The `get_logger` and `get_outer_logger` functions are used to retrieve the appropriate logger based on the caller's context.
3. The logging functions (`debug`, `info`, `warning`, `error`, `critical`, `log`, `exception`) are called to log messages at various levels.
4. The `DebugLogStream` class is used to create a custom IO stream that writes to the log.
5. The `print_log` function is used to log and print messages simultaneously.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It focuses on providing logging functionality within the application.