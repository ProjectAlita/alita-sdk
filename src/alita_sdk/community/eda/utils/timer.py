"""This module contains timer decorator."""

import logging

from time import perf_counter
from functools import wraps


logging.basicConfig(filename="./logs/eda_output.log",
                    level=logging.INFO,
                    format="%(asctime)s - %(message)s")


def timer(func):
    """Calculate duration of a code execution and write this data to the log file."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        duration = end - start
        if not args:
            logging.info(f'{func.__name__} -> duration {duration:.8f}s')
            print(f'{func.__name__} -> duration {duration:.8f}s')
        if args:
            arg = list(args)[0]
            logging.info(f'{func.__name__} for ({arg}) -> duration {duration:.8f}s')
            print(f'{func.__name__} for ({arg}) -> duration {duration:.8f}s')
        return result
    return wrapper
