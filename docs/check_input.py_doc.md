# check_input.py

**Path:** `src/alita_sdk/community/eda/utils/check_input.py`

## Data Flow

The data flow within the `check_input.py` file is straightforward and involves validating input parameters and checking file states. The primary data elements are the input date string and the file path to a CSV file. The `check_input_date` function takes a date string as input, validates its format using a regular expression, and logs an error if the format is incorrect. The `check_if_open` function takes a file path as input, checks if the file is open, and prompts the user to close it if necessary. The data flow is linear, with data being passed into the functions, processed, and either validated or used to prompt the user for further action.

Example:
```python
# Example of data validation in check_input_date function
if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
    logging.error('The since_date parameter must be in the format YYYY-MM-DD')
    raise ValueError('The since_date parameter must be in the format YYYY-MM-DD')
```

## Functions Descriptions

### check_input_date

This function checks if the input date is in the correct format (YYYY-MM-DD). It takes a single parameter, `date_str`, which is the date string to be validated. The function uses a regular expression to match the date format and logs an error and raises a `ValueError` if the format is incorrect.

### check_if_open

This function checks if a file is open and prompts the user to close it if necessary. It takes a single parameter, `path_to_csv`, which is the file path to the CSV file. The function attempts to open the file in read-write mode and catches a `PermissionError` if the file is open, prompting the user to close it before proceeding.

Example:
```python
# Example of file open check in check_if_open function
try:
    f = open(path_to_csv, 'r+')
    f.close()
except PermissionError:
    six.moves.input(f'Close the file {path_to_csv} and then press the <ENTER> key to continue...')
```

## Dependencies Used and Their Descriptions

### re

The `re` module is used for regular expression matching. In this file, it is used to validate the format of the input date string in the `check_input_date` function.

### logging

The `logging` module is used for logging error messages. In this file, it is used to log an error message if the input date string is not in the correct format in the `check_input_date` function.

### os.path

The `os.path` module is used to check the existence of the file path. In this file, it is used in the `check_if_open` function to check if the file exists before attempting to open it.

### six

The `six` module is used for compatibility between Python 2 and 3. In this file, it is used to prompt the user to close the file if it is open in the `check_if_open` function.

## Functional Flow

The functional flow of the `check_input.py` file involves two main functions: `check_input_date` and `check_if_open`. The `check_input_date` function is called to validate the format of an input date string. If the date string is not in the correct format, an error is logged, and a `ValueError` is raised. The `check_if_open` function is called to check if a file is open. If the file is open, the user is prompted to close it before proceeding. The flow is linear, with each function performing its specific task based on the input parameters.

## Endpoints Used/Created

There are no endpoints used or created in the `check_input.py` file.