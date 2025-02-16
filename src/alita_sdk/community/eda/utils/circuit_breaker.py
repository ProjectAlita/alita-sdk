"""This module contains a simple implementation of the circuit breaker pattern."""
import time
import functools


class CircuitOpenException(Exception):
    """Exception raised when the circuit breaker is open."""
    def __init__(self, message="Circuit is open!"):
        super().__init__(message)


class CircuitBreaker:
    """
    This class is a simple implementation of the circuit breaker pattern.
    Attributes:
        max_failures: int
            the maximum number of failures allowed before the circuit is opened.
        reset_timeout: int
            the time in seconds before the circuit is reset to the closed state.
        failures: int
            the number of consecutive failures.
        state: str
            the current state of the circuit breaker (OPEN, HALF-OPEN, CLOSED).
        last_attempt: float
            the timestamp of the last attempt to call the function.
    """
    def __init__(self, max_failures=3, reset_timeout=10):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = 'CLOSED'
        self.last_attempt = time.time()

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

            # OPEN state
            raise CircuitOpenException()

        return wrapped_func
