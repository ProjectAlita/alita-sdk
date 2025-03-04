# client.py

**Path:** `src/alita_sdk/clients/client.py`

## Data Flow

The data flow within `client.py` revolves around the `AlitaClient` class, which manages interactions with various endpoints of the Alita API. Data originates from the initialization parameters of the `AlitaClient` class, such as `base_url`, `project_id`, and `auth_token`. These parameters are used to construct URLs and headers for API requests. The data is then transformed through various methods that make HTTP requests to these URLs, retrieve responses, and process the data into usable formats. For example, the `prompt` method fetches prompt details, processes the response to extract model settings and messages, and constructs a templated chat message. The data ultimately flows back to the caller in the form of processed responses or objects like `AlitaPrompt` and `AlitaDataSource`.

### Example:
```python
class AlitaClient:
    def __init__(self,
                 base_url: str,
                 project_id: int,
                 auth_token: str,
                 api_extra_headers: Optional[dict] = None,
                 configurations: Optional[list] = None,
                 **kwargs):

        self.base_url = base_url.rstrip('/')
        self.api_path = '/api/v1'
        self.project_id = project_id
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            'X-SECRET': kwargs.get('XSECRET', 'secret')
        }
        if api_extra_headers is not None:
            self.headers.update(api_extra_headers)
        self.predict_url = f"{self.base_url}{self.api_path}/prompt_lib/predict/prompt_lib/{self.project_id}"
        # ... other URL initializations
```
In this snippet, the `__init__` method initializes the client with base URLs and headers, setting up the data flow for subsequent API interactions.

## Functions Descriptions

### `__init__`
The constructor method initializes the `AlitaClient` with essential parameters like `base_url`, `project_id`, and `auth_token`. It sets up various API endpoint URLs and headers required for making requests. Optional parameters like `api_extra_headers` and `configurations` allow for additional customization.

### `prompt`
This method retrieves prompt details from the API, processes the response to extract model settings and messages, and constructs a templated chat message. It can return either a `Jinja2TemplatedChatMessagesTemplate` or an `AlitaPrompt` object based on the `return_tool` flag.

### `get_app_details`
Fetches details of a specific application by its ID. It constructs the URL using the `application_id` and makes a GET request to retrieve the application details.

### `get_list_of_apps`
Retrieves a list of applications with pagination support. It makes repeated GET requests with offset and limit parameters until all applications are fetched.

### `fetch_available_configurations`
Fetches available configurations for the client. It makes a GET request to the configurations URL and returns the response as a list.

### `all_models_and_integrations`
Retrieves all models and integrations available for the client. It makes a GET request to the AI section URL and returns the response.

### `get_app_version_details`
Fetches details of a specific application version by its ID. It makes a PATCH request with configurations to retrieve the application version details.

### `get_integration_details`
Fetches details of a specific integration by its ID. It makes a GET request to the integration details URL and returns the response.

### `unsecret`
Retrieves the value of a secret by its name. It makes a GET request to the secrets URL and returns the secret value.

### `application`
Creates an application instance based on the provided parameters. It supports different runtime environments like `langchain` and `llama`.

### `datasource`
Fetches details of a specific datasource by its ID. It makes a GET request to the datasource URL and returns an `AlitaDataSource` object.

### `assistant`
Creates an assistant instance based on the provided parameters. It returns a `LangChainAssistant` object.

### `artifact`
Creates an artifact instance for a specific bucket. It returns an `Artifact` object.

### `_process_requst`
Processes the response of an HTTP request and returns a dictionary with the response data or an error message based on the status code.

### `bucket_exists`
Checks if a specific bucket exists by making a GET request to the bucket URL and searching for the bucket name in the response.

### `create_bucket`
Creates a new bucket with the specified name and expiration settings. It makes a POST request to the bucket URL with the bucket details.

### `list_artifacts`
Lists all artifacts in a specific bucket by making a GET request to the artifacts URL.

### `create_artifact`
Creates a new artifact in a specific bucket by making a POST request with the artifact data.

### `download_artifact`
Downloads an artifact from a specific bucket by making a GET request to the artifact URL.

### `delete_artifact`
Deletes an artifact from a specific bucket by making a DELETE request to the artifact URL.

### `_prepare_messages`
Prepares a list of messages for a chat by converting them into a format suitable for the API request.

### `_prepare_payload`
Prepares the payload for a chat prediction request by combining messages, model settings, and variables.

### `async_predict`
Makes an asynchronous prediction request to the API and yields the response messages as they are received.

### `predict`
Makes a synchronous prediction request to the API and returns the response messages.

### `rag`
Makes a retrieval-augmented generation (RAG) request to the API with the specified parameters and returns an `AIMessage` object with the response.

### `search`
Makes a search request to the API with the specified parameters and returns an `AIMessage` object with the search results.

## Dependencies Used and Their Descriptions

### `logging`
Used for logging messages and errors within the `AlitaClient` class.

### `requests`
Used for making HTTP requests to the Alita API endpoints.

### `quote` from `urllib.parse`
Used for URL encoding artifact names in the `delete_artifact` method.

### `Dict`, `List`, `Any`, `Optional` from `typing`
Used for type hinting and ensuring type safety within the `AlitaClient` class methods.

