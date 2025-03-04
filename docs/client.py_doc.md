# client.py

**Path:** `src/alita_sdk/clients/client.py`

## Data Flow

The data flow within `client.py` revolves around the `AlitaClient` class, which interacts with various endpoints of an API. The data originates from the initialization parameters of the `AlitaClient` class, such as `base_url`, `project_id`, and `auth_token`. These parameters are used to construct URLs and headers for API requests. The data is then transformed through various methods that make HTTP requests to these URLs, using the headers for authentication. The responses from these requests are processed and returned as Python dictionaries or other relevant data structures.

For example, in the `prompt` method, the data flow can be traced as follows:

```python
url = f"{self.prompt_versions}/{prompt_id}/{prompt_version_id}"
data = requests.get(url, headers=self.headers, verify=False).json()
model_settings = data['model_settings']
messages = [SystemMessage(content=data['context'])]
```

Here, the URL is constructed using the `prompt_versions` attribute and the `prompt_id` and `prompt_version_id` parameters. An HTTP GET request is made to this URL, and the response is parsed as JSON. The `model_settings` and `messages` are then extracted from the response data.

## Functions Descriptions

### `__init__`

The `__init__` method initializes an instance of the `AlitaClient` class. It takes several parameters, including `base_url`, `project_id`, `auth_token`, and optional `api_extra_headers` and `configurations`. The method constructs various URLs and headers for API requests and stores them as instance attributes.

### `prompt`

The `prompt` method retrieves the details of a specific prompt version from the API. It constructs the URL using the `prompt_versions` attribute and the `prompt_id` and `prompt_version_id` parameters. An HTTP GET request is made to this URL, and the response is parsed as JSON. The method then constructs a list of messages and variables based on the response data and returns a `Jinja2TemplatedChatMessagesTemplate` object.

### `get_app_details`

The `get_app_details` method retrieves the details of a specific application from the API. It constructs the URL using the `app` attribute and the `application_id` parameter. An HTTP GET request is made to this URL, and the response is parsed as JSON. The method returns the response data.

### `get_list_of_apps`

The `get_list_of_apps` method retrieves a list of applications from the API. It makes multiple HTTP GET requests with pagination parameters to retrieve all applications. The responses are parsed as JSON, and the application details are extracted and returned as a list.

### `fetch_available_configurations`

The `fetch_available_configurations` method retrieves the available configurations from the API. An HTTP GET request is made to the `configurations_url`, and the response is parsed as JSON. The method returns the response data.

### `all_models_and_integrations`

The `all_models_and_integrations` method retrieves the details of all models and integrations from the API. An HTTP GET request is made to the `ai_section_url`, and the response is parsed as JSON. The method returns the response data.

### `get_app_version_details`

The `get_app_version_details` method retrieves the details of a specific application version from the API. It constructs the URL using the `application_versions` attribute and the `application_id` and `application_version_id` parameters. An HTTP PATCH request is made to this URL with the configurations as the request body. The response is parsed as JSON and returned.

### `get_integration_details`

The `get_integration_details` method retrieves the details of a specific integration from the API. It constructs the URL using the `integration_details` attribute and the `integration_id` parameter. An HTTP GET request is made to this URL, and the response is parsed as JSON. The method returns the response data.

### `unsecret`

The `unsecret` method retrieves the value of a secret from the API. It constructs the URL using the `secrets_url` attribute and the `secret_name` parameter. An HTTP GET request is made to this URL, and the response is parsed as JSON. The method returns the secret value.

### `application`

The `application` method retrieves the details of a specific application version and returns an instance of the `LangChainAssistant` class. It constructs the URL using the `application_versions` attribute and the `application_id` and `application_version_id` parameters. The method then retrieves the application details and initializes the `LangChainAssistant` instance with the retrieved data.

### `datasource`

The `datasource` method retrieves the details of a specific datasource from the API. It constructs the URL using the `datasources` attribute and the `datasource_id` parameter. An HTTP GET request is made to this URL, and the response is parsed as JSON. The method returns an instance of the `AlitaDataSource` class initialized with the retrieved data.

### `assistant`

