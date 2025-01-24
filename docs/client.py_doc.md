# client.py

**Path:** `src/alita_sdk/clients/client.py`

## Data Flow

The data flow within `client.py` revolves around the `AlitaClient` class, which interacts with various endpoints to perform operations such as fetching prompt details, managing applications, and handling artifacts. Data originates from the initialization parameters of the `AlitaClient` class, including `base_url`, `project_id`, and `auth_token`. These parameters are used to construct URLs for API requests. The data is then transformed through various methods that make HTTP requests using the `requests` library. The responses from these requests are processed and returned in different formats, such as JSON objects or custom message objects.

For example, in the `prompt` method, data is fetched from an API endpoint and transformed into a list of message objects:

```python
url = f"{self.prompt_versions}/{prompt_id}/{prompt_version_id}"
data = requests.get(url, headers=self.headers, verify=False).json()
model_settings = data['model_settings']
messages = [SystemMessage(content=data['context'])]
```

Here, the URL is constructed using the `prompt_id` and `prompt_version_id`, and the response data is parsed into a JSON object. The `model_settings` and `messages` are then extracted and used within the method.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `AlitaClient` class with essential parameters such as `base_url`, `project_id`, and `auth_token`. It also sets up various URLs for API endpoints and headers for authentication.

### `prompt`

The `prompt` method fetches prompt details from the API and constructs a template using the `Jinja2TemplatedChatMessagesTemplate` class. It returns either the template or an `AlitaPrompt` object based on the `return_tool` parameter.

### `get_app_details`

This method retrieves details of a specific application using its `application_id` by making a GET request to the corresponding API endpoint.

### `get_list_of_apps`

The `get_list_of_apps` method fetches a list of applications with pagination support. It makes multiple GET requests to retrieve all applications and returns a list of application names and IDs.

### `fetch_available_configurations`

This method fetches available configurations for the project by making a GET request to the configurations API endpoint.

### `all_models_and_integrations`

This method retrieves all models and integrations for the project by making a GET request to the AI section API endpoint.

### `get_app_version_details`

This method retrieves details of a specific application version by making a PATCH request to the application versions API endpoint with the provided configurations.

### `get_integration_details`

This method fetches details of a specific integration using its `integration_id` by making a GET request to the corresponding API endpoint.

### `unsecret`

The `unsecret` method retrieves the value of a secret by making a GET request to the secrets API endpoint using the `secret_name`.

### `application`

This method initializes an application using the provided parameters and returns a runnable instance of `LangChainAssistant` or raises a `NotImplementedError` for unsupported runtimes.

### `datasource`

The `datasource` method fetches details of a specific datasource using its `datasource_id` and returns an `AlitaDataSource` object.

### `assistant`

This method initializes an assistant using the provided parameters and returns an instance of `LangChainAssistant`.

### `artifact`

The `artifact` method returns an `Artifact` object for the specified `bucket_name`.

### `_process_requst`

This private method processes the response of an HTTP request and returns the appropriate data or error message based on the status code.

### `bucket_exists`

This method checks if a bucket exists by making a GET request to the bucket URL and returns a boolean value.

### `create_bucket`

The `create_bucket` method creates a new bucket by making a POST request to the bucket URL with the provided bucket name and expiration settings.

### `list_artifacts`

This method lists all artifacts in a specified bucket by making a GET request to the artifacts URL.

### `create_artifact`

The `create_artifact` method creates a new artifact in a specified bucket by making a POST request with the artifact data.

### `download_artifact`

This method downloads an artifact from a specified bucket by making a GET request to the artifact URL and returns the content.

### `delete_artifact`

The `delete_artifact` method deletes an artifact from a specified bucket by making a DELETE request to the artifact URL.

### `_prepare_messages`

This private method prepares a list of messages for a chat by converting them into a specific format required by the API.

### `_prepare_payload`

This private method prepares the payload for a prediction request by combining messages, model settings, and variables into a dictionary.

### `async_predict`

The `async_predict` method makes an asynchronous prediction request to the API and yields the response messages one by one.

### `predict`

This method makes a synchronous prediction request to the API and returns the response messages.

### `rag`

The `rag` method performs a retrieval-augmented generation (RAG) operation by making a POST request to the datasource predict URL with the provided data and returns an `AIMessage` object.

