# jira_issues.py

**Path:** `src/alita_sdk/community/eda/jira/jira_issues.py`

## Data Flow

The data flow within the `jira_issues.py` file revolves around extracting and transforming issues data from Jira. The data originates from Jira through API calls made using the `JIRA` class instance. The data is then processed and transformed into a pandas DataFrame. The key steps in the data flow include extracting issues, merging issue history, calculating time spent in each status, and adding release information. The data is temporarily stored in intermediate variables such as `data_jira_fin`, `df_versions`, and `df_time_in_status` before being returned as a tuple of DataFrames.

Example:
```python
# Extract data
        data_jira_fin, df_versions = self.extract_issues_from_jira(custom_fields, dates)
        # Merge with calculated time that every issue spends in every status
        df_time_in_status = lead_time_distribution_jira(data_jira_fin)
        data_jira = merge_issues_and_history(data_jira_fin, df_time_in_status).reset_index(drop=True)
```
In this example, `data_jira_fin` and `df_versions` are extracted from Jira, and `df_time_in_status` is calculated and merged with `data_jira_fin` to produce the final `data_jira` DataFrame.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `JiraIssues` class with parameters such as `jira`, `projects`, `closed_params`, and `defects_name`. It sets up the instance variables and validates the `closed_issues_based_on` parameter.

### `extract_issues_from_jira_and_transform`

This function extracts issues from Jira and transforms the data by adding calculated time spent in each status and release information. It returns a tuple of DataFrames containing the transformed data and a mapping of statuses.

### `extract_issues_from_jira`

This function extracts default and custom fields values from Jira and saves the results to CSV files. It constructs JQL queries and requests data from Jira, handling both closed and open issues.

### `_request_data_from_jira`

This function requests data from Jira using the provided JQL query and fields. It handles errors and retries the request if necessary.

### `_loop_jira_search`

This function performs a paginated search for issues in Jira using the provided JQL query and fields. It uses a thread pool to parallelize the data extraction process.

### `_get_data_jira_one_issue`

This function extracts data for a single Jira issue, including its changelog and custom fields values.

### `_get_defects_data`

This function extracts defects data from the Jira issues that were created after a specified date.

### `_add_request_type`

This function adds a new column to the DataFrame with issues data, indicating the request type (e.g., closed, open, defect).

### `_construct_jql_request`

This function constructs a JQL query based on the input parameters and the criteria for closed issues.

### `_list_jira_fields`

This function creates a string containing all the fields that need to be extracted from Jira.

### `_add_changelog`

This function adds the changelog data to a Jira issue.

### `_get_all_fields_values_for_issue`

This function extracts values for all requested fields (standard and custom) for a single Jira issue.

### `_get_default_issues_fields`

This function extracts standard Jira issue attributes for a single issue.

### `_concat_latest_versions`

This function concatenates the latest fix version data for a single issue with the DataFrame containing all latest fix versions.

### `_get_linked_issues`

This function extracts linked issues for a single Jira issue and returns them as a concatenated string.

### `_get_latest_fix_version_for_issue`

This function extracts the latest release data for a single Jira issue.

### `_get_custom_fields_values`

This function extracts custom fields values for a single Jira issue.

### `_get_issues_changelog`

This function extracts the changelog for a single Jira issue.

## Dependencies Used and Their Descriptions

### `concurrent.futures`

Used for parallelizing the data extraction process using a thread pool.

### `warnings`

Used to filter out warnings.

### `logging`

Used for logging information and errors.

### `pandas`

Used for creating and manipulating DataFrames.

### `retry`

Used for retrying the data extraction process in case of errors.

### `jira`

Used for interacting with the Jira API.

### `utils.convert_to_datetime`

Used for converting strings to datetime objects.

### `utils.transform_jira`

Contains various functions for transforming Jira data, such as `lead_time_distribution_jira`, `merge_issues_and_history`, and `add_releases_info`.

### `utils.circuit_breaker`

Used for implementing a circuit breaker pattern to handle errors and retries.

### `jira_fields`

Contains the `JiraFields` class for handling custom fields in Jira.

### `jira_basic`

Contains the `JiraBasic` class, which `JiraIssues` inherits from.

## Functional Flow

1. **Initialization**: The `JiraIssues` class is initialized with the necessary parameters.
2. **Data Extraction**: The `extract_issues_from_jira_and_transform` method is called to extract and transform issues data from Jira.
3. **Data Transformation**: The extracted data is transformed by adding calculated time spent in each status and release information.
4. **Data Merging**: The transformed data is merged with issue history and returned as a tuple of DataFrames.

## Endpoints Used/Created

### Jira API

The `JiraIssues` class interacts with the Jira API to extract issues data. The specific endpoints and JQL queries used depend on the input parameters and the criteria for closed issues.