The `assistant` method retrieves the details of a specific prompt version and returns an instance of the `LangChainAssistant` class. It constructs the URL using the `prompt_versions` attribute and the `prompt_id` and `prompt_version_id` parameters. The method then retrieves the prompt details and initializes the `LangChainAssistant` instance with the retrieved data.

### `artifact`

The `artifact` method returns an instance of the `Artifact` class initialized with the `AlitaClient` instance and the `bucket_name` parameter.

### `_process_requst`

The `_process_requst` method processes the response of an HTTP request. It checks the status code of the response and returns an appropriate error message or the parsed JSON data.

### `bucket_exists`

The `bucket_exists` method checks if a specific bucket exists in the API. It makes an HTTP GET request to the `bucket_url` and checks if the bucket name is present in the response data.

### `create_bucket`

The `create_bucket` method creates a new bucket in the API. It constructs the request body with the bucket name and expiration details and makes an HTTP POST request to the `bucket_url`. The response is processed and returned.

### `list_artifacts`

The `list_artifacts` method retrieves a list of artifacts from a specific bucket in the API. It constructs the URL using the `artifacts_url` attribute and the `bucket_name` parameter. An HTTP GET request is made to this URL, and the response is processed and returned.

### `create_artifact`

The `create_artifact` method creates a new artifact in a specific bucket in the API. It constructs the URL using the `artifacts_url` attribute and the `bucket_name` parameter. An HTTP POST request is made to this URL with the artifact data as the request body. The response is processed and returned.

### `download_artifact`

The `download_artifact` method downloads a specific artifact from a bucket in the API. It constructs the URL using the `artifact_url` attribute and the `bucket_name` and `artifact_name` parameters. An HTTP GET request is made to this URL, and the response content is returned.

### `delete_artifact`

The `delete_artifact` method deletes a specific artifact from a bucket in the API. It constructs the URL using the `artifact_url` attribute and the `bucket_name` and `artifact_name` parameters. An HTTP DELETE request is made to this URL, and the response is processed and returned.

### `_prepare_messages`

The `_prepare_messages` method prepares a list of messages for an API request. It iterates over the input messages and constructs a list of dictionaries with the message role and content.

### `_prepare_payload`

The `_prepare_payload` method prepares the payload for an API request. It constructs a dictionary with the project ID, context, model settings, user input, messages, and variables.

### `async_predict`

The `async_predict` method makes an asynchronous prediction request to the API. It prepares the payload using the `_prepare_payload` method and makes an HTTP POST request to the `predict_url`. The response messages are yielded as they are received.

### `predict`

The `predict` method makes a prediction request to the API. It prepares the payload using the `_prepare_payload` method and makes an HTTP POST request to the `predict_url`. The response messages are returned as a list.

### `rag`

The `rag` method makes a retrieval-augmented generation request to the API. It constructs the request body with the user input, chat history, context, and datasource settings. An HTTP POST request is made to the `datasources_predict` URL, and the response is returned as an `AIMessage` object.

### `search`

The `search` method makes a search request to the API. It prepares the chat history and constructs the request body with the user input and datasource settings. An HTTP POST request is made to the `datasources_search` URL, and the response is returned as an `AIMessage` object.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging messages within the `client.py` file. It is configured to log messages using the `logger` object.

### `requests`

The `requests` library is used for making HTTP requests to the API. It is used extensively throughout the `client.py` file for making GET, POST, PATCH, and DELETE requests.

### `urllib.parse.quote`

The `quote` function from the `urllib.parse` module is used to URL-encode the artifact name in the `delete_artifact` method.

### `typing`

The `typing` module is used for type hinting within the `client.py` file. It provides type hints for function parameters and return values.

### `langchain_core.messages`

The `langchain_core.messages` module provides message classes such as `AIMessage`, `HumanMessage`, `SystemMessage`, and `BaseMessage`. These classes are used to construct and process messages within the `client.py` file.

### `..langchain.assistant`

The `Assistant` class from the `..langchain.assistant` module is used to create instances of the `LangChainAssistant` class in the `application` and `assistant` methods.

### `..prompt`

The `AlitaPrompt` class from the `..prompt` module is used to create instances of the `AlitaPrompt` class in the `prompt` method.