### `search`

This method performs a search operation on a datasource by making a POST request to the datasource search URL with the provided messages and settings, and returns an `AIMessage` object.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging information, errors, and debugging messages within the `AlitaClient` class.

### `requests`

The `requests` library is used for making HTTP requests to various API endpoints. It simplifies sending HTTP requests and handling responses.

### `typing`

The `typing` module provides type hints for function parameters and return types, improving code readability and maintainability.

### `langchain_core.messages`

This module provides message classes such as `AIMessage`, `HumanMessage`, `SystemMessage`, and `BaseMessage`, which are used to construct chat messages within the `AlitaClient` class.

### `..langchain.assistant`

The `LangChainAssistant` class from this module is used to create a runnable instance of an assistant for handling chat interactions.

### `..llamaindex.assistant`

This module is commented out in the code, indicating that it might be used for future implementations related to the `LLamaAssistant` class.

### `..prompt`

The `AlitaPrompt` class from this module is used to create prompt objects for handling chat interactions.

### `..datasource`

The `AlitaDataSource` class from this module is used to create datasource objects for managing data sources within the `AlitaClient` class.

### `..artifact`

The `Artifact` class from this module is used to create artifact objects for managing artifacts within the `AlitaClient` class.

### `..langchain.chat_message_template`

The `Jinja2TemplatedChatMessagesTemplate` class from this module is used to create chat message templates using the Jinja2 templating engine.

## Functional Flow

The functional flow of `client.py` begins with the initialization of the `AlitaClient` class, where essential parameters and URLs are set up. The class provides various methods to interact with API endpoints, fetch data, and perform operations such as managing prompts, applications, and artifacts.

For example, the `prompt` method fetches prompt details and constructs a template for chat interactions. The `get_app_details` method retrieves application details, while the `get_list_of_apps` method fetches a list of applications with pagination support. The `fetch_available_configurations` and `all_models_and_integrations` methods retrieve configurations and models for the project.

The `application` method initializes an application and returns a runnable instance of `LangChainAssistant`, while the `datasource` method fetches datasource details and returns an `AlitaDataSource` object. The `assistant` method initializes an assistant and returns an instance of `LangChainAssistant`.

The `artifact` method returns an `Artifact` object for managing artifacts, and the `_process_requst` method processes HTTP request responses. The `bucket_exists` and `create_bucket` methods manage buckets, while the `list_artifacts`, `create_artifact`, `download_artifact`, and `delete_artifact` methods manage artifacts within buckets.

The `_prepare_messages` and `_prepare_payload` methods prepare messages and payloads for prediction requests, while the `async_predict` and `predict` methods make asynchronous and synchronous prediction requests, respectively. The `rag` and `search` methods perform retrieval-augmented generation and search operations on datasources.

## Endpoints Used/Created

### Prompt Endpoints

- **Predict URL:** `self.predict_url` - Used for making prediction requests.
- **Prompt Versions URL:** `self.prompt_versions` - Used for fetching prompt version details.
- **Prompts URL:** `self.prompts` - Used for fetching prompt details.

### Application Endpoints

- **App URL:** `self.app` - Used for fetching application details.
- **Application Versions URL:** `self.application_versions` - Used for fetching application version details.
- **List Apps URL:** `self.list_apps_url` - Used for fetching a list of applications.

### Datasource Endpoints

- **Datasources URL:** `self.datasources` - Used for fetching datasource details.
- **Datasources Predict URL:** `self.datasources_predict` - Used for making prediction requests on datasources.
- **Datasources Search URL:** `self.datasources_search` - Used for performing search operations on datasources.

### Integration Endpoints

- **Integration Details URL:** `self.integration_details` - Used for fetching integration details.

### Secrets Endpoints

- **Secrets URL:** `self.secrets_url` - Used for fetching secret values.

### Artifacts Endpoints

- **Artifacts URL:** `self.artifacts_url` - Used for managing artifacts.
- **Artifact URL:** `self.artifact_url` - Used for managing individual artifacts.
- **Bucket URL:** `self.bucket_url` - Used for managing buckets.

### Configurations Endpoints

- **Configurations URL:** `self.configurations_url` - Used for fetching available configurations.
- **AI Section URL:** `self.ai_section_url` - Used for fetching models and integrations.
