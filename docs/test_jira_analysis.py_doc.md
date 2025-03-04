# test_jira_analysis.py

**Path:** `src/tests/test_jira_analysis.py`

## Data Flow

The data flow within `test_jira_analysis.py` revolves around the interaction between the test functions and the `eda_api_wrapper` fixture. The fixture initializes the `EDAApiWrapper` object, which is used by the test functions to interact with the JIRA API. The data originates from environment variables, which are loaded using the `dotenv` library. These variables include credentials and configuration settings for connecting to the JIRA server and the Alita client. The `eda_api_wrapper` fixture creates instances of `AlitaClient`, `ArtifactWrapper`, and connects to JIRA using these credentials. The test functions then use this fixture to call methods on the `EDAApiWrapper` object, passing in arguments that are also derived from environment variables. The results of these method calls are then asserted to ensure they contain the expected data.

Example:
```python
@pytest.fixture
def eda_api_wrapper():
    client = AlitaClient(
        base_url=os.getenv("DEPLOYMENT_URL"),
        project_id=int(os.getenv("PROJECT_ID")),
        auth_token=os.getenv("API_KEY")
    )
    jira = connect_to_jira(
        jira_base_url=os.getenv("JIRA_SERVER"),
        jira_username=os.getenv("JIRA_USER"),
        jira_token=os.getenv("JIRA_TOKEN"),
        jira_api_key=os.getenv("JIRA_API_KEY"),
        jira_verify_ssl=False
    )
    artifacts_wrapper = ArtifactWrapper(client=client, bucket=os.getenv("ARTIFACT_BUCKET_PATH"))
    
    check_schema(artifacts_wrapper)
    eda_wrapper = EDAApiWrapper(
        artifacts_wrapper=artifacts_wrapper,
        jira=jira,
        closed_status=os.getenv("JIRA_CLOSED_STATUS"),
        defects_name=os.getenv("JIRA_DEFECTS_NAME"),
        custom_fields={}
    )
    check_schema(eda_wrapper)
    return eda_wrapper
```
This fixture sets up the necessary objects for interacting with the JIRA API and returns an instance of `EDAApiWrapper`.

## Functions Descriptions

### `eda_api_wrapper`

This fixture function initializes and returns an instance of `EDAApiWrapper`. It sets up the `AlitaClient` with the base URL, project ID, and API key from environment variables. It then connects to JIRA using the `connect_to_jira` function, passing in the JIRA server URL, username, token, API key, and SSL verification flag. An `ArtifactWrapper` is created with the `AlitaClient` instance and the artifact bucket path from environment variables. The `check_schema` function is called on the `ArtifactWrapper` and the `EDAApiWrapper` to ensure the schemas are correct. Finally, the `EDAApiWrapper` is returned.

### `test_get_number_of_all_issues`

This test function uses the `eda_api_wrapper` fixture to get an instance of `EDAApiWrapper`. It creates an instance of `GetJiraFieldsArgs` with the project keys and after date from environment variables. It then calls the `get_number_off_all_issues` method on the `EDAApiWrapper` instance, passing in the project keys and after date. The result is asserted to ensure it contains the expected keys.

Example:
```python
def test_get_number_of_all_issues(eda_api_wrapper):
    args = GetJiraFieldsArgs(project_keys=os.getenv("JIRA_PROJECT"), after_date="2025-01-01")
    result = eda_api_wrapper.get_number_off_all_issues(args.project_keys, args.after_date)
    assert "projects" in result
    assert "projects_summary" in result
```
This test ensures that the `get_number_off_all_issues` method returns the expected data structure.

### `test_get_all_jira_fields`

This test function is similar to `test_get_number_of_all_issues`. It creates an instance of `GetJiraFieldsArgs` with the project keys and after date from environment variables. It then calls the `get_all_jira_fields` method on the `EDAApiWrapper` instance, passing in the project keys and after date. The result is asserted to ensure it contains the expected keys.

### `test_get_jira_issues`

This test function creates an instance of `GetJiraIssuesArgs` with the project keys, closed issues based on, resolved after, updated after, created after, and add filter from environment variables. It then calls the `get_jira_issues` method on the `EDAApiWrapper` instance, passing in these arguments. The result is asserted to ensure it contains the expected success message.

## Dependencies Used and Their Descriptions

### `os`

Used to access environment variables for configuration settings.

### `pytest`

Used for writing and running test functions.

### `dotenv`

Used to load environment variables from a `.env` file.

### `EDAApiWrapper`, `GetJiraFieldsArgs`, `GetJiraIssuesArgs`

Imported from `alita_sdk.community.eda.jiratookit.api_wrapper`. These are used to interact with the JIRA API and pass arguments to the methods of `EDAApiWrapper`.

### `AlitaClient`

Imported from `alita_sdk.clients.client`. This is used to create a client for interacting with the Alita API.

### `ArtifactWrapper`

Imported from `alita_sdk.tools.artifact`. This is used to wrap the Alita client and interact with artifacts.

### `connect_to_jira`

Imported from `alita_sdk.community.eda.jira.jira_connect`. This is used to connect to the JIRA server.

### `check_schema`

Imported from `alita_sdk.community.utils`. This is used to check the schema of the `ArtifactWrapper` and `EDAApiWrapper`.

## Functional Flow

1. **Load Environment Variables:** The `.env` file is loaded using `load_dotenv()`.
2. **Initialize `eda_api_wrapper` Fixture:** The `eda_api_wrapper` fixture is defined to set up the necessary objects for interacting with the JIRA API.
3. **Run Test Functions:** The test functions `test_get_number_of_all_issues`, `test_get_all_jira_fields`, and `test_get_jira_issues` are executed. Each test function uses the `eda_api_wrapper` fixture to get an instance of `EDAApiWrapper` and calls its methods with the appropriate arguments.
4. **Assertions:** The results of the method calls are asserted to ensure they contain the expected data.

## Endpoints Used/Created

### JIRA API Endpoints

The `EDAApiWrapper` interacts with various JIRA API endpoints to fetch data about issues, fields, and other project-related information. The specific endpoints are not detailed in the provided code, but they are accessed through the methods of `EDAApiWrapper` using the arguments passed in the test functions.
