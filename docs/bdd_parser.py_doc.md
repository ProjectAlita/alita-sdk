# bdd_parser.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/bdd_parser.py`

## Data Flow

The data flow within `bdd_parser.py` revolves around processing BDD (Behavior-Driven Development) feature files and extracting scenarios and steps from them. The data originates from feature files located in a specified directory. These files are parsed to extract scenarios, which are then transformed into pandas DataFrames for further analysis and manipulation.

For example, the `get_all_scenarios_from_directory` function reads feature files from a directory and yields scenarios:

```python
import os

def get_all_scenarios_from_directory(directory_name: str):
    for root, dirs, files in os.walk(directory_name):
        for filename in files:
            if filename.endswith('.feature'):
                yield from parse_feature(root, filename).scenarios
            if filename.endswith('.story'):
                yield from parse_feature(root, filename, is_jbehave_story=True).scenarios
```

In this example, the function traverses the directory structure, reads files with `.feature` or `.story` extensions, and uses the `parse_feature` function to extract scenarios. The scenarios are then yielded for further processing.

## Functions Descriptions

1. **get_all_scenarios_from_directory**
   - **Purpose:** Reads feature files from a directory and extracts scenarios.
   - **Inputs:** `directory_name` (str) - The name of the directory to search for feature files.
   - **Outputs:** A generator of `ScenarioTemplate` objects representing the scenarios found in the directory.
   - **Example Usage:**
     ```python
     scenarios = get_all_scenarios_from_directory('path/to/directory')
     for scenario in scenarios:
         print(scenario.name)
     ```

2. **get_initial_steps_data_frame**
   - **Purpose:** Creates a pandas DataFrame containing the initial steps' data from a list of scenarios.
   - **Inputs:** `scenarios` (Generator[ScenarioTemplate, Any, None]) - A list of `ScenarioTemplate` objects.
   - **Outputs:** A pandas DataFrame with columns representing various information about the steps in the scenarios.
   - **Example Usage:**
     ```python
     data_frame = get_initial_steps_data_frame(scenarios)
     ```

3. **create_scenarios_data_frame**
   - **Purpose:** Creates a pandas DataFrame containing the scenarios' data.
   - **Inputs:** `scenarios` (Generator[ScenarioTemplate, Any, None]) - A list of `ScenarioTemplate` objects.
   - **Outputs:** A pandas DataFrame with columns representing various information about the scenarios.
   - **Example Usage:**
     ```python
     data_frame = create_scenarios_data_frame(scenarios)
     ```

4. **get_first_instance**
   - **Purpose:** Returns the first instance of each 'Original Step' group in a DataFrame.
   - **Inputs:** `df` (DataFrame) - A pandas DataFrame containing the data to be processed.
   - **Outputs:** A pandas DataFrame with the first instance of each 'Original Step' group.
   - **Example Usage:**
     ```python
     first_instance_df = get_first_instance(data_frame)
     ```

5. **get_keyword**
   - **Purpose:** Returns the most frequently occurring BDD keyword for each unique original step in a DataFrame.
   - **Inputs:** `df` (DataFrame) - A pandas DataFrame containing the 'BDD Keyword' and 'Original Step' columns.
   - **Outputs:** A new DataFrame with the 'BDD Keyword' column containing the most frequently occurring BDD keyword for each unique original step.
   - **Example Usage:**
     ```python
     keyword_df = get_keyword(data_frame)
     ```

6. **get_count**
   - **Purpose:** Returns the count of each combination of 'Original Step' and 'BDD Keyword' in a DataFrame.
   - **Inputs:** `df` (DataFrame) - A pandas DataFrame containing the data.
   - **Outputs:** A DataFrame with the count of each combination.
   - **Example Usage:**
     ```python
     count_df = get_count(data_frame)
     ```

7. **get_final_data_frame**
   - **Purpose:** Merges three DataFrames and returns a new DataFrame.
   - **Inputs:** `df_first_instance` (DataFrame), `df_keyword` (DataFrame), `df_with_count` (DataFrame) - The DataFrames to be merged.
   - **Outputs:** A merged DataFrame.
   - **Example Usage:**
     ```python
     final_df = get_final_data_frame(first_instance_df, keyword_df, count_df)
     ```

8. **filter_tags**
   - **Purpose:** Filters a DataFrame based on specified tags.
   - **Inputs:** `df` (DataFrame) - A pandas DataFrame containing the data.
   - **Outputs:** The filtered DataFrame.
   - **Example Usage:**
     ```python
     filtered_df = filter_tags(data_frame)
     ```

