# jira_projects_overview.py

**Path:** `src/alita_sdk/community/eda/jira/jira_projects_overview.py`

## Data Flow

The data flow within the `jira_projects_overview.py` file begins with the connection to a Jira instance and the retrieval of project data. The primary function, `jira_projects_overview`, takes three parameters: `after_date`, `project_keys`, and `jira`. It first connects to Jira and retrieves a DataFrame of projects using the `connect_to_jira_and_print_projects` function. The `project_keys` string is then processed into a list of individual project keys. This list is filtered to include only those projects that are available in the retrieved DataFrame. The function then calls `jira_get_issues_count_for_projects` to get the count of issues for each project after the specified date. The resulting DataFrame is merged with the initial project DataFrame, sorted, and saved to a CSV file. The final DataFrame is returned as the output.

Example:
```python
# Example of data transformation in jira_projects_overview function
jira, df_prj = connect_to_jira_and_print_projects(jira)
projects_list = project_keys.strip().replace(" ", "").split(',')
available_projects = df_prj['key'].tolist()
list_to_analyze = []
for project in projects_list:
    if project not in available_projects:
        logging.warning(f"Project {project} is not available in the list of accessible projects.")
    else:
        list_to_analyze.append(project)
```

## Functions Descriptions

### jira_projects_overview

This function retrieves the list of projects a user has access to and merges them with the count of issues for each project. It takes three parameters: `after_date` (a string representing the date after which issues are counted), `project_keys` (a string of comma-separated project keys), and `jira` (an instance of the JIRA class). The function connects to Jira, retrieves project data, filters the projects based on availability, gets the issue counts, merges the data, sorts it, and saves it to a CSV file.

### jira_get_issues_count_for_projects

This function loops through each project in the provided list and gets the count of issues using a JQL request. It takes three parameters: `jira` (an instance of the JIRA class), `projects_to_analyze` (a list of project keys), and `after_date` (a string representing the date after which issues are counted). The function constructs a JQL query for each project, retrieves the issue count, and returns a DataFrame with the project keys and issue counts.

### jira_get_issues_count

This function requests issues for a single project that were updated after a specified date and returns the count of these issues. It takes four parameters: `jira` (an instance of the JIRA class), `jql` (a JQL query string), `block_size` (an integer representing the number of issues to retrieve per request, default is 100), and `block_num` (an integer representing the block number for pagination, default is 0). The function performs a paginated search for issues and returns the total count of issues.

## Dependencies Used and Their Descriptions

### jira

The `jira` module is imported to interact with the Jira instance. It provides the JIRA class and JIRAError exception used for connecting to Jira and handling errors.

### pandas

The `pandas` library is used for data manipulation and analysis. It provides the DataFrame structure used to store and process project and issue data.

### logging

The `logging` module is used for logging warnings and errors during the execution of the functions.

### connect_to_jira_and_print_projects

This function is imported from the `jira_connect` module. It connects to Jira and retrieves a DataFrame of projects.

### OUTPUT_ISSUES_COUNT

This constant is imported from the `constants` module. It specifies the file path for saving the CSV file with the issue counts.

## Functional Flow

1. The `jira_projects_overview` function is called with `after_date`, `project_keys`, and `jira` as parameters.
2. The function connects to Jira and retrieves a DataFrame of projects using `connect_to_jira_and_print_projects`.
3. The `project_keys` string is processed into a list of project keys.
4. The list of project keys is filtered to include only available projects.
5. The `jira_get_issues_count_for_projects` function is called to get the issue counts for the filtered projects.
6. The resulting DataFrame is merged with the initial project DataFrame.
7. The merged DataFrame is sorted by issue count and saved to a CSV file.
8. The final DataFrame is returned as the output.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file. The interaction with Jira is handled through the JIRA class provided by the `jira` module.