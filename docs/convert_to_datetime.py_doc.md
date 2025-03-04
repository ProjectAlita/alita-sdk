# convert_to_datetime.py

**Path:** `src/alita_sdk/community/eda/utils/convert_to_datetime.py`

## Data Flow

The data flow within the `convert_to_datetime.py` file revolves around converting various date and time formats into Python's `datetime` objects. The data originates as strings or Unix time in milliseconds and is transformed into `datetime` objects through a series of function calls. The primary data elements are date strings and Unix time, which are manipulated using Python's `datetime` module and the `pandas` library for null checks. The data flow can be summarized as follows:

1. **Input:** Date strings or Unix time in milliseconds.
2. **Processing:** Conversion functions parse and transform the input data into `datetime` objects.
3. **Output:** The resulting `datetime` objects or Unix time in milliseconds.

Example:
```python
from datetime import datetime

def string_to_datetime(date_as_string: Optional[str]) -> Optional[datetime]:
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
```
In this example, the function `string_to_datetime` takes a date string, checks its format, and converts it to a `datetime` object.

## Functions Descriptions

### `string_to_datetime`

This function converts a date string into a `datetime` object. It takes a string as input and returns a `datetime` object or `None` if the input is invalid. The function checks the format of the date string and uses `datetime.strptime` to parse it. If the string is in the format `yyyy-mm-ddTHH:MM:SS`, it is parsed accordingly. If the string is in the format `yyyy-mm-dd HH:MM:SS`, it is parsed differently. If the string is only a date (`yyyy-mm-dd`), it is parsed as such. The function raises a `ValueError` if the string does not match the expected formats.

Example:
```python
def string_to_datetime(date_as_string: Optional[str]) -> Optional[datetime]:
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
```

### `unix_milliseconds_to_datetime`

This function converts Unix time in milliseconds to a `datetime` object. It takes a string representing Unix time in milliseconds as input and returns a `datetime` object. The function checks if the input is valid and uses `datetime.fromtimestamp` to convert the Unix time to a `datetime` object.

Example:
```python
def unix_milliseconds_to_datetime(unix_time: str) -> Optional[datetime]:
    if not unix_time:
        return None
    return datetime.fromtimestamp(int(unix_time)/1000)
```

### `string_to_unix_milliseconds`

This function converts a date string to Unix time in milliseconds. It takes a date string as input and returns an integer representing Unix time in milliseconds. The function checks if the input is valid, parses the date string using `datetime.strptime`, and calculates the Unix time in milliseconds.

Example:
```python
def string_to_unix_milliseconds(date_string: str) -> Optional[int]:
    if not date_string:
        return None
    try:
        date_object = datetime.strptime(date_string, "%Y-%m-%d").date()
        timestamp_seconds = datetime.combine(date_object, datetime.min.time()).timestamp()
        return int(timestamp_seconds * 1000)
    except ValueError as exc:
        logging.error('Print the date for updated_after parameter in the format YYYY-MM-DD.')
        raise exc
```

## Dependencies Used and Their Descriptions

### `datetime`

The `datetime` module supplies classes for manipulating dates and times. In this file, it is used to parse date strings, convert Unix time to `datetime` objects, and calculate Unix time in milliseconds.

### `Optional` from `typing`

The `Optional` type hint is used to indicate that a function parameter or return value can be of a specified type or `None`.

### `logging`

The `logging` module is used to log error messages when date strings do not match the expected format.

### `pandas as pd`

The `pandas` library is used to check for null values in date strings.

## Functional Flow

1. **Input Validation:** Each function first checks if the input is valid (e.g., not `None`, not an empty string, and of the correct type).
2. **Parsing and Conversion:** The functions then parse the input data and convert it to the desired format (`datetime` object or Unix time in milliseconds).
3. **Error Handling:** If the input data does not match the expected format, the functions raise appropriate errors and log messages.
4. **Return Value:** The functions return the converted data or `None` if the input is invalid.

Example:
```python
def string_to_datetime(date_as_string: Optional[str]) -> Optional[datetime]:
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
```

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It focuses solely on converting date and time formats to `datetime` objects and Unix time in milliseconds.