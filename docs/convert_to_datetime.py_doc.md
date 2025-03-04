# convert_to_datetime.py

**Path:** `src/alita_sdk/community/eda/utils/convert_to_datetime.py`

## Data Flow

The data flow within the `convert_to_datetime.py` file primarily revolves around converting various date and time formats into Python's `datetime` objects. The data originates as strings or Unix time in milliseconds and is transformed into `datetime` objects or Unix time in milliseconds. The functions handle different formats and ensure that the data is correctly parsed and converted. Intermediate variables are used to store the parsed date and time before conversion. The data flow is straightforward, with input data being processed and returned in the desired format.

Example:
```python
if len(date_as_string) > 10 and 'T' in date_as_string:
    try:
        return datetime.strptime(date_as_string[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError as err:
        raise ValueError(f'time data "{date_as_string}" does not match format "yyyy-mm-ddTHH:MM:SS". '
                         f'Example: 2023-06-06T12:34:56Z') from err
```
In this example, the function checks if the string contains a 'T' and then attempts to parse it into a `datetime` object.

## Functions Descriptions

### `string_to_datetime`

This function converts a string representation of a date and time into a `datetime` object. It takes an optional string as input and returns an optional `datetime` object. The function handles different date and time formats, including those with 'T' separators and those without. It raises a `ValueError` if the string does not match the expected format.

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

This function converts Unix time in milliseconds to a `datetime` object. It takes a string representing Unix time in milliseconds as input and returns an optional `datetime` object. The function divides the Unix time by 1000 to convert it to seconds and then uses `datetime.fromtimestamp` to create the `datetime` object.

Example:
```python
def unix_milliseconds_to_datetime(unix_time: str) -> Optional[datetime]:
    if not unix_time:
        return None

    return datetime.fromtimestamp(int(unix_time)/1000)
```

### `string_to_unix_milliseconds`

This function converts a date string to Unix time in milliseconds. It takes a string representing a date in the format `YYYY-MM-DD` as input and returns an optional integer representing Unix time in milliseconds. The function parses the date string into a `datetime` object, combines it with the minimum time, and then converts it to Unix time in seconds, which is then multiplied by 1000 to get milliseconds.

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

The `datetime` module is used for manipulating dates and times. It provides classes for working with both dates and times, allowing for arithmetic operations, formatting, and parsing.

### `Optional`

The `Optional` type hint from the `typing` module is used to indicate that a function parameter or return value can be of a specified type or `None`.

### `logging`

The `logging` module is used for logging error messages. It provides a flexible framework for emitting log messages from Python programs.

### `pandas`

The `pandas` library is used for data manipulation and analysis. In this file, it is used to check for null values in the input strings.

## Functional Flow

1. The `string_to_datetime` function is called with a date string as input. It checks the format of the string and attempts to parse it into a `datetime` object.
2. The `unix_milliseconds_to_datetime` function is called with Unix time in milliseconds as input. It converts the Unix time to seconds and then to a `datetime` object.
3. The `string_to_unix_milliseconds` function is called with a date string as input. It parses the date string into a `datetime` object, converts it to Unix time in seconds, and then to milliseconds.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It focuses on converting date and time formats to `datetime` objects and Unix time in milliseconds.