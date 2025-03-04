# jira_all_fields_overview.py

**Path:** `src/alita_sdk/community/eda/jira/jira_all_fields_overview.py`

## Data Flow

The data flow within the `jira_all_fields_overview.py` file is centered around extracting, transforming, and analyzing Jira field data for one or more projects. The process begins with the `jira_all_fields_overview` function, which takes in project identifiers and a date to filter issues updated after this date. If a JIRA connection is not provided, it establishes one using the `connect_to_jira` function. The data is then extracted using the `extract_all_fields` method from the `JiraBasic` class. This raw data undergoes several transformations: renaming columns, filtering out unnecessary columns, and mapping field names to more readable formats. The transformed data is then used to calculate statistics on field usage, both overall and per issue type. The results are logged and returned as data frames.

Example:
```python
all_fields_data = jiraBasic.extract_all_fields(updated_after)
all_fields_data = _rename_columns(all_fields_data)
columns_filtered = _filter_columns(all_fields_data)
filtered_columns_data = all_fields_data.filter(items=columns_filtered)
```
In this snippet, `all_fields_data` is extracted, renamed, filtered, and then further filtered to retain only the necessary columns.

## Functions Descriptions

1. **jira_all_fields_overview**: This is the main function that orchestrates the extraction and analysis of Jira field data. It takes in project identifiers, a date filter, and an optional JIRA connection. It returns two data frames containing statistics on field usage.
   - **Inputs**: `projects` (str), `updated_after` (str), `jira` (JIRA, optional)
   - **Outputs**: `overall_stat` (pd.DataFrame), `issue_types_stat` (pd.DataFrame)

2. **_rename_columns**: Renames columns in the data frame to more readable formats by removing prefixes and renaming specific columns.
   - **Inputs**: `df_issues` (pd.DataFrame)
   - **Outputs**: `df_issues` (pd.DataFrame)

3. **_get_names_pairs**: Creates a dictionary mapping field IDs to their readable names using the JiraFields class.
   - **Inputs**: `jira_connection` (JIRA), `df_issues` (pd.DataFrame)
   - **Outputs**: `name_pairs` (dict)

4. **_filter_columns**: Filters out unnecessary columns from the data frame based on predefined criteria.
   - **Inputs**: `df_issues` (pd.DataFrame)
   - **Outputs**: `columns_filtered` (list)

5. **_describe_fields_values**: Calculates overall statistics for Jira field usage.
   - **Inputs**: `issues_data` (pd.DataFrame)
   - **Outputs**: `df_count` (pd.DataFrame)

6. **_describe_fields_values_per_issue_type**: Calculates statistics for Jira field usage per issue type.
   - **Inputs**: `issues_data` (pd.DataFrame)
   - **Outputs**: `df_count` (pd.DataFrame)

7. **_count_values**: Groups data by project names and counts values in other columns.
   - **Inputs**: `issues_data` (pd.DataFrame)
   - **Outputs**: `df_count` (pd.DataFrame)

8. **_sort_by_sum_across_columns**: Sorts a data frame by the sum of values across all columns.
   - **Inputs**: `df_data` (pd.DataFrame)
   - **Outputs**: `df_count` (pd.DataFrame)

## Dependencies Used and Their Descriptions

1. **re**: Used for regular expression operations, particularly in filtering column names.
2. **warnings**: Used to suppress warnings that might clutter the output.
3. **logging**: Used for logging information, particularly the results of the analysis.
4. **pandas (pd)**: Used extensively for data manipulation and analysis.
5. **jira (JIRA)**: Used to interact with the Jira API for extracting field data.
6. **connect_to_jira**: A custom function from `jira_connect` module to establish a connection to Jira.
7. **JiraFields**: A custom class from `jira_fields` module to handle Jira field operations.
8. **JiraBasic**: A custom class from `jira_basic` module to handle basic Jira operations.
9. **constants**: A custom module containing constants like `OUTPUT_FOLDER` and `OUTPUT_COUNT_PATH` used for file operations.

## Functional Flow

The functional flow of the `jira_all_fields_overview.py` file starts with the `jira_all_fields_overview` function, which is the entry point. This function either uses an existing JIRA connection or establishes a new one. It then extracts all field data for the specified projects and date filter. The data undergoes several transformations, including renaming columns, filtering out unnecessary columns, and mapping field names. The transformed data is then used to calculate statistics on field usage, both overall and per issue type. The results are logged and returned as data frames.

Example:
```python
if jira is None:
    jiraBasic = JiraBasic(connect_to_jira(), projects)
else:
    jiraBasic = JiraBasic(jira, projects)
all_fields_data = jiraBasic.extract_all_fields(updated_after)
```
In this snippet, a JIRA connection is established if not provided, and field data is extracted for further processing.

## Endpoints Used/Created

The `jira_all_fields_overview.py` file interacts with the Jira API to extract field data. The specific endpoints and their interactions are abstracted within the `JiraBasic` and `JiraFields` classes. These classes handle the API calls to Jira, making it easier to extract and manipulate field data without directly dealing with the API endpoints in this file.