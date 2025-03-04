# jira_basic.py

**Path:** `src/alita_sdk/community/eda/jira/jira_basic.py`

## Data Flow

The data flow within the `jira_basic.py` file revolves around the interaction with the Jira API to fetch and process issue data. The data originates from the Jira server, accessed via the `JIRA` instance passed to the `JiraBasic` class. The primary data elements are issue IDs and their associated fields, which are retrieved and transformed into a pandas DataFrame for further manipulation.

The journey of data begins with the initialization of the `JiraBasic` class, where the `jira` instance and `projects` string are stored as attributes. When the `get_issues_ids` method is called, it triggers the `extract_all_fields` method to fetch issue data updated after a specified date. This method constructs a JQL query and parameters for the Jira API request, which are then passed to the `_extract_fields_values` method.

In `_extract_fields_values`, the Jira API is queried in blocks, and the results are accumulated in a list. This list is then converted into a pandas DataFrame. The data flow concludes with the DataFrame being returned to the calling method, which extracts and returns the issue IDs.

Example:
```python
class JiraBasic:
    def get_issues_ids(self, updated_after: str) -> Optional[list]:
        fields = 'key'
        df_issues = self.extract_all_fields(updated_after, fields)
        if df_issues.empty:
            return None
        return df_issues['key'].tolist()
```
In this example, the `get_issues_ids` method fetches issue IDs updated after a given date by calling `extract_all_fields` and processing the resulting DataFrame.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `JiraBasic` class with a `jira` instance and a `projects` string. It validates the presence of project keys and raises a `ValueError` if they are not provided.

**Parameters:**
- `jira` (JIRA): An instance of the JIRA class.
- `projects` (str): One or more project keys separated by commas.

### `get_issues_ids`

The `get_issues_ids` method retrieves a list of issue IDs updated after a specified date. It calls `extract_all_fields` to fetch the data and processes the resulting DataFrame to extract the issue keys.

**Parameters:**
- `updated_after` (str): The date after which issues were updated.

**Returns:**
- `Optional[list]`: A list of issue IDs or `None` if no issues are found.

### `extract_all_fields`

The `extract_all_fields` method fetches issues with all Jira fields based on the provided parameters. It constructs a JQL query and calls `_extract_fields_values` to perform the actual data extraction.

**Parameters:**
- `updated_after` (str): The date after which issues were updated.
- `fields` (str, optional): Specific fields to retrieve. Defaults to `None`.
- `block_size` (int, optional): The number of issues to fetch per block. Defaults to `100`.
- `block_num` (int, optional): The block number to start fetching from. Defaults to `0`.

**Returns:**
- `Optional[pd.DataFrame]`: A DataFrame containing the fetched issues or `None` if no issues are found.

### `_extract_fields_values`

The `_extract_fields_values` method performs the actual extraction of issue data from Jira. It handles pagination and accumulates the results into a DataFrame.

**Parameters:**
- `parameters` (dict): The parameters for the Jira API request.
- `block_size` (int, optional): The number of issues to fetch per block. Defaults to `100`.
- `block_num` (int, optional): The block number to start fetching from. Defaults to `0`.

**Returns:**
- `Optional[pd.DataFrame]`: A DataFrame containing the fetched issues or `None` if an error occurs.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging information and errors during the execution of the code. It helps in tracking the progress and debugging issues.

### `Optional` from `typing`

The `Optional` type hint from the `typing` module is used to indicate that a function can return a value of the specified type or `None`.

### `pandas as pd`

The `pandas` library is used for data manipulation and analysis. In this file, it is used to create and manage DataFrames that store issue data fetched from Jira.

### `JIRAError, JIRA` from `jira`

The `JIRA` class is used to interact with the Jira API, and `JIRAError` is used to handle exceptions that occur during API calls.

## Functional Flow

The functional flow of the `jira_basic.py` file starts with the initialization of the `JiraBasic` class, followed by the invocation of its methods to fetch and process issue data from Jira.

1. **Initialization:** An instance of the `JiraBasic` class is created with a `jira` instance and project keys.
2. **Fetching Issue IDs:** The `get_issues_ids` method is called with a date parameter to fetch issue IDs updated after that date.
3. **Extracting All Fields:** The `extract_all_fields` method constructs a JQL query and parameters, then calls `_extract_fields_values` to fetch the data.
4. **Extracting Field Values:** The `_extract_fields_values` method queries the Jira API in blocks, accumulates the results, and converts them into a DataFrame.
5. **Returning Results:** The DataFrame is returned to the calling method, which processes and returns the issue IDs.

## Endpoints Used/Created

The `jira_basic.py` file interacts with the Jira API to fetch issue data. The specific endpoints and their usage are abstracted by the `JIRA` class from the `jira` library. The primary endpoint used is the Jira search API, which is queried with JQL strings to retrieve issues based on specified criteria.

Example:
```python
parameters = {
    'jql_str': f'project IN ({self.projects}) AND updated >= {updated_after}',
    'startAt': block_num * block_size,
    'maxResults': block_size,
    'json_result': True,
}
jira_search = self.jira.search_issues(**parameters).get('issues')
```
In this example, the Jira search API is queried with a JQL string to fetch issues updated after a specified date.