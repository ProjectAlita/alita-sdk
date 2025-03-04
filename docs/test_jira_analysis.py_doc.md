# test_jira_analysis.py

**Path:** `src/tests/test_jira_analysis.py`

## Data Flow

The data flow in `test_jira_analysis.py` revolves around the interaction between the test functions and the `EDAApiWrapper` class. The data originates from environment variables, which are loaded using the `load_dotenv()` function. These variables include deployment URLs, project IDs, API keys, and Jira credentials. The `eda_api_wrapper` fixture initializes the `EDAApiWrapper` instance using these environment variables. The test functions then use this instance to interact with the Jira API and retrieve data.

For example, in the `test_get_number_of_all_issues` function, the `GetJiraFieldsArgs` class is used to create an argument object with the project keys and a date. This object is passed to the `get_number_off_all_issues` method of the `EDAApiWrapper` instance, which returns the result containing project information.

```python
args = GetJiraFieldsArgs(project_keys=os.getenv("JIRA_PROJECT"), after_date="2025-01-01")
result = eda_api_wrapper.get_number_off_all_issues(args.project_keys, args.after_date)
assert "projects" in result
assert "projects_summary" in result
```

## Functions Descriptions

### `eda_api_wrapper`

This fixture function initializes the `EDAApiWrapper` instance. It creates an `AlitaClient` instance using environment variables for the base URL, project ID, and API key. It also connects to Jira using the `connect_to_jira` function with Jira credentials from environment variables. An `ArtifactWrapper` instance is created with the `AlitaClient` instance and artifact bucket path. The `EDAApiWrapper` instance is then initialized with the `ArtifactWrapper` and Jira instances, along with other parameters from environment variables. The function returns the `EDAApiWrapper` instance.

### `test_get_number_of_all_issues`

This test function checks the `get_number_off_all_issues` method of the `EDAApiWrapper` instance. It creates a `GetJiraFieldsArgs` object with project keys and a date, and passes it to the `get_number_off_all_issues` method. The result is asserted to contain project information.

### `test_get_all_jira_fields`

This test function checks the `get_all_jira_fields` method of the `EDAApiWrapper` instance. It creates a `GetJiraFieldsArgs` object with project keys and a date, and passes it to the `get_all_jira_fields` method. The result is asserted to contain overall statistics and issue types statistics.

### `test_get_jira_issues`

This test function checks the `get_jira_issues` method of the `EDAApiWrapper` instance. It creates a `GetJiraIssuesArgs` object with project keys, closed issues based on a value, and dates for resolved, updated, and created issues. The result is asserted to contain a success message.

## Dependencies Used and Their Descriptions

### `os`

Used to access environment variables.

### `pytest`

Used for writing and running test functions.

### `dotenv`

Used to load environment variables from a `.env` file.

### `EDAApiWrapper`, `GetJiraFieldsArgs`, `GetJiraIssuesArgs`

Imported from `..alita_sdk.community.eda.jiratookit.api_wrapper`. These are used to interact with the Jira API and retrieve data.

### `AlitaClient`

Imported from `..alita_sdk.clients.client`. This is used to create a client instance for interacting with the API.

### `ArtifactWrapper`

Imported from `..alita_sdk.tools.artifact`. This is used to create an artifact wrapper instance for handling artifacts.

### `connect_to_jira`

Imported from `..alita_sdk.community.eda.jira.jira_connect`. This is used to connect to the Jira server.

### `check_schema`

Imported from `..alita_sdk.community.utils`. This is used to check the schema of the data.

## Functional Flow

1. **Load Environment Variables:** The `load_dotenv()` function loads environment variables from a `.env` file.
2. **Initialize `EDAApiWrapper`:** The `eda_api_wrapper` fixture initializes the `EDAApiWrapper` instance using environment variables.
3. **Run Test Functions:** The test functions (`test_get_number_of_all_issues`, `test_get_all_jira_fields`, `test_get_jira_issues`) use the `EDAApiWrapper` instance to interact with the Jira API and retrieve data.
4. **Assertions:** Each test function asserts that the retrieved data contains the expected information.

## Endpoints Used/Created

The `test_jira_analysis.py` file does not explicitly define or call any endpoints. Instead, it uses the `EDAApiWrapper` class to interact with the Jira API. The specific endpoints and their details are abstracted away by the `EDAApiWrapper` class. The test functions focus on verifying the correctness of the data retrieved by the `EDAApiWrapper` methods.