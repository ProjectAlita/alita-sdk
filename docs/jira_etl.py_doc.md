# jira_etl.py

**Path:** `src/alita_sdk/community/eda/jira/jira_data_extractor/jira_etl.py`

## Data Flow

The data flow within the `jira_etl.py` file is centered around extracting data from Jira and loading it into a SQL database. The process begins with reading configuration parameters from local files, which include details about Jira projects and cloud services. The data extraction is triggered by the `run_issues_pipeline` and `run_sprints_pipeline` methods, which handle issues and sprints data respectively.

Data is extracted from Jira using the `connect_to_jira` function, which establishes a connection to the Jira instance. The extracted data is then transformed into pandas DataFrames for further processing. For issues, the `_extract_updated_issues` method is used to fetch updated issues based on the last updated date stored in the database. The data is then enriched with additional fields such as `data_extraction_date` before being written to the database.

Intermediate variables such as `df_issues` and `df_sprints_all` are used to store the extracted data temporarily. The data is then written to the database using the `DBEngine` class, which handles database operations. Deleted issues are identified and removed from the database to ensure data consistency.

```python
# Example of data extraction and transformation
jira = connect_to_jira(self.cloud_provider, self.cloud_conf_path)
jira_issues = JiraIssuesUpdate(jira, project,
                               (self.jira_extraction_conf[project]['closed_issues_based_on'],
                                self.jira_extraction_conf[project]['closed_status']),
                               self.jira_extraction_conf[project]['defects_name'])
df_issues, _ = jira_issues.extract_issues_from_jira_and_transform(custom_fields, tuple([date_after] * 3))
logging.info('New data from Jira project %s has been extracted.', project)
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `ExtractJiraIssuesToDb` class with the paths to the configuration files and the cloud provider. It reads the configuration parameters for Jira and the cloud provider using the `Config.read_config` method.

### `run_issues_pipeline`

This method orchestrates the extraction and loading of issues data from Jira to the database. It iterates over the projects specified in the configuration, extracts updated issues, and writes them to the database. It also handles the identification and removal of deleted issues.

### `run_sprints_pipeline`

This method handles the extraction and loading of sprints data from Jira to the database. It iterates over the projects specified in the configuration, extracts sprints data, and writes it to the database.

### `_extract_updated_issues`

This private method extracts updated issues from Jira for a specific project. It uses the `JiraIssuesUpdate` class to fetch and transform the issues data based on the last updated date.

### `_define_date_for_jql_query`

This private method determines the date for the JQL query to extract issues updated after a specific date. It retrieves the last updated date from the database or uses the date from the configuration file if no issues are found in the database.

### `_construct_delete_or_move_query`

This private method constructs an SQL query to delete issues data from the database for issues that no longer exist in Jira or are present in the newly extracted data.

### `_construct_string`

This static method constructs a string from a list of values, which is used in SQL queries.

### `_define_deleted_issues`

This private method identifies issues that have been deleted from Jira by comparing the issues in the database with the existing issues in Jira.

### `_define_issues_intersection`

This static method identifies issues that are present in both the database and the newly extracted data from Jira.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging information, warnings, and errors during the execution of the script.

### `Optional`

Used for type hinting to indicate that a variable can be of a specified type or `None`.

### `datetime`

Used to handle date and time operations, such as getting the current UTC time.

### `pandas`

Used for data manipulation and analysis, particularly for handling data in DataFrame format.

### `DBEngine`

A custom class used for database operations, such as reading from and writing to the database.

### `Config`

A custom class used to read configuration parameters from local files.

### `connect_to_jira`

A custom function used to establish a connection to the Jira instance.

### `JiraBasic`, `JiraIssuesUpdate`, `JiraSprints`

Custom classes used to interact with Jira and extract issues and sprints data.

## Functional Flow

1. **Initialization**: The `ExtractJiraIssuesToDb` class is initialized with the paths to the configuration files and the cloud provider.
2. **Run Issues Pipeline**: The `run_issues_pipeline` method is called to extract and load issues data from Jira to the database.
3. **Extract Updated Issues**: The `_extract_updated_issues` method is used to fetch updated issues from Jira based on the last updated date.
4. **Write to Database**: The extracted issues data is written to the database using the `DBEngine` class.
5. **Identify Deleted Issues**: The `_define_deleted_issues` method is used to identify issues that have been deleted from Jira.
6. **Run Sprints Pipeline**: The `run_sprints_pipeline` method is called to extract and load sprints data from Jira to the database.
7. **Extract Sprints Data**: The `JiraSprints` class is used to fetch sprints data from Jira.
8. **Write to Database**: The extracted sprints data is written to the database using the `DBEngine` class.

## Endpoints Used/Created

No explicit endpoints are defined or called within the `jira_etl.py` file. The script primarily interacts with Jira and the database through custom classes and functions.