# client.py

**Path:** `src/alita_sdk/clients/client.py`

## Data Flow

The data flow within the `client.py` file revolves around the `AlitaClient` class, which is responsible for interacting with various endpoints of the Alita API. The data originates from the initialization parameters of the `AlitaClient` class, such as `base_url`, `project_id`, and `auth_token`. These parameters are used to construct various API endpoint URLs and headers for authentication.

Data is then transformed and manipulated through various methods within the `AlitaClient` class. For example, the `prompt` method fetches prompt details from the API, processes the response to extract model settings and messages, and constructs a `Jinja2TemplatedChatMessagesTemplate` object. Similarly, the `get_app_details` method retrieves application details from the API and returns the response data.

The data flow can be visualized as follows:

1. Initialization: Data is passed to the `AlitaClient` constructor and stored as instance variables.
2. API Requests: Methods like `prompt`, `get_app_details`, and `predict` make API requests using the stored instance variables.
3. Data Processing: The responses from the API are processed to extract relevant information and construct objects or return data.

Example:
```python
class AlitaClient:
    def __init__(self, base_url: str, project_id: int, auth_token: str, api_extra_headers: Optional[dict] = None, configurations: Optional[list] = None, **kwargs):
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
```

## Functions Descriptions

### `__init__`
The constructor initializes the `AlitaClient` instance with the provided parameters. It constructs various API endpoint URLs and sets up the headers for authentication.

### `prompt`
Fetches prompt details from the API, processes the response to extract model settings and messages, and constructs a `Jinja2TemplatedChatMessagesTemplate` object. If `return_tool` is `True`, it returns an `AlitaPrompt` object.

### `get_app_details`
Retrieves application details from the API for a given `application_id` and returns the response data.

### `get_list_of_apps`
Fetches a list of applications from the API with pagination support. It returns a list of application names and IDs.

### `fetch_available_configurations`
Fetches available configurations from the API and returns them as a list.

### `all_models_and_integrations`
Fetches all models and integrations from the API and returns the response data.

### `get_app_version_details`
Fetches application version details from the API for a given `application_id` and `application_version_id`. It applies configurations if available and returns the response data.

### `get_integration_details`
Fetches integration details from the API for a given `integration_id` and returns the response data.

### `unsecret`
Fetches a secret from the API for a given `secret_name` and returns the secret value.

### `application`
Fetches application version details and returns a `LangChainAssistant` object based on the runtime and app type.

### `datasource`
Fetches datasource details from the API for a given `datasource_id` and returns an `AlitaDataSource` object.

### `assistant`
Fetches prompt details and returns a `LangChainAssistant` object.

### `artifact`
Returns an `Artifact` object for a given `bucket_name`.

### `_process_requst`
Processes the API response and returns the JSON data or an error message based on the status code.

### `bucket_exists`
Checks if a bucket exists in the API and returns `True` or `False`.

### `create_bucket`
Creates a new bucket in the API and returns the response data.

### `list_artifacts`
Lists artifacts in a given bucket and returns the response data.

### `create_artifact`
Creates a new artifact in a given bucket and returns the response data.

### `download_artifact`
Downloads an artifact from a given bucket and returns the content.

### `delete_artifact`
Deletes an artifact from a given bucket and returns the response data.

### `_prepare_messages`
Prepares chat history messages for the API request.

### `_prepare_payload`
Prepares the payload for the API request with messages, model settings, and variables.

### `async_predict`
Sends an asynchronous prediction request to the API and yields the response messages.

### `predict`
Sends a prediction request to the API and returns the response messages.

### `rag`
Sends a retrieval-augmented generation request to the API and returns an `AIMessage` object with the response content and references.

### `search`
Sends a search request to the API and returns an `AIMessage` object with the search results and references.

## Dependencies Used and Their Descriptions

### `logging`
Used for logging information and errors within the `AlitaClient` class.

### `requests`
Used for making HTTP requests to the Alita API endpoints.

### `typing`
Provides type hints for function parameters and return types.

