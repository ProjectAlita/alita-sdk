# constants.py

**Path:** `src/alita_sdk/community/eda/utils/constants.py`

## Data Flow

The `constants.py` file primarily defines a set of constants used throughout the project. These constants include file paths, status labels, and date-time values. The data flow in this file is straightforward as it involves the initialization of these constants and their potential use in other parts of the project. The constants are defined at the module level, making them accessible throughout the project wherever this module is imported. For example, the `OUTPUT_FOLDER` constant defines the directory where output data will be stored, and other constants like `OUTPUT_WORK_ITEMS` build upon this base path to specify complete file paths. The `DATE_UTC` constant is dynamically generated using the `string_to_datetime` function, which converts the current UTC time to a specific format. This constant is then used to calculate the `TIME_IN_STATUS_OPEN` by finding the difference in days between the current date and a predefined timestamp `OPEN_ISSUE_CREATED`.

Example:
```python
OUTPUT_FOLDER = './raw_data/'
OUTPUT_WORK_ITEMS_FILE = 'data_work_items_'
OUTPUT_WORK_ITEMS = OUTPUT_FOLDER + OUTPUT_WORK_ITEMS_FILE
```
In this example, `OUTPUT_FOLDER` is the base directory, and `OUTPUT_WORK_ITEMS_FILE` is the filename prefix. `OUTPUT_WORK_ITEMS` combines these to form the complete path.

## Functions Descriptions

This file does not contain any functions. Instead, it focuses on defining constants that are used across the project. The only function-related aspect is the import of the `string_to_datetime` function from another module, which is used to initialize the `DATE_UTC` constant.

## Dependencies Used and Their Descriptions

1. `datetime`: This standard library module is used to get the current UTC time.
2. `pandas.Timestamp`: This is used to create a specific timestamp for the `OPEN_ISSUE_CREATED` constant.
3. `string_to_datetime`: This function is imported from a sibling module and is used to convert a string representation of a date-time into a `datetime` object.

Example:
```python
from datetime import datetime
from pandas import Timestamp
from ..utils.convert_to_datetime import string_to_datetime
```
These imports are essential for initializing some of the constants in the file.

## Functional Flow

The functional flow of this file is linear and involves the initialization of constants. There are no functions or complex logic structures. The constants are defined at the top level and are immediately available for use throughout the project. The `DATE_UTC` constant is dynamically generated at runtime, ensuring it always holds the current UTC time when the module is imported. This dynamic generation is the only aspect that introduces a runtime element to the otherwise static nature of the file.

## Endpoints Used/Created

This file does not define or interact with any endpoints. Its sole purpose is to provide a centralized location for constants that can be used throughout the project.