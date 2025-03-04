# api_wrapper.py

**Path:** `src/alita_sdk/community/eda/jiratookit/api_wrapper.py`

## Data Flow

The data flow within `api_wrapper.py` revolves around the interaction with Jira through the JIRA API and the manipulation of data using pandas DataFrames. The data originates from Jira, where it is fetched based on specific project keys and date filters. This data is then processed and transformed into various formats, such as CSV files, which are stored using the `ArtifactWrapper` class. The data flow can be summarized as follows:

1. **Data Retrieval:** Data is fetched from Jira using the JIRA API based on project keys and date filters.
2. **Data Processing:** The retrieved data is processed and transformed using pandas DataFrames. This includes filtering, aggregating, and summarizing the data.
3. **Data Storage:** The processed data is stored as CSV files using the `ArtifactWrapper` class.

Example:
```python
project_df = jira_projects_overview(after_date, project_keys=project_keys, jira=self.jira)
with open(OUTPUT_ISSUES_COUNT, 'r') as f:
    self.artifacts_wrapper.create_file('projects_overview.csv', f.read())
```
In this example, data is retrieved from Jira using the `jira_projects_overview` function, processed into a DataFrame (`project_df`), and then stored as a CSV file using the `ArtifactWrapper` class.

## Functions Descriptions

### `get_number_off_all_issues`

This function retrieves the number of all issues for specified projects after a given date. It takes `project_keys` and `after_date` as parameters, fetches the data from Jira, processes it into a DataFrame, and stores the result as a CSV file.

### `get_all_jira_fields`

This function retrieves all Jira fields for specified projects after a given date. It takes `project_keys` and `updated_after` as parameters, fetches the data from Jira, processes it into DataFrames, and stores the results as CSV files.

### `get_jira_issues`

This function extracts Jira issues for specified projects based on various filters. It takes parameters such as `project_keys`, `closed_issues_based_on`, `resolved_after`, `updated_after`, `created_after`, and `add_filter`. It fetches the data from Jira, processes it into DataFrames, and stores the results as CSV files.

### `get_available_tools`

This function returns a list of available tools, including their names, descriptions, argument schemas, and references to the corresponding functions.

### `run`

This function executes a specified tool based on the provided mode. It iterates through the available tools and calls the corresponding function with the given arguments.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging messages within the module.

### `StringIO`

Used for creating in-memory file-like objects for CSV data.

### `pandas`

Used for data manipulation and analysis, particularly for working with DataFrames.

### `pydantic`

Used for data validation and settings management using Python type annotations.

### `ArtifactWrapper`

A custom class used for storing artifacts, such as CSV files.

### `JIRA`

A class from the `jira` library used for interacting with the Jira API.

### `jira_projects_overview`, `jira_all_fields_overview`, `get_all_statuses_list`, `JiraIssues`

Custom functions and classes used for various Jira-related operations, such as fetching project overviews, field overviews, statuses, and issues.

## Functional Flow

1. **Initialization:** The `EDAApiWrapper` class is initialized with instances of `ArtifactWrapper`, `JIRA`, and other necessary parameters.
2. **Tool Execution:** The `run` method is called with a specific mode, which triggers the corresponding function based on the available tools.
3. **Data Retrieval and Processing:** The selected function retrieves data from Jira, processes it using pandas DataFrames, and stores the results as CSV files.
4. **Result Return:** The processed data or a success message is returned as the output of the function.

## Endpoints Used/Created

The `api_wrapper.py` file does not explicitly define or call any endpoints. Instead, it interacts with Jira through the JIRA API using the `JIRA` class from the `jira` library. The specific endpoints and operations are abstracted away by the `JIRA` class and the custom functions used within the module.