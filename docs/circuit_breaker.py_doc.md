# circuit_breaker.py

**Path:** `src/alita_sdk/community/eda/utils/circuit_breaker.py`

## Data Flow

The data flow within the `circuit_breaker.py` file revolves around the state management of the circuit breaker and the execution of the wrapped function. The data originates from the function call that is being wrapped by the `CircuitBreaker` class. The state of the circuit breaker (CLOSED, OPEN, HALF-OPEN) determines the flow of execution. When the circuit is CLOSED, the function executes normally. If the function fails, the failure count increments. Once the failure count exceeds the maximum allowed failures, the circuit state changes to OPEN, and subsequent calls raise a `CircuitOpenException`. If the circuit is in the HALF-OPEN state, a trial execution of the function occurs. If successful, the circuit closes; otherwise, it reopens. The data elements include the function arguments, the state of the circuit breaker, and the timestamps of the last attempts. Temporary storage is evident in the form of instance variables like `failures`, `state`, and `last_attempt`.

Example:
```python
if self.state == 'CLOSED':
    try:
        result = func(*args, **kwargs)
        return result
    except Exception as e:
        self.failures += 1
        if self.failures >= self.max_failures:
            self.state = 'OPEN'
            self.last_attempt = current_time
        raise e
```
This snippet shows the data flow when the circuit is CLOSED. The function executes, and if an exception occurs, the failure count increments. If the failures exceed the maximum allowed, the circuit state changes to OPEN.

## Functions Descriptions

### CircuitBreaker.__init__

The `__init__` method initializes the `CircuitBreaker` instance with default or provided values for `max_failures` and `reset_timeout`. It sets the initial state to CLOSED, failure count to zero, and records the current time as the last attempt timestamp.

### CircuitBreaker.__call__

The `__call__` method allows the `CircuitBreaker` instance to be used as a decorator. It wraps the target function and manages the circuit state based on the function's execution results. It handles the transitions between CLOSED, OPEN, and HALF-OPEN states and raises a `CircuitOpenException` if the circuit is OPEN.

Example:
```python
@functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        current_time = time.time()
        if self.state == 'OPEN' and (current_time - self.last_attempt) > self.reset_timeout:
            self.state = 'HALF-OPEN'

        if self.state == 'HALF-OPEN':
            try:
                result = func(*args, **kwargs)
                self.state = 'CLOSED'
                self.failures = 0
                return result
            except Exception as e:
                self.state = 'OPEN'
                self.last_attempt = current_time
                raise e

        elif self.state == 'CLOSED':
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                self.failures += 1
                if self.failures >= self.max_failures:
                    self.state = 'OPEN'
                    self.last_attempt = current_time
                raise e

        # OPEN state
        raise CircuitOpenException()
```
This example shows the wrapped function managing the circuit state transitions and handling exceptions.

## Dependencies Used and Their Descriptions

The `circuit_breaker.py` file imports the following dependencies:

- `time`: This module provides various time-related functions. It is used to get the current time for managing the circuit breaker's state transitions.
- `functools`: This module provides higher-order functions that act on or return other functions. It is used to preserve the metadata of the wrapped function using the `wraps` decorator.

Example:
```python
import time
import functools
```
These imports are essential for the circuit breaker to function correctly, as they provide the necessary tools for time management and function wrapping.

## Functional Flow

The functional flow of the `circuit_breaker.py` file starts with the initialization of the `CircuitBreaker` class. The class is then used as a decorator to wrap a target function. When the wrapped function is called, the circuit breaker checks its state and decides whether to execute the function or raise an exception. The state transitions between CLOSED, OPEN, and HALF-OPEN based on the function's success or failure and the elapsed time since the last attempt.

Example:
```python
breaker = CircuitBreaker(max_failures=3, reset_timeout=10)

@breaker
def my_function():
    # Function logic here
    pass
```
This example shows how to initialize the `CircuitBreaker` and use it to wrap a function.

## Endpoints Used/Created

The `circuit_breaker.py` file does not explicitly define or call any endpoints. It is a utility module that provides the circuit breaker functionality to be used within other parts of the application.