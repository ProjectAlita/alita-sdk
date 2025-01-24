# bdd_parser.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/bdd_parser.py`

## Data Flow

The data flow within `bdd_parser.py` is centered around the processing of BDD (Behavior-Driven Development) scenarios from feature files. The primary data elements are the scenarios and steps extracted from these files. The data flow can be summarized as follows:

1. **Data Origin:** The data originates from feature files located in a specified directory. These files have extensions `.feature` or `.story`.
2. **Data Extraction:** The `get_all_scenarios_from_directory` function traverses the directory, identifies relevant files, and extracts scenarios using the `parse_feature` function.
3. **Data Transformation:** The extracted scenarios are transformed into a pandas DataFrame using functions like `get_initial_steps_data_frame` and `create_scenarios_data_frame`. These functions process the steps within each scenario, extracting relevant information and organizing it into a structured format.
4. **Data Aggregation:** Functions like `get_first_instance`, `get_keyword`, and `get_count` further process the DataFrame to aggregate and summarize the data, such as identifying the first instance of each step, determining the most frequent BDD keyword, and counting occurrences.
5. **Data Filtering:** The `filter_tags` function filters out unwanted tags from the DataFrame based on predefined criteria.
6. **Data Normalization:** The `normalize_parameter_names` function standardizes the parameter names within steps to ensure consistency.
7. **Data Merging:** The `merge_semantically_similar_steps` function combines semantically similar steps to reduce redundancy.
8. **Data Output:** The final processed data is returned as a pandas DataFrame, ready for further analysis or use.

Example:
```python
# Example of data extraction and transformation
scenarios = get_all_scenarios_from_directory('path/to/directory')
data_frame = get_initial_steps_data_frame(scenarios)
```

## Functions Descriptions

### get_all_scenarios_from_directory

This function searches for feature files in a specified directory and extracts scenarios from them.

- **Parameters:**
  - `directory_name` (str): The name of the directory to search for feature files.
- **Returns:**
  - A generator of `ScenarioTemplate` objects representing all the scenarios found in the directory and its subdirectories.

### get_initial_steps_data_frame

This function creates a pandas DataFrame from a list of `ScenarioTemplate` objects, representing the initial steps' data.

- **Parameters:**
  - `scenarios` (Generator[ScenarioTemplate, Any, None]): A list of `ScenarioTemplate` objects representing the scenarios.
- **Returns:**
  - A pandas DataFrame object containing the initial steps' data.

### create_scenarios_data_frame

This function creates a pandas DataFrame from a list of `ScenarioTemplate` objects, representing the scenarios' data.

- **Parameters:**
  - `scenarios` (Generator[ScenarioTemplate, Any, None]): A list of `ScenarioTemplate` objects representing the scenarios.
- **Returns:**
  - A pandas DataFrame object containing the scenarios' data.

### get_first_instance

This function processes a DataFrame to get the first instance of each 'Original Step' group.

- **Parameters:**
  - `df` (DataFrame): A pandas DataFrame containing the data to be processed.
- **Returns:**
  - A pandas DataFrame with the first instance of each 'Original Step' group.

### get_keyword

This function processes a DataFrame to get the most frequently occurring BDD keyword for each unique original step.

- **Parameters:**
  - `df` (DataFrame): A pandas DataFrame containing the 'BDD Keyword' and 'Original Step' columns.
- **Returns:**
  - A new DataFrame with the 'BDD Keyword' column containing the most frequently occurring BDD keyword for each unique original step.

### get_count

This function processes a DataFrame to get the count of each combination of 'Original Step' and 'BDD Keyword'.

- **Parameters:**
  - `df` (DataFrame): The DataFrame containing the data.
- **Returns:**
  - The DataFrame with the count of each combination.

### get_final_data_frame

This function merges three DataFrames to create a final DataFrame.

- **Parameters:**
  - `df_first_instance` (DataFrame): The first DataFrame to be merged.
  - `df_keyword` (DataFrame): The second DataFrame to be merged.
  - `df_with_count` (DataFrame): The third DataFrame to be merged.
- **Returns:**
  - The merged DataFrame.

### filter_tags

This function filters a DataFrame based on specified tags.

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

- **Purpose:** Provides a way of using operating system-dependent functionality.
- **Usage:** Utilized in the `get_all_scenarios_from_directory` function to traverse directories and identify relevant files.

### re

- **Purpose:** Provides support for regular expressions.
- **Usage:** Utilized in various functions for pattern matching and text processing.

### string

- **Purpose:** Provides a collection of string operations.
- **Usage:** Utilized in various functions for string manipulation and formatting.

### typing

- **Purpose:** Provides support for type hints.
- **Usage:** Utilized throughout the code for type annotations.

### numpy

- **Purpose:** Provides support for large, multi-dimensional arrays and matrices, along with a collection of mathematical functions to operate on these arrays.
- **Usage:** Utilized in the `get_initial_steps_data_frame` and `create_scenarios_data_frame` functions to create and manipulate arrays.

### pandas

- **Purpose:** Provides data structures and data analysis tools.
- **Usage:** Utilized throughout the code for creating and manipulating DataFrames.

### parse_feature

- **Purpose:** Parses feature files to extract scenarios.
- **Usage:** Utilized in the `get_all_scenarios_from_directory` function to parse feature files.

### ScenarioTemplate

- **Purpose:** Represents a BDD scenario template.
- **Usage:** Utilized throughout the code to represent and manipulate BDD scenarios.

## Functional Flow

The functional flow of `bdd_parser.py` involves the following sequence of operations:

1. **Directory Traversal:** The `get_all_scenarios_from_directory` function is called to traverse a specified directory and identify relevant feature files.
2. **Scenario Extraction:** The `parse_feature` function is used to extract scenarios from the identified feature files.
3. **DataFrame Creation:** The extracted scenarios are transformed into a pandas DataFrame using the `get_initial_steps_data_frame` and `create_scenarios_data_frame` functions.
4. **Data Processing:** The DataFrame is further processed using functions like `get_first_instance`, `get_keyword`, and `get_count` to aggregate and summarize the data.
5. **Data Filtering:** The `filter_tags` function is used to filter out unwanted tags from the DataFrame.
6. **Data Normalization:** The `normalize_parameter_names` function is used to standardize the parameter names within steps.
7. **Data Merging:** The `merge_semantically_similar_steps` function is used to combine semantically similar steps.
8. **Final DataFrame:** The final processed data is returned as a pandas DataFrame, ready for further analysis or use.

Example:
```python
# Example of functional flow
scenarios = get_all_scenarios_from_directory('path/to/directory')
data_frame = get_initial_steps_data_frame(scenarios)
filtered_data_frame = filter_tags(data_frame)
final_data_frame = merge_semantically_similar_steps(filtered_data_frame)
```

## Endpoints Used/Created

There are no explicit endpoints used or created within `bdd_parser.py`. The functionality is focused on processing BDD scenarios from feature files and transforming them into a structured format for further analysis.