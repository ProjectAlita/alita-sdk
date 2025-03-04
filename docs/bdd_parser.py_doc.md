# bdd_parser.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/bdd_parser.py`

## Data Flow

The data flow within `bdd_parser.py` revolves around the processing of BDD (Behavior-Driven Development) scenarios from feature files. The primary data elements are the scenarios and steps extracted from these files. The data flow can be summarized as follows:

1. **Data Origin:** The data originates from feature files located in a specified directory. These files have extensions `.feature` or `.story`.
2. **Data Extraction:** The `get_all_scenarios_from_directory` function traverses the directory, identifies relevant files, and uses the `parse_feature` function to extract scenarios from these files.
3. **Data Transformation:** The extracted scenarios are transformed into a pandas DataFrame using functions like `get_initial_steps_data_frame` and `create_scenarios_data_frame`. These functions process the scenario steps, normalize parameter names, and filter tags.
4. **Data Aggregation:** Functions like `get_first_instance`, `get_keyword`, and `get_count` aggregate the data to provide insights such as the first instance of each step, the most frequent BDD keyword, and the count of each step-keyword combination.
5. **Data Merging:** The `get_final_data_frame` function merges multiple DataFrames to create a comprehensive view of the scenarios and steps.
6. **Data Filtering:** The `filter_tags` function filters out unwanted tags from the DataFrame.
7. **Data Output:** The final DataFrame is ready for further analysis or reporting.

Example:
```python
# Example of data extraction and transformation
scenarios = get_all_scenarios_from_directory('path/to/directory')
df_initial = get_initial_steps_data_frame(scenarios)
```

## Functions Descriptions

### get_all_scenarios_from_directory

This function searches for feature files in a given directory and extracts scenarios from them.

- **Parameters:**
  - `directory_name` (str): The name of the directory to search for feature files.
- **Returns:**
  - A generator of `ScenarioTemplate` objects representing all the scenarios found in the directory and its subdirectories.

### get_initial_steps_data_frame

This function creates a pandas DataFrame from a list of scenarios, with columns representing various information about the steps in the scenarios.

- **Parameters:**
  - `scenarios` (Generator[ScenarioTemplate, Any, None]): A list of `ScenarioTemplate` objects representing the scenarios.
- **Returns:**
  - A pandas DataFrame object containing the initial steps' data.

### create_scenarios_data_frame

This function creates a pandas DataFrame from a list of scenarios, with columns representing the scenario name, steps, test data, and tags.

- **Parameters:**
  - `scenarios` (Generator[ScenarioTemplate, Any, None]): A list of `ScenarioTemplate` objects representing the scenarios.
- **Returns:**
  - A pandas DataFrame object containing the scenarios' data.

### get_first_instance

This function returns the first instance of each 'Original Step' group in a DataFrame.

- **Parameters:**
  - `df` (DataFrame): A pandas DataFrame containing the data to be processed.
- **Returns:**
  - A pandas DataFrame with the first instance of each 'Original Step' group.

### get_keyword

This function returns a DataFrame with the most frequently occurring BDD keyword for each unique original step.

- **Parameters:**
  - `df` (DataFrame): A pandas DataFrame containing the 'BDD Keyword' and 'Original Step' columns.
- **Returns:**
  - A new DataFrame with the 'BDD Keyword' column containing the most frequently occurring BDD keyword for each unique original step.

### get_count

This function returns the count of each combination of 'Original Step' and 'BDD Keyword' in a DataFrame.

- **Parameters:**
  - `df` (DataFrame): The DataFrame containing the data.
- **Returns:**
  - The DataFrame with the count of each combination.

### get_final_data_frame

This function merges multiple DataFrames to create a comprehensive view of the scenarios and steps.

- **Parameters:**
  - `df_first_instance` (DataFrame): The first DataFrame to be merged.
  - `df_keyword` (DataFrame): The second DataFrame to be merged.
  - `df_with_count` (DataFrame): The third DataFrame to be merged.
- **Returns:**
  - The merged DataFrame.

### filter_tags

This function filters the given DataFrame based on specified tags.

- **Parameters:**
  - `df` (DataFrame): The DataFrame to be filtered.
