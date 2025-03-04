# jira_projects_overview.py

**Path:** `src/alita_sdk/community/eda/jira/jira_projects_overview.py`

## Data Flow

The data flow within the `jira_projects_overview.py` file begins with the connection to a Jira instance and the retrieval of project data. The primary function, `jira_projects_overview`, takes three parameters: `after_date`, `project_keys`, and `jira`. It first connects to Jira and retrieves a DataFrame of projects using the `connect_to_jira_and_print_projects` function. The `project_keys` string is then processed into a list of individual project keys, which are checked against the available projects in the DataFrame. Projects that are not available are logged as warnings, while available projects are added to a list for further analysis.

Next, the `jira_get_issues_count_for_projects` function is called with the Jira instance, the list of projects to analyze, and the `after_date` parameter. This function constructs a JQL query for each project to count the number of issues updated after the specified date. The results are stored in a dictionary and converted into a DataFrame. This DataFrame is then merged with the initial project DataFrame to include the issues count for each project. The final DataFrame is sorted by the issues count and saved to a CSV file.

Example:
```python
projects_list = project_keys.strip().replace(" ", "").split(',')
# Check if projects_list is present in df_prj['key'].tolist()
available_projects = df_prj['key'].tolist()
list_to_analyze = []
for project in projects_list:
    if project not in available_projects:
        logging.warning(f"Project {project} is not available in the list of accessible projects.")
    else:
        list_to_analyze.append(project)
```
This snippet processes the `project_keys` string into a list and checks each project against the available projects, logging warnings for unavailable projects.

## Functions Descriptions

### `jira_projects_overview`

This function retrieves the list of projects a user has access to and merges it with the issues count for each project. It takes three parameters:
- `after_date` (str): The date after which issues are considered.
- `project_keys` (str): A comma-separated string of project keys.
- `jira` (JIRA): An instance of the JIRA class.

The function connects to Jira, retrieves the project list, processes the project keys, and calls `jira_get_issues_count_for_projects` to get the issues count. The results are merged and saved to a CSV file.

### `jira_get_issues_count_for_projects`

This function loops through each project and gets the issues count using a JQL request. It takes three parameters:
- `jira` (JIRA): An instance of the JIRA class.
- `projects_to_analyze` (list): A list of project keys to analyze.
- `after_date` (str): The date after which issues are considered.

The function constructs a JQL query for each project, retrieves the issues count, and returns a DataFrame with the results.

### `jira_get_issues_count`

This function requests issues for one project that were updated after a set date and returns their number. It takes four parameters:
- `jira` (JIRA): An instance of the JIRA class.
- `jql` (str): The JQL query string.
- `block_size` (int, default=100): The number of issues to retrieve per block.
- `block_num` (int, default=0): The block number to start retrieving issues from.
- `fields` (str, default="key"): The fields to retrieve for each issue.

The function retrieves issues in blocks, counts them, and handles any JIRA errors by logging them.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging warnings and errors throughout the module.

### `pandas as pd`

Used for creating and manipulating DataFrames, which store project and issues data.

### `jira`

The JIRA library is used to connect to a Jira instance and perform JQL queries to retrieve project and issues data.

### `connect_to_jira_and_print_projects`

A function from the `jira_connect` module that connects to Jira and retrieves a list of projects.

### `OUTPUT_ISSUES_COUNT`

A constant from the `constants` module that specifies the output file path for the issues count CSV.

## Functional Flow

1. **Connect to Jira:** The `jira_projects_overview` function connects to Jira and retrieves a DataFrame of projects.
2. **Process Project Keys:** The `project_keys` string is processed into a list, and each project is checked against the available projects.
3. **Get Issues Count:** The `jira_get_issues_count_for_projects` function constructs JQL queries and retrieves the issues count for each project.
4. **Merge Results:** The issues count DataFrame is merged with the project DataFrame, sorted, and saved to a CSV file.

## Endpoints Used/Created

### JIRA API

The module interacts with the JIRA API to retrieve project and issues data using JQL queries. The specific endpoints and methods used are part of the JIRA library's `search_issues` method, which constructs and sends the appropriate API requests based on the JQL queries.