# client.py

**Path:** `src/alita_sdk/clients/client.py`

## Data Flow

The data flow within the `client.py` file primarily revolves around the `AlitaClient` class, which interacts with various endpoints of an API. The data originates from the initialization parameters of the `AlitaClient` class, such as `base_url`, `project_id`, and `auth_token`. These parameters are used to construct URLs and headers for API requests. The data is then transformed through various methods within the class, which make HTTP requests to the API and process the responses.

For example, in the `prompt` method, the data flow can be traced as follows:

1. The method constructs a URL using the `prompt_versions` attribute and the provided `prompt_id` and `prompt_version_id`.
2. It makes a GET request to the constructed URL and retrieves the response data.
3. The response data is processed to extract `model_settings`, `messages`, and `variables`.
4. A `Jinja2TemplatedChatMessagesTemplate` object is created using the extracted data.
5. The method returns the template object or an `AlitaPrompt` object based on the `return_tool` parameter.

```python
url = f"{self.prompt_versions}/{prompt_id}/{prompt_version_id}"
data = requests.get(url, headers=self.headers, verify=False).json()
model_settings = data['model_settings']
messages = [SystemMessage(content=data['context'])]
# Further processing of data
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes an instance of the `AlitaClient` class. It sets up various attributes such as `base_url`, `project_id`, `auth_token`, and `headers`. It also constructs several URLs for different API endpoints using the provided `base_url` and `project_id`.

### `prompt`

The `prompt` method retrieves and processes prompt data from the API. It constructs a URL using the `prompt_versions` attribute and the provided `prompt_id` and `prompt_version_id`, makes a GET request to the URL, and processes the response data to create a `Jinja2TemplatedChatMessagesTemplate` object. It returns the template object or an `AlitaPrompt` object based on the `return_tool` parameter.

### `get_app_details`

The `get_app_details` method retrieves details of a specific application from the API. It constructs a URL using the `app` attribute and the provided `application_id`, makes a GET request to the URL, and returns the response data.

### `get_list_of_apps`

The `get_list_of_apps` method retrieves a list of applications from the API. It makes multiple GET requests with pagination to retrieve all applications and returns a list of application names and IDs.

### `fetch_available_configurations`

The `fetch_available_configurations` method retrieves available configurations from the API. It makes a GET request to the `configurations_url` and returns the response data.

### `all_models_and_integrations`

The `all_models_and_integrations` method retrieves all models and integrations from the API. It makes a GET request to the `ai_section_url` and returns the response data.

### `get_app_version_details`

The `get_app_version_details` method retrieves details of a specific application version from the API. It constructs a URL using the `application_versions` attribute and the provided `application_id` and `application_version_id`, makes a PATCH request to the URL with configurations, and returns the response data.

### `get_integration_details`

The `get_integration_details` method retrieves details of a specific integration from the API. It constructs a URL using the `integration_details` attribute and the provided `integration_id`, makes a GET request to the URL, and returns the response data.

### `unsecret`

The `unsecret` method retrieves a secret value from the API. It constructs a URL using the `secrets_url` attribute and the provided `secret_name`, makes a GET request to the URL, and returns the secret value.

### `application`

The `application` method retrieves application version details and returns an assistant object based on the runtime parameter. It supports different runtimes such as `langchain` and `llama`.

### `datasource`

The `datasource` method retrieves details of a specific datasource from the API. It constructs a URL using the `datasources` attribute and the provided `datasource_id`, makes a GET request to the URL, and returns an `AlitaDataSource` object.

### `assistant`

The `assistant` method retrieves prompt data and returns a `LangChainAssistant` object.

### `artifact`

The `artifact` method returns an `Artifact` object for the specified bucket name.

### `_process_requst`

The `_process_requst` method processes the response of an HTTP request. It handles different status codes and returns the appropriate response data or error message.

### `bucket_exists`

The `bucket_exists` method checks if a bucket exists in the API. It makes a GET request to the `bucket_url` and checks if the specified bucket name is present in the response data.

### `create_bucket`

The `create_bucket` method creates a new bucket in the API. It makes a POST request to the `bucket_url` with the bucket name and expiration settings, and returns the response data.

### `list_artifacts`

The `list_artifacts` method retrieves a list of artifacts in a specified bucket from the API. It constructs a URL using the `artifacts_url` attribute and the provided `bucket_name`, makes a GET request to the URL, and returns the response data.

### `create_artifact`

The `create_artifact` method creates a new artifact in a specified bucket in the API. It constructs a URL using the `artifacts_url` attribute and the provided `bucket_name`, makes a POST request to the URL with the artifact data, and returns the response data.

### `download_artifact`

The `download_artifact` method downloads an artifact from a specified bucket in the API. It constructs a URL using the `artifact_url` attribute and the provided `bucket_name` and `artifact_name`, makes a GET request to the URL, and returns the artifact content.

### `delete_artifact`

The `delete_artifact` method deletes an artifact from a specified bucket in the API. It constructs a URL using the `artifact_url` attribute and the provided `bucket_name` and `artifact_name`, makes a DELETE request to the URL, and returns the response data.

### `_prepare_messages`

The `_prepare_messages` method prepares a list of messages for an API request. It converts a list of `BaseMessage` objects into a list of dictionaries with `role` and `content` keys.

### `_prepare_payload`

The `_prepare_payload` method prepares the payload for a prediction request. It constructs a dictionary with project ID, context, model settings, user input, messages, and variables.

### `async_predict`

The `async_predict` method makes an asynchronous prediction request to the API. It prepares the payload, makes a POST request to the `predict_url`, and yields the response messages.

### `predict`

The `predict` method makes a prediction request to the API. It prepares the payload, makes a POST request to the `predict_url`, and returns the response messages.

### `rag`

The `rag` method makes a retrieval-augmented generation request to the API. It constructs the request data with user input, context, chat history, and datasource settings, makes a POST request to the `datasources_predict` URL, and returns an `AIMessage` object with the response content and references.

### `search`

The `search` method makes a search request to the API. It prepares the chat history, constructs the request data with user input and datasource settings, makes a POST request to the `datasources_search` URL, and returns an `AIMessage` object with the response content and references.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used to set up a logger for the `client.py` file. It provides a way to configure and use loggers to output messages for debugging and monitoring purposes.

### `requests`

The `requests` library is used to make HTTP requests to the API. It simplifies the process of sending HTTP requests and handling responses.

### `typing`

The `typing` module is used to provide type hints for function parameters and return values. It helps in improving code readability and type checking.

### `langchain_core.messages`

The `langchain_core.messages` module is used to import message classes such as `AIMessage`, `HumanMessage`, `SystemMessage`, and `BaseMessage`. These classes are used to represent different types of messages in the chat history.

### `..langchain.assistant`

The `..langchain.assistant` module is used to import the `Assistant` class from the `langchain` package. This class is used to create an assistant object for the `langchain` runtime.

### `..llamaindex.assistant`

The `..llamaindex.assistant` module is commented out, indicating that it is not currently used in the code. It is intended to import the `Assistant` class from the `llamaindex` package for the `llama` runtime.

### `prompt`

The `prompt` module is used to import the `AlitaPrompt` class. This class is used to create a prompt object for the `AlitaClient` class.

### `datasource`

The `datasource` module is used to import the `AlitaDataSource` class. This class is used to create a datasource object for the `AlitaClient` class.

### `artifact`

The `artifact` module is used to import the `Artifact` class. This class is used to create an artifact object for the `AlitaClient` class.

### `chat_message_template`

The `chat_message_template` module is used to import the `Jinja2TemplatedChatMessagesTemplate` class. This class is used to create a template for chat messages using Jinja2 templating.

## Functional Flow

The functional flow of the `client.py` file revolves around the `AlitaClient` class and its methods. The sequence of operations is as follows:

1. An instance of the `AlitaClient` class is created with the required parameters such as `base_url`, `project_id`, and `auth_token`.
2. Various methods of the `AlitaClient` class are called to interact with the API and perform different operations such as retrieving prompt data, application details, configurations, models, integrations, and artifacts.
3. The methods make HTTP requests to the API using the `requests` library and process the responses.
4. The processed data is returned to the caller or used to create objects such as `Jinja2TemplatedChatMessagesTemplate`, `AlitaPrompt`, `LangChainAssistant`, `AlitaDataSource`, and `Artifact`.
5. The methods handle different input conditions and errors by using conditional statements and exception handling.

For example, the `get_list_of_apps` method retrieves a list of applications from the API by making multiple GET requests with pagination:

```python
offset = 0
limit = 10
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
```

## Endpoints Used/Created

The `client.py` file interacts with various endpoints of an API. The endpoints are constructed using the `base_url` and `project_id` parameters provided during the initialization of the `AlitaClient` class. The endpoints used in the file include:

### Prompt Endpoints

- `self.prompt_versions`: Retrieves prompt versions.
- `self.prompts`: Retrieves prompt details.

### Application Endpoints

- `self.app`: Retrieves application details.
- `self.application_versions`: Retrieves application version details.
- `self.list_apps_url`: Retrieves a list of applications.

### Configuration Endpoints

- `self.configurations_url`: Retrieves available configurations.
- `self.ai_section_url`: Retrieves all models and integrations.

### Integration Endpoints

- `self.integration_details`: Retrieves integration details.

### Secret Endpoints

- `self.secrets_url`: Retrieves secret values.

### Artifact Endpoints

- `self.artifacts_url`: Retrieves a list of artifacts.
- `self.artifact_url`: Retrieves artifact details.
- `self.bucket_url`: Checks if a bucket exists and creates a new bucket.

### Datasource Endpoints

- `self.datasources`: Retrieves datasource details.
- `self.datasources_predict`: Makes a prediction request to a datasource.
- `self.datasources_search`: Makes a search request to a datasource.

These endpoints are used to perform various operations such as retrieving data, making predictions, creating artifacts, and managing configurations. The methods in the `AlitaClient` class construct the URLs for these endpoints, make HTTP requests using the `requests` library, and process the responses to return the required data or objects.