9. **convert_tags_to_list**
   - **Purpose:** Converts the 'Tags' column from a set to a list.
   - **Inputs:** `df` (DataFrame) - A pandas DataFrame containing the data.
   - **Outputs:** The DataFrame with the 'Tags' column converted to a list.
   - **Example Usage:**
     ```python
     tags_list_df = convert_tags_to_list(data_frame)
     ```

10. **normalize_parameter_names**
    - **Purpose:** Normalizes the parameter names in a step.
    - **Inputs:** `step` (str) - The step to normalize.
    - **Outputs:** The normalized step.
    - **Example Usage:**
      ```python
      normalized_step = normalize_parameter_names(step)
      ```

11. **merge_semantically_similar_steps**
    - **Purpose:** Merges semantically similar steps in a DataFrame.
    - **Inputs:** `df` (DataFrame) - A pandas DataFrame containing the data.
    - **Outputs:** The DataFrame with semantically similar steps merged.
    - **Example Usage:**
      ```python
      merged_df = merge_semantically_similar_steps(data_frame)
      ```

12. **extract_all_tags**
    - **Purpose:** Extracts all the tags for all the available BDD steps.
    - **Inputs:** `df` (DataFrame) - A pandas DataFrame containing the data.
    - **Outputs:** A set containing all the tags.
    - **Example Usage:**
      ```python
      all_tags = extract_all_tags(data_frame)
      ```

## Dependencies Used and Their Descriptions

1. **functools**
   - **Purpose:** Provides higher-order functions that act on or return other functions. Used for reducing operations on sets.
   - **Example Usage:**
     ```python
     from functools import reduce
     reduce(set.union, x)
     ```

2. **os**
   - **Purpose:** Provides a way of using operating system-dependent functionality like reading or writing to the file system.
   - **Example Usage:**
     ```python
     import os
     os.walk(directory_name)
     ```

3. **re**
   - **Purpose:** Provides regular expression matching operations. Used for searching and manipulating strings.
   - **Example Usage:**
     ```python
     import re
     re.sub(r"\".*?\"|'.*?'|<.*?>|'<.*?>'|\"<.*?>\"", "'value'", step)
     ```

4. **string**
   - **Purpose:** Provides a collection of string operations and constants. Used for string manipulation.
   - **Example Usage:**
     ```python
     import string
     string.capwords(step.type)
     ```

5. **typing**
   - **Purpose:** Provides runtime support for type hints. Used for type annotations.
   - **Example Usage:**
     ```python
     from typing import Generator, Any
     ```

6. **numpy**
   - **Purpose:** Provides support for large, multi-dimensional arrays and matrices, along with a collection of mathematical functions to operate on these arrays.
   - **Example Usage:**
     ```python
     import numpy as np
     np.array(list(embeddings_generator))
     ```

7. **pandas**
   - **Purpose:** Provides data structures and data analysis tools. Used for creating and manipulating DataFrames.
   - **Example Usage:**
     ```python
     import pandas as pd
     pd.DataFrame(data_array, columns=['Tags', 'Embeddings Source', 'Original Step', 'BDD Keyword'])
     ```

8. **parser**
   - **Purpose:** Custom module for parsing feature files and extracting scenarios.
   - **Example Usage:**
     ```python
     from .parser import parse_feature, ScenarioTemplate
     parse_feature(root, filename)
     ```

## Functional Flow

The functional flow of `bdd_parser.py` involves the following steps:

1. **Reading Feature Files:** The `get_all_scenarios_from_directory` function reads feature files from a specified directory and extracts scenarios.
2. **Creating DataFrames:** Functions like `get_initial_steps_data_frame` and `create_scenarios_data_frame` create pandas DataFrames from the extracted scenarios.
3. **Processing DataFrames:** Functions like `get_first_instance`, `get_keyword`, and `get_count` process the DataFrames to extract meaningful information.
4. **Merging DataFrames:** The `get_final_data_frame` function merges multiple DataFrames to create a final DataFrame with comprehensive information.
5. **Filtering and Normalizing Data:** Functions like `filter_tags`, `convert_tags_to_list`, and `normalize_parameter_names` filter and normalize the data in the DataFrames.
6. **Merging Similar Steps:** The `merge_semantically_similar_steps` function merges semantically similar steps in the DataFrame.
7. **Extracting Tags:** The `extract_all_tags` function extracts all the tags from the DataFrame.

## Endpoints Used/Created

The `bdd_parser.py` file does not explicitly define or call any endpoints. Its primary focus is on reading feature files from the file system, processing the data, and creating pandas DataFrames for further analysis.
