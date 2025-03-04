# constants.py

**Path:** `src/alita_sdk/community/eda/utils/constants.py`

## Data Flow

The data flow within `constants.py` is relatively straightforward as it primarily involves the definition and initialization of constants used throughout the project. These constants are defined at the module level and are intended to be imported and used by other modules within the project. The constants include file paths, status labels, and date-related values. For example, the `OUTPUT_FOLDER` constant defines the base directory for output files, and other constants like `OUTPUT_WORK_ITEMS` and `OUTPUT_MAPPING` build upon this base directory to specify complete file paths. Additionally, the `DATE_UTC` constant is initialized using the `string_to_datetime` function, which converts the current UTC time to a specific string format. This constant is then used to calculate the `TIME_IN_STATUS_OPEN` value, representing the number of days an issue has been open. The data flow is primarily unidirectional, with constants being defined and then used elsewhere in the project.

```python
OUTPUT_FOLDER = './raw_data/'
OUTPUT_WORK_ITEMS_FILE = 'data_work_items_'
OUTPUT_WORK_ITEMS = OUTPUT_FOLDER + OUTPUT_WORK_ITEMS_FILE
OUTPUT_MAPPING_FILE = 'map_statuses_'
OUTPUT_MAPPING = OUTPUT_FOLDER + OUTPUT_MAPPING_FILE
DATE_UTC = string_to_datetime(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
TIME_IN_STATUS_OPEN = (DATE_UTC - OPEN_ISSUE_CREATED).days
```

In this snippet, constants are defined and combined to form complete file paths, and a date constant is calculated and used to determine the time an issue has been open.

## Functions Descriptions

The `constants.py` file does not contain any functions. Instead, it focuses on defining constants that are used throughout the project. These constants include file paths, status labels, and date-related values. The constants are defined at the module level and are intended to be imported and used by other modules within the project. For example, the `OUTPUT_FOLDER` constant defines the base directory for output files, and other constants like `OUTPUT_WORK_ITEMS` and `OUTPUT_MAPPING` build upon this base directory to specify complete file paths. Additionally, the `DATE_UTC` constant is initialized using the `string_to_datetime` function, which converts the current UTC time to a specific string format. This constant is then used to calculate the `TIME_IN_STATUS_OPEN` value, representing the number of days an issue has been open.

## Dependencies Used and Their Descriptions

The `constants.py` file imports several dependencies, including:

- `datetime`: This module is part of the Python standard library and provides classes for manipulating dates and times. In this file, it is used to get the current UTC time.
- `pandas.Timestamp`: This class is part of the Pandas library and is used to represent dates and times. In this file, it is used to define a specific timestamp for an open issue.
- `string_to_datetime`: This function is imported from the `convert_to_datetime` module within the same project. It is used to convert a string representation of a date and time to a `datetime` object.

These dependencies are used to define date-related constants and to perform date and time calculations. For example, the `datetime` module is used to get the current UTC time, which is then converted to a specific string format using the `string_to_datetime` function. The `pandas.Timestamp` class is used to define a specific timestamp for an open issue.

## Functional Flow

The functional flow of the `constants.py` file is straightforward as it primarily involves the definition and initialization of constants. The file starts by importing the necessary dependencies, including the `datetime` module, the `pandas.Timestamp` class, and the `string_to_datetime` function. It then defines a series of constants, including file paths, status labels, and date-related values. These constants are defined at the module level and are intended to be imported and used by other modules within the project. For example, the `OUTPUT_FOLDER` constant defines the base directory for output files, and other constants like `OUTPUT_WORK_ITEMS` and `OUTPUT_MAPPING` build upon this base directory to specify complete file paths. Additionally, the `DATE_UTC` constant is initialized using the `string_to_datetime` function, which converts the current UTC time to a specific string format. This constant is then used to calculate the `TIME_IN_STATUS_OPEN` value, representing the number of days an issue has been open.

## Endpoints Used/Created

The `constants.py` file does not define or interact with any endpoints. Its primary purpose is to define constants that are used throughout the project. These constants include file paths, status labels, and date-related values. The constants are defined at the module level and are intended to be imported and used by other modules within the project. For example, the `OUTPUT_FOLDER` constant defines the base directory for output files, and other constants like `OUTPUT_WORK_ITEMS` and `OUTPUT_MAPPING` build upon this base directory to specify complete file paths. Additionally, the `DATE_UTC` constant is initialized using the `string_to_datetime` function, which converts the current UTC time to a specific string format. This constant is then used to calculate the `TIME_IN_STATUS_OPEN` value, representing the number of days an issue has been open.
