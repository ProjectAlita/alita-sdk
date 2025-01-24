# client.py

**Path:** `src/alita_sdk/clients/client.py`

## Data Flow

The `client.py` file primarily handles interactions with the Alita API. The data flow begins with the initialization of the `AlitaClient` class, where essential parameters such as `base_url`, `project_id`, and `auth_token` are set. These parameters are used to construct various API endpoints. When a method like `prompt`, `get_app_details`, or `predict` is called, it sends HTTP requests to these endpoints using the `requests` library. The responses are then processed and returned to the caller. For example, in the `prompt` method, data is fetched from the API, transformed into a template, and returned. Intermediate variables like `url`, `data`, and `response` are used to store and manipulate data temporarily.

```python
url = f"{self.prompt_versions}/{prompt_id}/{prompt_version_id}"
data = requests.get(url, headers=self.headers, verify=False).json()
model_settings = data['model_settings']
messages = [SystemMessage(content=data['context'])]
```

In this snippet, the `url` is constructed, data is fetched from the API, and `model_settings` and `messages` are extracted from the response.

## Functions Descriptions

### `__init__`

The constructor initializes the `AlitaClient` with essential parameters and constructs various API endpoints. It takes `base_url`, `project_id`, `auth_token`, and optional headers and configurations as inputs.

### `prompt`

This method fetches prompt details from the API and constructs a template. It takes `prompt_id`, `prompt_version_id`, and optional `chat_history` and `return_tool` as inputs. It returns a template or an `AlitaPrompt` object.

### `get_app_details`

Fetches details of a specific application using its ID. It takes `application_id` as input and returns the application details.

### `get_list_of_apps`

Retrieves a list of applications with pagination. It returns a list of application names and IDs.

### `fetch_available_configurations`

Fetches available configurations from the API. It returns a list of configurations.

### `all_models_and_integrations`

Fetches all models and integrations from the API. It returns a list of models and integrations.

### `get_app_version_details`

Fetches details of a specific application version. It takes `application_id` and `application_version_id` as inputs and returns the version details.

### `get_integration_details`

Fetches details of a specific integration. It takes `integration_id` and an optional `format_for_model` flag as inputs and returns the integration details.

### `unsecret`

Fetches a secret value by its name. It takes `secret_name` as input and returns the secret value.

### `application`

Initializes an application with the given parameters. It takes `client`, `application_id`, `application_version_id`, and optional `tools`, `chat_history`, `app_type`, `memory`, and `runtime` as inputs.

### `datasource`

Fetches details of a specific datasource. It takes `datasource_id` as input and returns an `AlitaDataSource` object.

### `assistant`

Initializes an assistant with the given parameters. It takes `prompt_id`, `prompt_version_id`, `tools`, optional `openai_tools`, `client`, and `chat_history` as inputs.

### `artifact`

Initializes an artifact with the given bucket name. It takes `bucket_name` as input and returns an `Artifact` object.

### `_process_requst`

Processes the HTTP response and handles errors. It takes `data` as input and returns the processed response.

### `bucket_exists`

Checks if a bucket exists. It takes `bucket_name` as input and returns a boolean.

### `create_bucket`

Creates a new bucket. It takes `bucket_name` as input and returns the response.

### `list_artifacts`

Lists artifacts in a bucket. It takes `bucket_name` as input and returns the list of artifacts.

### `create_artifact`

Creates a new artifact in a bucket. It takes `bucket_name`, `artifact_name`, and `artifact_data` as inputs and returns the response.

### `download_artifact`

Downloads an artifact from a bucket. It takes `bucket_name` and `artifact_name` as inputs and returns the artifact content.

### `delete_artifact`

Deletes an artifact from a bucket. It takes `bucket_name` and `artifact_name` as inputs and returns the response.

### `_prepare_messages`

Prepares chat messages for the API request. It takes `messages` as input and returns the prepared chat history.

### `_prepare_payload`

Prepares the payload for the API request. It takes `messages`, `model_settings`, and `variables` as inputs and returns the prepared payload.

