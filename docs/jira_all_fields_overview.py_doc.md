# jira_all_fields_overview.py

**Path:** `src/alita_sdk/community/eda/jira/jira_all_fields_overview.py`

## Data Flow

The data flow within the `jira_all_fields_overview.py` file begins with the extraction of all fields from Jira for one or more projects. The data is then filtered to remove columns with all `None` values, and statistics are calculated on the fields' usage. The data originates from the Jira instance, is transformed through various filtering and renaming operations, and finally, the results are stored in data frames and written to CSV files.

For example, in the `jira_all_fields_overview` function:

```python
all_fields_data = jiraBasic.extract_all_fields(updated_after)
all_fields_data = _rename_columns(all_fields_data)
columns_filtered = _filter_columns(all_fields_data)
filtered_columns_data = all_fields_data.filter(items=columns_filtered)
```

Here, `all_fields_data` is extracted from Jira, renamed, filtered, and then the filtered data is stored in `filtered_columns_data`.

## Functions Descriptions

### jira_all_fields_overview

This function extracts all fields from Jira, filters out columns with all `None` values, and calculates statistics on the fields' usage. It takes `projects` and `updated_after` as parameters, and an optional `jira` parameter. It returns two data frames: `overall_stat` and `issue_types_stat`.

### _rename_columns

This function renames columns with issues' IDs and keys and removes 'fields' from the beginning of columns' names. It takes a data frame `df_issues` as input and returns the renamed data frame.

### _get_names_pairs

This function creates a dictionary with fields' IDs and names. It takes a Jira connection and a data frame `df_issues` as inputs and returns a dictionary `name_pairs`.

### _filter_columns

This function filters out columns with all `None` values and certain patterns. It takes a data frame `df_issues` as input and returns a list of filtered columns.

### _describe_fields_values

This function calculates statistics for all Jira fields' usage for the requested projects. It takes a data frame `issues_data` as input and returns a data frame `df_count`.

### _describe_fields_values_per_issue_type

This function calculates statistics for all Jira fields' usage for the requested projects per issue type. It takes a data frame `issues_data` as input and returns a data frame `df_count`.

### _count_values

This function groups a data frame by projects' names and counts values in other columns. It takes a data frame `issues_data` as input and returns a data frame `df_count`.

### _sort_by_sum_across_columns

This function sorts a data frame by a temporarily added column with the sum of values across all columns. It takes a data frame `df_data` as input and returns the sorted data frame `df_count`.

## Dependencies Used and Their Descriptions

### pandas

The `pandas` library is used for data manipulation and analysis. It provides data structures and functions needed to manipulate structured data seamlessly.

### jira

The `jira` library is used to interact with the Jira API. It allows the script to connect to Jira, extract fields, and perform various operations on Jira data.

### re

The `re` module provides support for regular expressions, which are used for string matching and manipulation within the script.

### warnings

The `warnings` module is used to manage warnings that occur during the execution of the script.

### logging

The `logging` module is used to log messages that provide insights into the script's execution flow and any issues that arise.

### connect_to_jira

This function from the `jira_connect` module is used to establish a connection to the Jira instance.

### JiraFields

This class from the `jira_fields` module is used to interact with Jira fields and retrieve their details.

### JiraBasic

This class from the `jira_basic` module is used to perform basic operations on Jira data, such as extracting all fields.

### OUTPUT_FOLDER, OUTPUT_COUNT_PATH

These constants from the `constants` module define the output folder and path for storing the results.

## Functional Flow

The functional flow of the `jira_all_fields_overview.py` file starts with the `jira_all_fields_overview` function, which extracts all fields from Jira, filters the data, and calculates statistics. The helper functions `_rename_columns`, `_get_names_pairs`, `_filter_columns`, `_describe_fields_values`, `_describe_fields_values_per_issue_type`, `_count_values`, and `_sort_by_sum_across_columns` are called within this function to perform specific tasks.

For example, the `_filter_columns` function is called to filter out unnecessary columns:

```python
columns_filtered = _filter_columns(all_fields_data)
filtered_columns_data = all_fields_data.filter(items=columns_filtered)
```

## Endpoints Used/Created

The script interacts with the Jira API to extract fields and perform operations on Jira data. The `connect_to_jira` function establishes a connection to the Jira instance, and the `JiraBasic` and `JiraFields` classes use this connection to interact with Jira.