### `AIMessage`, `HumanMessage`, `SystemMessage`, `BaseMessage` from `langchain_core.messages`
Used for creating and handling different types of chat messages within the `prompt` and other chat-related methods.

### `LangChainAssistant` from `..langchain.assistant`
Used for creating assistant instances in the `application` and `assistant` methods.

### `AlitaPrompt` from `..prompt`
Used for creating prompt instances in the `prompt` method.

### `AlitaDataSource` from `..datasource`
Used for creating datasource instances in the `datasource` method.

### `Artifact` from `..artifact`
Used for creating artifact instances in the `artifact` method.

### `Jinja2TemplatedChatMessagesTemplate` from `..langchain.chat_message_template`
Used for creating templated chat messages in the `prompt` method.

## Functional Flow

The functional flow of `client.py` begins with the initialization of the `AlitaClient` class, where essential parameters and URLs are set up. The client then interacts with various API endpoints through its methods, making HTTP requests and processing the responses. The flow typically involves constructing the request URL, making the request with appropriate headers, processing the response, and returning the processed data or objects to the caller. Error handling is implemented in methods like `_process_requst` to manage different HTTP status codes and provide meaningful error messages.

### Example:
```python
def get_list_of_apps(self):
    apps = []
    limit = 10
    offset = 0
    total_count = None

    while total_count is None or offset < total_count:
        params = {'offset': offset, 'limit': limit}
        resp = requests.get(self.list_apps_url, headers=self.headers, params=params, verify=False)

        if resp.ok:
            data = resp.json()
            total_count = data.get('total')
            apps.extend([{"name": app['name'], "id": app['id']} for app in data.get('rows', [])])
            offset += limit
        else:
            break

    return apps
```
In this snippet, the `get_list_of_apps` method demonstrates the functional flow of making paginated requests to retrieve a list of applications.

## Endpoints Used/Created

### `predict_url`
- **Type:** POST
- **URL:** `{base_url}/api/v1/prompt_lib/predict/prompt_lib/{project_id}`
- **Purpose:** Used for making prediction requests with chat messages and model settings.

### `prompt_versions`
- **Type:** GET
- **URL:** `{base_url}/api/v1/prompt_lib/version/prompt_lib/{project_id}/{prompt_id}/{prompt_version_id}`
- **Purpose:** Used for retrieving prompt details and versions.

### `prompts`
- **Type:** GET
- **URL:** `{base_url}/api/v1/prompt_lib/prompt/prompt_lib/{project_id}/{prompt_id}`
- **Purpose:** Used for retrieving prompt details.

### `datasources`
- **Type:** GET
- **URL:** `{base_url}/api/v1/datasources/datasource/prompt_lib/{project_id}/{datasource_id}`
- **Purpose:** Used for retrieving datasource details.

### `datasources_predict`
- **Type:** POST
- **URL:** `{base_url}/api/v1/datasources/predict/prompt_lib/{project_id}/{datasource_id}`
- **Purpose:** Used for making prediction requests with datasource settings.

### `datasources_search`
- **Type:** POST
- **URL:** `{base_url}/api/v1/datasources/search/prompt_lib/{project_id}/{datasource_id}`
- **Purpose:** Used for making search requests with datasource settings.

### `app`
- **Type:** GET
- **URL:** `{base_url}/api/v1/applications/application/prompt_lib/{project_id}/{application_id}`
- **Purpose:** Used for retrieving application details.

### `application_versions`
- **Type:** PATCH
- **URL:** `{base_url}/api/v1/applications/version/prompt_lib/{project_id}/{application_id}/{application_version_id}`
- **Purpose:** Used for retrieving application version details.

### `list_apps_url`
- **Type:** GET
- **URL:** `{base_url}/api/v1/applications/applications/prompt_lib/{project_id}`
- **Purpose:** Used for retrieving a list of applications.

### `integration_details`
- **Type:** GET
- **URL:** `{base_url}/api/v1/integrations/integration/{project_id}/{integration_id}`
- **Purpose:** Used for retrieving integration details.

### `secrets_url`
- **Type:** GET
- **URL:** `{base_url}/api/v1/secrets/secret/{project_id}/{secret_name}`
- **Purpose:** Used for retrieving secret values.

### `artifacts_url`
- **Type:** GET, POST
- **URL:** `{base_url}/api/v1/artifacts/artifacts/{project_id}/{bucket_name}`
- **Purpose:** Used for listing and creating artifacts.

### `artifact_url`
- **Type:** GET, DELETE
- **URL:** `{base_url}/api/v1/artifacts/artifact/{project_id}/{bucket_name}/{artifact_name}`
- **Purpose:** Used for downloading and deleting artifacts.

### `bucket_url`
- **Type:** GET, POST
- **URL:** `{base_url}/api/v1/artifacts/buckets/{project_id}`
- **Purpose:** Used for checking bucket existence and creating buckets.

### `configurations_url`
- **Type:** GET
- **URL:** `{base_url}/api/v1/integrations/integrations/default/{project_id}?section=configurations&unsecret=true`
- **Purpose:** Used for retrieving available configurations.

### `ai_section_url`
- **Type:** GET
- **URL:** `{base_url}/api/v1/integrations/integrations/default/{project_id}?section=ai`
- **Purpose:** Used for retrieving AI models and integrations.