### `async_predict`

Sends an asynchronous prediction request to the API. It takes `messages`, `model_settings`, and optional `variables` as inputs and yields the response messages.

### `predict`

Sends a prediction request to the API. It takes `messages`, `model_settings`, and optional `variables` as inputs and returns the response messages.

### `rag`

Sends a retrieval-augmented generation request to the API. It takes `datasource_id`, optional `user_input`, `context`, `chat_history`, `datasource_settings`, and `datasource_predict_settings` as inputs and returns an `AIMessage`.

### `search`

Sends a search request to the API. It takes `datasource_id`, `messages`, and `datasource_settings` as inputs and returns an `AIMessage`.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging information and errors within the client.

### `requests`

Used for making HTTP requests to the Alita API.

### `typing`

Provides type hints for better code readability and maintenance.

### `langchain_core.messages`

Provides message classes like `AIMessage`, `HumanMessage`, and `SystemMessage` used in chat interactions.

### `..langchain.assistant`

Imports the `Assistant` class from the `langchain` module.

### `..clients.prompt`

Imports the `AlitaPrompt` class for handling prompts.

### `..clients.datasource`

Imports the `AlitaDataSource` class for handling datasources.

### `..clients.artifact`

Imports the `Artifact` class for handling artifacts.

### `..langchain.chat_message_template`

Imports the `Jinja2TemplatedChatMessagesTemplate` class for templating chat messages.

## Functional Flow

1. **Initialization**: The `AlitaClient` class is initialized with essential parameters like `base_url`, `project_id`, and `auth_token`.
2. **API Requests**: Methods like `prompt`, `get_app_details`, and `predict` send HTTP requests to the Alita API using the `requests` library.
3. **Data Processing**: The responses from the API are processed and returned to the caller. For example, the `prompt` method constructs a template from the API response.
4. **Error Handling**: The `_process_requst` method handles errors in the HTTP responses.
5. **Utility Methods**: Methods like `_prepare_messages` and `_prepare_payload` prepare data for API requests.

## Endpoints Used/Created

### `prompt`

- **URL**: `{self.prompt_versions}/{prompt_id}/{prompt_version_id}`
- **Method**: GET
- **Purpose**: Fetches prompt details.

### `get_app_details`

- **URL**: `{self.app}/{application_id}`
- **Method**: GET
- **Purpose**: Fetches application details.

### `get_list_of_apps`

- **URL**: `{self.list_apps_url}`
- **Method**: GET
- **Purpose**: Retrieves a list of applications.

### `fetch_available_configurations`

- **URL**: `{self.configurations_url}`
- **Method**: GET
- **Purpose**: Fetches available configurations.

### `all_models_and_integrations`

- **URL**: `{self.ai_section_url}`
- **Method**: GET
- **Purpose**: Fetches all models and integrations.

### `get_app_version_details`

- **URL**: `{self.application_versions}/{application_id}/{application_version_id}`
- **Method**: PATCH
- **Purpose**: Fetches application version details.

### `get_integration_details`

- **URL**: `{self.integration_details}/{integration_id}`
- **Method**: GET
- **Purpose**: Fetches integration details.

### `unsecret`

- **URL**: `{self.secrets_url}/{secret_name}`
- **Method**: GET
- **Purpose**: Fetches a secret value.

### `datasource`

- **URL**: `{self.datasources}/{datasource_id}`
- **Method**: GET
- **Purpose**: Fetches datasource details.

### `async_predict`

- **URL**: `{self.predict_url}`
- **Method**: POST
- **Purpose**: Sends an asynchronous prediction request.

### `predict`

- **URL**: `{self.predict_url}`
- **Method**: POST
- **Purpose**: Sends a prediction request.

### `rag`

- **URL**: `{self.datasources_predict}/{datasource_id}`
- **Method**: POST
- **Purpose**: Sends a retrieval-augmented generation request.

### `search`

- **URL**: `{self.datasources_search}/{datasource_id}`
- **Method**: POST
- **Purpose**: Sends a search request.