### `langchain_core.messages`
Imports message classes (`AIMessage`, `HumanMessage`, `SystemMessage`, `BaseMessage`) used for constructing chat messages.

### `..langchain.assistant`
Imports the `Assistant` class from the `langchain` module, used for creating `LangChainAssistant` objects.

### `..prompt`
Imports the `AlitaPrompt` class, used for creating prompt objects.

### `..datasource`
Imports the `AlitaDataSource` class, used for creating datasource objects.

### `..artifact`
Imports the `Artifact` class, used for creating artifact objects.

### `..langchain.chat_message_template`
Imports the `Jinja2TemplatedChatMessagesTemplate` class, used for creating chat message templates.

## Functional Flow

The functional flow of the `client.py` file involves the following steps:

1. **Initialization**: An instance of the `AlitaClient` class is created with the required parameters.
2. **API Requests**: Methods like `prompt`, `get_app_details`, and `predict` make API requests using the stored instance variables.
3. **Data Processing**: The responses from the API are processed to extract relevant information and construct objects or return data.
4. **Error Handling**: The `_process_requst` method handles errors in API responses and returns appropriate error messages.
5. **Object Creation**: Methods like `application`, `datasource`, and `artifact` create and return objects based on the API responses.

Example:
```python
def get_app_details(self, application_id: int):
    url = f"{self.app}/{application_id}"
    data = requests.get(url, headers=self.headers, verify=False).json()
    return data
```

## Endpoints Used/Created

### `self.predict_url`
- **Type**: POST
- **URL**: `{self.base_url}{self.api_path}/prompt_lib/predict/prompt_lib/{self.project_id}`
- **Purpose**: Sends a prediction request to the API.

### `self.prompt_versions`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/prompt_lib/version/prompt_lib/{self.project_id}`
- **Purpose**: Fetches prompt version details from the API.

### `self.prompts`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/prompt_lib/prompt/prompt_lib/{self.project_id}`
- **Purpose**: Fetches prompt details from the API.

### `self.datasources`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/datasources/datasource/prompt_lib/{self.project_id}`
- **Purpose**: Fetches datasource details from the API.

### `self.datasources_predict`
- **Type**: POST
- **URL**: `{self.base_url}{self.api_path}/datasources/predict/prompt_lib/{self.project_id}`
- **Purpose**: Sends a datasource prediction request to the API.

### `self.datasources_search`
- **Type**: POST
- **URL**: `{self.base_url}{self.api_path}/datasources/search/prompt_lib/{self.project_id}`
- **Purpose**: Sends a datasource search request to the API.

### `self.app`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/applications/application/prompt_lib/{self.project_id}`
- **Purpose**: Fetches application details from the API.

### `self.application_versions`
- **Type**: PATCH
- **URL**: `{self.base_url}{self.api_path}/applications/version/prompt_lib/{self.project_id}`
- **Purpose**: Fetches application version details from the API.

### `self.list_apps_url`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/applications/applications/prompt_lib/{self.project_id}`
- **Purpose**: Fetches a list of applications from the API.

### `self.integration_details`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/integrations/integration/{self.project_id}`
- **Purpose**: Fetches integration details from the API.

### `self.secrets_url`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/secrets/secret/{self.project_id}`
- **Purpose**: Fetches a secret from the API.

### `self.artifacts_url`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/artifacts/artifacts/{self.project_id}`
- **Purpose**: Lists artifacts in a given bucket.

### `self.artifact_url`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/artifacts/artifact/{self.project_id}`
- **Purpose**: Downloads an artifact from a given bucket.

### `self.bucket_url`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/artifacts/buckets/{self.project_id}`
- **Purpose**: Checks if a bucket exists in the API.

### `self.configurations_url`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=configurations&unsecret=true`
- **Purpose**: Fetches available configurations from the API.

### `self.ai_section_url`
- **Type**: GET
- **URL**: `{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=ai`
- **Purpose**: Fetches all models and integrations from the API.
