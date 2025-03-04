# jira_etl.py

**Path:** `src/alita_sdk/community/eda/jira/jira_data_extractor/jira_etl.py`

## Data Flow

The data flow within the `jira_etl.py` file is centered around extracting data from Jira and uploading it to a SQL database. The process begins with reading configuration parameters from local files, which include details about Jira projects and cloud services. The data extraction is triggered by the `run_issues_pipeline` and `run_sprints_pipeline` methods. These methods initiate connections to Jira and the database, extract updated issues and sprints data, and then upload this data to the database. Intermediate variables such as `data_extraction_date`, `df_issues`, and `df_sprints_all` are used to temporarily store data during the extraction and transformation process. The data flow is sequential, with each step depending on the successful completion of the previous one.

Example:
```python
# Extract issues from Jira for one project
jira = connect_to_jira(self.cloud_provider, self.cloud_conf_path)
jira_issues = JiraIssuesUpdate(jira, project,
                               (self.jira_extraction_conf[project]['closed_issues_based_on'],
                                self.jira_extraction_conf[project]['closed_status']),
                               self.jira_extraction_conf[project]['defects_name'])
df_issues, _ = jira_issues.extract_issues_from_jira_and_transform(custom_fields, tuple([date_after] * 3))
```
In this example, data is extracted from Jira and stored in the `df_issues` DataFrame.

## Functions Descriptions

### `__init__`
The `__init__` method initializes the `ExtractJiraIssuesToDb` class with paths to configuration files and the cloud provider. It reads the configuration parameters for Jira and the cloud provider.

### `run_issues_pipeline`
This method runs the pipeline to extract issues data from Jira and save it to the database. It iterates over the projects specified in the configuration, extracts updated issues, and uploads them to the database.

### `run_sprints_pipeline`
This method runs the pipeline to extract sprints data from Jira and save it to the database. It iterates over the projects specified in the configuration, extracts sprints data, and uploads it to the database.

### `_extract_updated_issues`
This private method extracts issues from Jira for a specific project that were updated on or after the latest update date in the database. It returns a DataFrame containing the extracted issues.

### `_define_date_for_jql_query`
This private method defines the date for issues extraction based on the latest update date in the database or the date specified in the configuration file.

### `_construct_delete_or_move_query`
This private method constructs an SQL query to delete issues data from the database for issues that no longer exist in Jira or are present in the newly extracted data.

### `_construct_string`
This static method constructs a string from a list of values, used in SQL queries.

### `_define_deleted_issues`
This private method defines issues that have been deleted from Jira by comparing the existing issues in the database with those in Jira.

### `_define_issues_intersection`
This static method defines issues that are both in the database and the newly extracted data from Jira.

## Dependencies Used and Their Descriptions

### `logging`
Used for logging information, warnings, and errors during the execution of the script.

### `Optional`
Used for type hinting optional parameters.

### `datetime`
Used to handle date and time operations, such as getting the current date and time.

### `pandas`
Used for data manipulation and analysis, particularly for handling data in DataFrame structures.

### `DBEngine`
A custom module for interacting with the SQL database, handling connections, and executing queries.

### `Config`
A custom module for reading configuration files and extracting parameters.

### `connect_to_jira`
A custom module for establishing a connection to Jira.

### `JiraBasic`, `JiraIssuesUpdate`, `JiraSprints`
Custom modules for interacting with Jira, extracting issues, and sprints data.

## Functional Flow

1. **Initialization**: The `ExtractJiraIssuesToDb` class is initialized with configuration paths and the cloud provider.
2. **Run Issues Pipeline**: The `run_issues_pipeline` method is called to extract and upload issues data.
3. **Run Sprints Pipeline**: The `run_sprints_pipeline` method is called to extract and upload sprints data.
4. **Extract Updated Issues**: The `_extract_updated_issues` method is used to get updated issues from Jira.
5. **Define Date for JQL Query**: The `_define_date_for_jql_query` method determines the date for extracting issues.
6. **Construct Delete or Move Query**: The `_construct_delete_or_move_query` method creates an SQL query for deleting issues.
7. **Define Deleted Issues**: The `_define_deleted_issues` method identifies issues deleted from Jira.
8. **Define Issues Intersection**: The `_define_issues_intersection` method finds issues present in both the database and the newly extracted data.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file. The interactions with Jira and the database are handled through custom modules and classes.