### `..datasource`

The `AlitaDataSource` class from the `..datasource` module is used to create instances of the `AlitaDataSource` class in the `datasource` method.

### `..artifact`

The `Artifact` class from the `..artifact` module is used to create instances of the `Artifact` class in the `artifact` method.

### `..langchain.chat_message_template`

The `Jinja2TemplatedChatMessagesTemplate` class from the `..langchain.chat_message_template` module is used to create instances of the `Jinja2TemplatedChatMessagesTemplate` class in the `prompt` method.

## Functional Flow

The functional flow of `client.py` begins with the initialization of the `AlitaClient` class. The `__init__` method sets up the necessary URLs and headers for API requests. The various methods of the `AlitaClient` class are then used to interact with the API, making HTTP requests and processing the responses.

For example, the `prompt` method follows this flow:

1. Construct the URL using the `prompt_versions` attribute and the `prompt_id` and `prompt_version_id` parameters.
2. Make an HTTP GET request to the constructed URL.
3. Parse the response as JSON.
4. Extract the `model_settings` and `messages` from the response data.
5. Construct a list of `SystemMessage`, `AIMessage`, and `HumanMessage` objects based on the response data.
6. Return a `Jinja2TemplatedChatMessagesTemplate` object with the constructed messages.

## Endpoints Used/Created

### `prompt_versions`

- **URL:** `{base_url}{api_path}/prompt_lib/version/prompt_lib/{project_id}`
- **Method:** GET
- **Description:** Retrieves the details of a specific prompt version.

### `prompts`

- **URL:** `{base_url}{api_path}/prompt_lib/prompt/prompt_lib/{project_id}`
- **Method:** GET
- **Description:** Retrieves the details of a specific prompt.

### `app`

- **URL:** `{base_url}{api_path}/applications/application/prompt_lib/{project_id}`
- **Method:** GET
- **Description:** Retrieves the details of a specific application.

### `list_apps_url`

- **URL:** `{base_url}{api_path}/applications/applications/prompt_lib/{project_id}`
- **Method:** GET
- **Description:** Retrieves a list of applications.

### `configurations_url`

- **URL:** `{base_url}{api_path}/integrations/integrations/default/{project_id}?section=configurations&unsecret=true`
- **Method:** GET
- **Description:** Retrieves the available configurations.

### `ai_section_url`

- **URL:** `{base_url}{api_path}/integrations/integrations/default/{project_id}?section=ai`
- **Method:** GET
- **Description:** Retrieves the details of all models and integrations.

### `integration_details`

- **URL:** `{base_url}{api_path}/integrations/integration/{project_id}`
- **Method:** GET
- **Description:** Retrieves the details of a specific integration.

### `secrets_url`

- **URL:** `{base_url}{api_path}/secrets/secret/{project_id}`
- **Method:** GET
- **Description:** Retrieves the value of a secret.

### `datasources`

- **URL:** `{base_url}{api_path}/datasources/datasource/prompt_lib/{project_id}`
- **Method:** GET
- **Description:** Retrieves the details of a specific datasource.

### `datasources_predict`

- **URL:** `{base_url}{api_path}/datasources/predict/prompt_lib/{project_id}`
- **Method:** POST
- **Description:** Makes a prediction request to a specific datasource.

### `datasources_search`

- **URL:** `{base_url}{api_path}/datasources/search/prompt_lib/{project_id}`
- **Method:** POST
- **Description:** Makes a search request to a specific datasource.

### `artifacts_url`

- **URL:** `{base_url}{api_path}/artifacts/artifacts/{project_id}`
- **Method:** GET, POST
- **Description:** Retrieves a list of artifacts or creates a new artifact in a specific bucket.

### `artifact_url`

- **URL:** `{base_url}{api_path}/artifacts/artifact/{project_id}`
- **Method:** GET, DELETE
- **Description:** Downloads or deletes a specific artifact from a bucket.

### `bucket_url`

- **URL:** `{base_url}{api_path}/artifacts/buckets/{project_id}`
- **Method:** GET, POST
- **Description:** Checks if a specific bucket exists or creates a new bucket.