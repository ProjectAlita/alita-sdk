# jira_basic.py

**Path:** `src/alita_sdk/community/eda/jira/jira_basic.py`

## Data Flow

The data flow within the `jira_basic.py` file revolves around interacting with the Jira API to fetch and process issue data. The data originates from the Jira server, where it is queried using JQL (Jira Query Language) and then processed within the code. The primary data elements are issue IDs and their associated fields, which are retrieved and transformed into a pandas DataFrame for further manipulation.

For example, in the `get_issues_ids` method, the data flow can be traced as follows:

1. The method `get_issues_ids` is called with a date parameter `updated_after`.
2. This method calls `extract_all_fields` with the specified date and the field 'key'.
3. `extract_all_fields` constructs a JQL query and calls `_extract_fields_values` to execute the query and fetch the data.
4. `_extract_fields_values` interacts with the Jira API, retrieves the data, and normalizes it into a DataFrame.
5. The DataFrame is returned to `extract_all_fields`, which then extracts the 'key' column and returns it as a list of issue IDs.

```python
# Example of data flow in get_issues_ids method
fields = 'key'
df_issues = self.extract_all_fields(updated_after, fields)
if df_issues.empty:
    return None
return df_issues['key'].tolist()
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `JiraBasic` class with an instance of the JIRA class and a string of project keys. It ensures that the projects parameter is provided, raising a ValueError if it is not.

**Parameters:**
- `jira`: An instance of the JIRA class.
- `projects`: A string containing one or more project keys separated by commas.

### `get_issues_ids`

The `get_issues_ids` method retrieves a list of issue IDs that were updated after a specified date. It calls `extract_all_fields` to fetch the data and then extracts the 'key' field from the resulting DataFrame.

**Parameters:**
- `updated_after`: A string representing the date after which issues were updated.

**Returns:**
- A list of issue IDs or None if no issues are found.

### `extract_all_fields`

The `extract_all_fields` method constructs a JQL query to fetch issues updated after a specified date and with specified fields. It calls `_extract_fields_values` to execute the query and retrieve the data.

**Parameters:**
- `updated_after`: A string representing the date after which issues were updated.
- `fields`: A string of fields to retrieve (optional).
- `block_size`: The number of issues to fetch per block (default is 100).
- `block_num`: The block number to start fetching from (default is 0).

**Returns:**
- A pandas DataFrame containing the retrieved issues.

### `_extract_fields_values`

The `_extract_fields_values` method executes the JQL query and retrieves the issues from Jira. It handles pagination and logging, and normalizes the retrieved data into a pandas DataFrame.

**Parameters:**
- `parameters`: A dictionary of parameters for the JQL query.
- `block_size`: The number of issues to fetch per block (default is 100).
- `block_num`: The block number to start fetching from (default is 0).

**Returns:**
- A pandas DataFrame containing the retrieved issues or None if the Jira instance is not available.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging information and errors during the execution of the code. It helps in tracking the progress and debugging issues.

### `Optional`

The `Optional` type hint from the `typing` module is used to indicate that a function can return a value of the specified type or None.

### `pandas as pd`

The `pandas` library is used for data manipulation and analysis. In this file, it is used to create and manipulate DataFrames that store the retrieved issue data.

### `JIRAError, JIRA`

These classes from the `jira` module are used to interact with the Jira API. `JIRA` is the main class for connecting to Jira, and `JIRAError` is used for handling errors that occur during API interactions.

## Functional Flow

The functional flow of the `jira_basic.py` file involves initializing the `JiraBasic` class with the necessary parameters and then using its methods to fetch and process issue data from Jira. The sequence of operations is as follows:

1. An instance of the `JiraBasic` class is created with the Jira instance and project keys.
2. The `get_issues_ids` method is called with a date parameter to retrieve issue IDs updated after that date.
3. The `extract_all_fields` method constructs a JQL query and calls `_extract_fields_values` to fetch the data.
4. The `_extract_fields_values` method executes the query, handles pagination, and normalizes the data into a DataFrame.
5. The DataFrame is returned to `extract_all_fields`, which then extracts the 'key' column and returns it as a list of issue IDs.

## Endpoints Used/Created

The `jira_basic.py` file interacts with the Jira API to fetch issue data. The main endpoint used is the `search_issues` method of the `JIRA` class, which executes a JQL query and retrieves the matching issues.

**Endpoint:**
- `search_issues`

**Request Format:**
- The request is constructed using a JQL query string and additional parameters such as `startAt` and `maxResults`.

**Response Format:**
- The response is a JSON object containing the retrieved issues.

**Example:**

```python
parameters = {
    'jql_str': f'project IN ({self.projects}) AND updated >= {updated_after}',
    'startAt': block_num * block_size,
    'maxResults': block_size,
    'json_result': True,
}
jira_search = self.jira.search_issues(**parameters).get('issues')
```