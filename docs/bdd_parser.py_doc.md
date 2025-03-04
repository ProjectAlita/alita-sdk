# bdd_parser.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/bdd_parser.py`

## Data Flow

The data flow within `bdd_parser.py` revolves around the processing of BDD (Behavior-Driven Development) feature files and scenarios. The primary data elements are the feature files and the scenarios extracted from them. The data flow can be summarized as follows:

1. **Input:** The directory containing feature files is provided as input to the `get_all_scenarios_from_directory` function.
2. **Processing:** The function iterates through the directory, identifying files with `.feature` and `.story` extensions. For each identified file, it calls the `parse_feature` function to extract scenarios.
3. **Transformation:** The extracted scenarios are processed to create pandas DataFrames using functions like `get_initial_steps_data_frame`, `create_scenarios_data_frame`, and others. These DataFrames organize the scenario data into structured formats for further analysis.
4. **Output:** The final output is a set of DataFrames that contain detailed information about the scenarios, steps, tags, and other relevant data.

Example:
```python
for root, dirs, files in os.walk(directory_name):
    for filename in files:
        if filename.endswith('.feature'):
            yield from parse_feature(root, filename).scenarios
        if filename.endswith('.story'):
            yield from parse_feature(root, filename, is_jbehave_story=True).scenarios
```
In this example, the code iterates through the directory, identifies feature files, and extracts scenarios using the `parse_feature` function.

## Functions Descriptions

### get_all_scenarios_from_directory

This function searches for feature files in a given directory and extracts scenarios from them.
- **Input:** `directory_name` (str) - The name of the directory to search for feature files.
- **Output:** A generator of `ScenarioTemplate` objects representing all the scenarios found in the directory and its subdirectories.

### get_initial_steps_data_frame

This function creates a pandas DataFrame containing the initial steps' data from a list of scenarios.
- **Input:** `scenarios` (Generator[ScenarioTemplate, Any, None]) - A list of `ScenarioTemplate` objects representing the scenarios.
- **Output:** A pandas DataFrame object containing the initial steps' data.

### create_scenarios_data_frame

This function creates a pandas DataFrame containing detailed information about the scenarios.
- **Input:** `scenarios` (Generator[ScenarioTemplate, Any, None]) - A list of `ScenarioTemplate` objects representing the scenarios.
- **Output:** A pandas DataFrame object containing detailed information about the scenarios.

### get_first_instance

This function processes a DataFrame to retain the first instance of each 'Original Step' group.
- **Input:** `df` (DataFrame) - A pandas DataFrame containing the data to be processed.
- **Output:** A pandas DataFrame with the first instance of each 'Original Step' group.

### get_keyword

This function determines the most frequently occurring BDD keyword for each unique original step.
- **Input:** `df` (DataFrame) - A pandas DataFrame containing the 'BDD Keyword' and 'Original Step' columns.
- **Output:** A new DataFrame with the 'BDD Keyword' column containing the most frequently occurring BDD keyword for each unique original step.

### get_count

This function calculates the count of each combination of 'Original Step' and 'BDD Keyword' in the given DataFrame.
- **Input:** `df` (DataFrame) - The DataFrame containing the data.
- **Output:** The DataFrame with the count of each combination.

### get_final_data_frame

This function merges three DataFrames to create a final DataFrame with comprehensive data.
- **Input:** `df_first_instance` (DataFrame), `df_keyword` (DataFrame), `df_with_count` (DataFrame)
- **Output:** The merged DataFrame.

### filter_tags

This function filters the given DataFrame based on specified tags.
- **Input:** `df` (DataFrame) - The DataFrame to be filtered.
- **Output:** The filtered DataFrame.

### convert_tags_to_list

This function converts the 'Tags' column from a set to a list.
- **Input:** `df` (DataFrame) - The DataFrame containing the data.
- **Output:** The DataFrame with the 'Tags' column converted to a list.

### normalize_parameter_names

This function normalizes the parameter names in a step.
- **Input:** `step` (str) - The step to normalize.
- **Output:** The normalized step.

### merge_semantically_similar_steps

This function merges semantically similar steps in the DataFrame.
- **Input:** `df` (DataFrame) - The DataFrame containing the data.
- **Output:** The DataFrame with semantically similar steps merged.

### extract_all_tags

This function extracts all the tags for all the available BDD steps.
- **Input:** `df` (DataFrame) - The DataFrame containing the data.
- **Output:** A set containing all the tags.

## Dependencies Used and Their Descriptions

### Libraries and Modules

- `functools`: Provides higher-order functions that act on or return other functions.
- `os`: Provides a way of using operating system-dependent functionality like reading or writing to the file system.
- `re`: Provides regular expression matching operations.
- `string`: Provides a collection of string operations.
- `typing`: Provides runtime support for type hints.
- `numpy`: A fundamental package for scientific computing with Python.
- `pandas`: A powerful data analysis and manipulation library for Python.
- `parse_feature` and `ScenarioTemplate` from `.parser`: Custom modules for parsing feature files and representing scenarios.

## Functional Flow

The functional flow of `bdd_parser.py` involves the following steps:

1. **Directory Traversal:** The `get_all_scenarios_from_directory` function traverses the specified directory to identify feature files.
2. **Scenario Extraction:** For each identified feature file, the `parse_feature` function is called to extract scenarios.
3. **DataFrame Creation:** The extracted scenarios are processed to create pandas DataFrames using functions like `get_initial_steps_data_frame` and `create_scenarios_data_frame`.
4. **Data Processing:** Various functions like `get_first_instance`, `get_keyword`, `get_count`, and `get_final_data_frame` are used to process the DataFrames and extract meaningful information.
5. **Tag Filtering:** The `filter_tags` function filters the DataFrame based on specified tags.
6. **Normalization and Merging:** Functions like `normalize_parameter_names` and `merge_semantically_similar_steps` are used to normalize and merge steps.
7. **Tag Extraction:** The `extract_all_tags` function extracts all the tags from the DataFrame.

## Endpoints Used/Created

There are no explicit endpoints defined or used within `bdd_parser.py`. The functionality is focused on processing local feature files and scenarios.