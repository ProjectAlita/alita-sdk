# circuit_breaker.py

**Path:** `src/alita_sdk/community/eda/utils/circuit_breaker.py`

## Data Flow

The data flow within the `circuit_breaker.py` file revolves around the state management of the circuit breaker pattern. The primary data elements include the state of the circuit breaker (`OPEN`, `HALF-OPEN`, `CLOSED`), the number of failures, and the timestamp of the last attempt to call the function. The data originates from the initialization of the `CircuitBreaker` class and is manipulated through the `__call__` method, which wraps the target function. The state transitions are based on the number of failures and the elapsed time since the last attempt. The data is temporarily stored in the attributes of the `CircuitBreaker` class and is used to determine whether to allow the function call or raise a `CircuitOpenException`.

Example:
```python
class CircuitBreaker:
    def __init__(self, max_failures=3, reset_timeout=10):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = 'CLOSED'
        self.last_attempt = time.time()
```
*Initialization of the CircuitBreaker class with default values for max_failures and reset_timeout.*

## Functions Descriptions

### CircuitBreaker.__init__

The `__init__` method initializes the `CircuitBreaker` class with default or provided values for `max_failures` and `reset_timeout`. It sets the initial state to `CLOSED`, initializes the failure count to zero, and records the current time as the last attempt timestamp.

### CircuitBreaker.__call__

The `__call__` method is a decorator that wraps the target function. It checks the state of the circuit breaker and either allows the function call, transitions the state, or raises a `CircuitOpenException` based on the number of failures and the elapsed time since the last attempt.

Example:
```python
def __call__(self, func):
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
        raise CircuitOpenException()
    return wrapped_func
```
*Decorator method that manages the state transitions and function call attempts.*

## Dependencies Used and Their Descriptions

### time

The `time` module is used to record the current time for managing the reset timeout and the last attempt timestamp. It provides the `time()` function to get the current time in seconds since the epoch.

### functools

The `functools` module is used to preserve the metadata of the wrapped function. The `wraps` decorator is applied to the `wrapped_func` to ensure that it retains the original function's name, docstring, and other attributes.

## Functional Flow

The functional flow of the `circuit_breaker.py` file starts with the initialization of the `CircuitBreaker` class, setting the initial state and parameters. The `__call__` method is then used as a decorator to wrap the target function. When the wrapped function is called, the current state of the circuit breaker is checked. If the state is `OPEN` and the reset timeout has elapsed, the state transitions to `HALF-OPEN`. If the state is `HALF-OPEN`, the function is attempted, and based on the result, the state transitions to `CLOSED` or back to `OPEN`. If the state is `CLOSED`, the function is called, and failures are tracked. If the maximum number of failures is reached, the state transitions to `OPEN`. If the state is `OPEN`, a `CircuitOpenException` is raised.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The functionality is focused on implementing the circuit breaker pattern as a decorator for functions.