- **Returns:**
  - The filtered DataFrame.

### convert_tags_to_list

This function converts the 'Tags' column from a set to a list.

- **Parameters:**
  - `df` (DataFrame): The DataFrame containing the data.
- **Returns:**
  - The DataFrame with the 'Tags' column converted to a list.

### normalize_parameter_names

This function normalizes the parameter names in a step.

- **Parameters:**
  - `step` (str): The step to normalize.
- **Returns:**
  - The normalized step.

### merge_semantically_similar_steps

This function merges semantically similar steps in the DataFrame.

- **Parameters:**
  - `df` (DataFrame): The DataFrame containing the data.
- **Returns:**
  - The DataFrame with semantically similar steps merged.

### extract_all_tags

This function extracts all the tags for all the available BDD steps.

- **Parameters:**
  - `df` (DataFrame): The DataFrame containing the data.
- **Returns:**
  - A set containing all the tags.

## Dependencies Used and Their Descriptions

### functools

- **Purpose:** Used for higher-order functions that act on or return other functions.
- **Usage:** Utilized in the `get_first_instance` function to apply a union operation on sets of tags.

### os

- **Purpose:** Provides a way of using operating system-dependent functionality like reading or writing to the file system.
- **Usage:** Used in the `get_all_scenarios_from_directory` function to traverse directories and identify relevant files.

### re

- **Purpose:** Provides regular expression matching operations.
- **Usage:** Used in various functions to search, split, and manipulate strings based on patterns.

### string

- **Purpose:** Contains a collection of string operations and constants.
- **Usage:** Used in the `get_initial_steps_data_frame` and `create_scenarios_data_frame` functions to manipulate and format strings.

### typing

- **Purpose:** Provides runtime support for type hints.
- **Usage:** Used to specify the types of parameters and return values in function signatures.

### numpy

- **Purpose:** Supports large, multi-dimensional arrays and matrices, along with a collection of mathematical functions to operate on these arrays.
- **Usage:** Used in the `get_initial_steps_data_frame` and `create_scenarios_data_frame` functions to create and manipulate arrays.

### pandas

- **Purpose:** Provides data structures and data analysis tools.
- **Usage:** Used extensively to create and manipulate DataFrames in various functions.

### parser

- **Purpose:** Custom module for parsing feature files and extracting scenarios.
- **Usage:** Used in the `get_all_scenarios_from_directory` function to parse feature files and extract scenarios.

## Functional Flow

The functional flow of `bdd_parser.py` involves a sequence of operations to extract, transform, and analyze BDD scenarios from feature files. The flow can be summarized as follows:

1. **Initialization:** The process begins with the `get_all_scenarios_from_directory` function, which initializes the extraction of scenarios from feature files in a specified directory.
2. **Data Extraction:** The scenarios are extracted using the `parse_feature` function and yielded as `ScenarioTemplate` objects.
3. **Data Transformation:** The extracted scenarios are transformed into a pandas DataFrame using the `get_initial_steps_data_frame` function. This DataFrame contains columns representing various information about the steps in the scenarios.
4. **Data Aggregation:** The `get_first_instance`, `get_keyword`, and `get_count` functions aggregate the data to provide insights such as the first instance of each step, the most frequent BDD keyword, and the count of each step-keyword combination.
5. **Data Merging:** The `get_final_data_frame` function merges multiple DataFrames to create a comprehensive view of the scenarios and steps.
6. **Data Filtering:** The `filter_tags` function filters out unwanted tags from the DataFrame.
7. **Data Output:** The final DataFrame is ready for further analysis or reporting.

Example:
```python
# Example of functional flow
scenarios = get_all_scenarios_from_directory('path/to/directory')
df_initial = get_initial_steps_data_frame(scenarios)
df_first_instance = get_first_instance(df_initial)
df_keyword = get_keyword(df_initial)
df_count = get_count(df_initial)
df_final = get_final_data_frame(df_first_instance, df_keyword, df_count)
df_filtered = filter_tags(df_final)
```

## Endpoints Used/Created

There are no explicit endpoints used or created within `bdd_parser.py`. The functionality is focused on processing local feature files and does not involve any network communication or API calls.
