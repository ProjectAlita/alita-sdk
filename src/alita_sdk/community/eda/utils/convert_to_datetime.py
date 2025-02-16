"""This module contains functions for converting date and time to datetime type."""

from datetime import datetime
from typing import Optional
import logging
import pandas as pd


def string_to_datetime(date_as_string: Optional[str]) -> Optional[datetime]:
    """Takes first 19 symbols of a string and converts it to the datetime type."""
    if (not date_as_string or date_as_string == 'None' or not isinstance(date_as_string, str) or
            pd.isnull(date_as_string)):
        return None

    if len(date_as_string) > 10 and 'T' in date_as_string:
        try:
            return datetime.strptime(date_as_string[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError as err:
            raise ValueError(f'time data "{date_as_string}" does not match format "yyyy-mm-ddTHH:MM:SS". '
                             f'Example: 2023-06-06T12:34:56Z') from err
    elif len(date_as_string) > 10 and 'T' not in date_as_string:
        try:
            return datetime.strptime(date_as_string[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError as err:
            raise ValueError(f'time data "{date_as_string}" does not match format "yyyy-mm-dd HH:MM:SS". '
                             f'Example: 2023-06-06 12:34:56') from err
    elif len(date_as_string) == 10 and '-' in date_as_string:
        return datetime.strptime(date_as_string, "%Y-%m-%d")
    return datetime.strptime(date_as_string, "%Y-%m-%d")


def unix_milliseconds_to_datetime(unix_time: str) -> Optional[datetime]:
    """Convert Unix time in milliseconds to datetime."""
    if not unix_time:
        return None

    return datetime.fromtimestamp(int(unix_time)/1000)


def string_to_unix_milliseconds(date_string: str) -> Optional[int]:
    """Convert datetime string to Unix time in milliseconds."""
    if not date_string:
        return None
    try:
        date_object = datetime.strptime(date_string, "%Y-%m-%d").date()
        timestamp_seconds = datetime.combine(date_object, datetime.min.time()).timestamp()
        return int(timestamp_seconds * 1000)
    except ValueError as exc:
        logging.error('Print the date for updated_after parameter in the format YYYY-MM-DD.')
        raise exc
