# api_wrapper.py

**Path:** `src/alita_sdk/community/eda/jiratookit/api_wrapper.py`

## Data Flow

The data flow within `api_wrapper.py` revolves around the interaction with Jira and the processing of Jira-related data. The data originates from Jira, accessed via the JIRA API, and is processed and transformed within various functions. The data is then stored or returned as output. For instance, in the `get_number_off_all_issues` function, data is fetched from Jira, processed to create a DataFrame, and then written to a CSV file using the `artifacts_wrapper`.

```python
project_df = jira_projects_overview(after_date, project_keys=project_keys, jira=self.jira)
with open(OUTPUT_ISSUES_COUNT, 'r') as f:
    self.artifacts_wrapper.create_file('projects_overview.csv', f.read())
```

In this example, `project_df` holds the data fetched from Jira, which is then written to a CSV file.

## Functions Descriptions

### `get_number_off_all_issues`

This function retrieves the number of issues for specified projects after a given date. It takes `project_keys` and `after_date` as parameters, fetches the data from Jira, processes it into a DataFrame, and writes the result to a CSV file.

### `get_all_jira_fields`

This function retrieves all Jira fields for specified projects after a given date. It takes `project_keys` and `updated_after` as parameters, fetches the data from Jira, processes it, and writes the result to a CSV file.

### `get_jira_issues`

This function extracts Jira issues for specified projects based on various parameters such as `closed_issues_based_on`, `resolved_after`, `updated_after`, `created_after`, and `add_filter`. It processes the data and writes the results to CSV files.

### `get_available_tools`

This function returns a list of available tools, each with its name, description, argument schema, and reference.

### `run`

This function executes a specified tool based on the `mode` parameter. It iterates through the available tools and calls the appropriate one.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information.
- `StringIO`: Used for in-memory file operations.
- `pandas`: Used for data manipulation and analysis.
- `pydantic`: Used for data validation and settings management.
- `ArtifactWrapper`: Custom module for handling artifacts.
- `JIRA`: Used for interacting with the Jira API.
- `jira_projects_overview`, `jira_all_fields_overview`, `get_all_statuses_list`, `JiraIssues`: Custom modules for various Jira-related operations.

## Functional Flow

1. **Initialization**: The `EDAApiWrapper` class is initialized with various parameters such as `artifacts_wrapper`, `jira`, `closed_status`, `defects_name`, and `custom_fields`.
2. **Function Calls**: Functions like `get_number_off_all_issues`, `get_all_jira_fields`, and `get_jira_issues` are called based on the requirements.
3. **Data Processing**: Data is fetched from Jira, processed, and written to CSV files.
4. **Tool Execution**: The `run` function executes the specified tool based on the `mode` parameter.

## Endpoints Used/Created

The file interacts with Jira endpoints via the JIRA API to fetch data related to projects, fields, and issues. The specific endpoints and their interactions are abstracted within the custom modules like `jira_projects_overview`, `jira_all_fields_overview`, and `JiraIssues`.