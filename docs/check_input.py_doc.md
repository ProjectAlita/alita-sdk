# check_input.py

**Path:** `src/alita_sdk/community/eda/utils/check_input.py`

## Data Flow

The data flow within `check_input.py` is straightforward and involves validating input parameters and checking file states. The module primarily deals with two types of data: date strings and file paths. The `check_input_date` function takes a date string as input and verifies its format using a regular expression. If the format is incorrect, it logs an error and raises a `ValueError`. The `check_if_open` function takes a file path as input and checks if the file is open. If the file is open, it prompts the user to close it before proceeding. The data flow is linear, with data being passed into functions, validated, and then either logged or used to prompt user actions.

Example:
```python
import re
import logging

# Function to check date format
if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
    logging.error('The since_date parameter must be in the format YYYY-MM-DD')
    raise ValueError('The since_date parameter must be in the format YYYY-MM-DD')
```

## Functions Descriptions

### check_input_date

This function checks if the input date string is in the correct format (YYYY-MM-DD). It uses a regular expression to validate the format. If the format is incorrect, it logs an error message and raises a `ValueError`.

**Parameters:**
- `date_str` (str): The date string to check.

**Returns:**
- None

Example:
```python
def check_input_date(date_str: str) -> None:
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        logging.error('The since_date parameter must be in the format YYYY-MM-DD')
        raise ValueError('The since_date parameter must be in the format YYYY-MM-DD')
```

### check_if_open

This function checks if a file is open. If the file is open, it prompts the user to close it before proceeding. It uses a loop to repeatedly check the file state until it is closed.

**Parameters:**
- `path_to_csv` (str): The path to the CSV file to check.

**Returns:**
- None

Example:
```python
def check_if_open(path_to_csv):
    if path.exists(path_to_csv):
        file_open = True
        while file_open:
            try:
                f = open(path_to_csv, 'r+')
                f.close()
            except PermissionError:
                six.moves.input(f'Close the file {path_to_csv} and then press the <ENTER> key to continue...')
            else:
                file_open = False
```

## Dependencies Used and Their Descriptions

### re

The `re` module is used for regular expression matching. In this file, it is used to validate the format of the date string in the `check_input_date` function.

### logging

The `logging` module is used to log error messages. In this file, it is used to log an error message if the date string format is incorrect in the `check_input_date` function.

### os.path

The `os.path` module is used to check the existence of the file path in the `check_if_open` function.

### six

The `six` module is used for compatibility between Python 2 and 3. In this file, it is used to prompt the user to close the file in the `check_if_open` function.

## Functional Flow

1. The `check_input_date` function is called with a date string as an argument.
2. The function uses a regular expression to check if the date string is in the correct format.
3. If the format is incorrect, an error message is logged, and a `ValueError` is raised.
4. The `check_if_open` function is called with a file path as an argument.
5. The function checks if the file exists and is open.
6. If the file is open, the user is prompted to close it.
7. The function repeatedly checks the file state until it is closed.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints.