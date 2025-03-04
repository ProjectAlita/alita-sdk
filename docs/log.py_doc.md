# log.py

**Path:** `src/alita_sdk/langchain/tools/log.py`

## Data Flow

The data flow within `log.py` revolves around logging messages at various levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) and initializing the logging configuration. The data originates from the logging messages passed to the logging functions (`debug`, `info`, `warning`, `error`, `critical`, `log`, `exception`). These messages are then processed by the `get_outer_logger` function, which retrieves the appropriate logger based on the caller's context. The logger then handles the message according to its level and configuration.

For example, the `debug` function logs a message with the DEBUG level:

```python

def debug(msg, *args, **kwargs):
    """ Logs a message with level DEBUG """
    return get_outer_logger().debug(msg, *args, **kwargs)
```

In this snippet, the `msg` parameter represents the message to be logged. The `get_outer_logger` function retrieves the logger for the caller's context, and the `debug` method of the logger is called with the message and any additional arguments or keyword arguments.

## Functions Descriptions

1. **init(level=logging.INFO):**
   Initializes the logging configuration with the specified logging level. The default level is INFO. This function sets the logging level for the root logger.

   ```python
   def init(level=logging.INFO):
       """ Initialize logging """
       logging.getLogger().setLevel(level)
   ```

2. **get_logger():**
   Retrieves the logger for the caller's context. This function uses the `inspect` module to get the name of the module from which it was called and returns the corresponding logger.

   ```python
   def get_logger():
       """ Get logger for caller context """
       return logging.getLogger(
           inspect.currentframe().f_back.f_globals["__name__"]
       )
   ```

3. **get_outer_logger():**
   Similar to `get_logger`, but retrieves the logger for the caller's caller context. This is useful for logging within the logging module itself.

   ```python
   def get_outer_logger():
       """ Get logger for callers context (for use in this module) """
       return logging.getLogger(
           inspect.currentframe().f_back.f_back.f_globals["__name__"]
       )
   ```

4. **debug(msg, *args, **kwargs):**
   Logs a message with the DEBUG level. This function calls `get_outer_logger` to retrieve the appropriate logger and then logs the message using the logger's `debug` method.

   ```python
   def debug(msg, *args, **kwargs):
       """ Logs a message with level DEBUG """
       return get_outer_logger().debug(msg, *args, **kwargs)
   ```

5. **info(msg, *args, **kwargs):**
   Logs a message with the INFO level. Similar to the `debug` function, but uses the `info` method of the logger.

   ```python
   def info(msg, *args, **kwargs):
       """ Logs a message with level INFO """
       return get_outer_logger().info(msg, *args, **kwargs)
   ```

6. **warning(msg, *args, **kwargs):**
   Logs a message with the WARNING level. Similar to the `debug` function, but uses the `warning` method of the logger.

   ```python
   def warning(msg, *args, **kwargs):
       """ Logs a message with level WARNING """
       return get_outer_logger().warning(msg, *args, **kwargs)
   ```

7. **error(msg, *args, **kwargs):**
   Logs a message with the ERROR level. Similar to the `debug` function, but uses the `error` method of the logger.

   ```python
   def error(msg, *args, **kwargs):
       """ Logs a message with level ERROR """
       return get_outer_logger().error(msg, *args, **kwargs)
   ```

8. **critical(msg, *args, **kwargs):**
   Logs a message with the CRITICAL level. Similar to the `debug` function, but uses the `critical` method of the logger.

   ```python
   def critical(msg, *args, **kwargs):
       """ Logs a message with level CRITICAL """
       return get_outer_logger().critical(msg, *args, **kwargs)
   ```

9. **log(lvl, msg, *args, **kwargs):**
   Logs a message with the specified logging level. This function calls `get_outer_logger` to retrieve the appropriate logger and then logs the message using the logger's `log` method with the specified level.

   ```python
   def log(lvl, msg, *args, **kwargs):
       """ Logs a message with integer level lvl """
       return get_outer_logger().log(lvl, msg, *args, **kwargs)
   ```

10. **exception(msg, *args, **kwargs):**
    Logs a message with the ERROR level inside an exception handler. This function calls `get_outer_logger` to retrieve the appropriate logger and then logs the message using the logger's `exception` method.

    ```python
    def exception(msg, *args, **kwargs):
        """ Logs a message with level ERROR inside exception handler """
        return get_outer_logger().exception(msg, *args, **kwargs)
    ```

11. **DebugLogStream:**
    A class that represents an IO stream that writes to `log.debug`. This class inherits from `io.RawIOBase` and overrides the `write` method to log each line of the input data at the DEBUG level.

    ```python
    class DebugLogStream(io.RawIOBase):
        """ IO stream that writes to log.debug """

        def read(self, size=-1):  # pylint: disable=W0613
            return None

        def readall(self):
            return None

        def readinto(self, b):  # pylint: disable=W0613
            return None

        def write(self, b):
            for line in b.decode().splitlines():
                get_outer_logger().debug(line)
    ```

12. **print_log(*args):**
    Emulates the `print` function by sending the output to both `log.info` and the standard `print` function. This function attempts to log the message at the INFO level and falls back to printing if logging fails.

    ```python
    def print_log(*args):
        """ Emulate print: send to log.info and print() at the same time """
        print(*args)
        try:
            info("%s", " ".join([str(i) for i in args]))
        except:  # pylint: disable=W0702
            pass
    ```

## Dependencies Used and Their Descriptions

1. **io:**
   The `io` module is used to handle the `DebugLogStream` class, which provides an IO stream that writes to `log.debug`. This module is part of the Python standard library and provides the base classes and functions for working with streams.

2. **logging:**
   The `logging` module is the core dependency for this file. It is used to configure and manage logging throughout the module. The `logging` module is part of the Python standard library and provides a flexible framework for emitting log messages from Python programs.

3. **inspect:**
   The `inspect` module is used to retrieve information about the caller's context, specifically to get the name of the module from which a function was called. This module is part of the Python standard library and provides several useful functions to help get information about live objects such as modules, classes, methods, functions, tracebacks, frame objects, and code objects.

## Functional Flow

The functional flow of `log.py` begins with the initialization of the logging configuration using the `init` function. This sets the logging level for the root logger. The module then provides several functions for logging messages at different levels (`debug`, `info`, `warning`, `error`, `critical`, `log`, `exception`). Each of these functions retrieves the appropriate logger using `get_outer_logger` and logs the message with the specified level.

For example, the `info` function logs a message with the INFO level:

```python

def info(msg, *args, **kwargs):
    """ Logs a message with level INFO """
    return get_outer_logger().info(msg, *args, **kwargs)
```

In this snippet, the `msg` parameter represents the message to be logged. The `get_outer_logger` function retrieves the logger for the caller's context, and the `info` method of the logger is called with the message and any additional arguments or keyword arguments.

The module also includes the `DebugLogStream` class, which provides an IO stream that writes to `log.debug`, and the `print_log` function, which emulates the `print` function by sending the output to both `log.info` and the standard `print` function.

## Endpoints Used/Created

This module does not explicitly define or call any endpoints. Its primary purpose is to provide logging functionality within the application.