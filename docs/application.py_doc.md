# application.py

**Path:** `src/alita_sdk/toolkits/application.py`

## Data Flow

The data flow within `application.py` revolves around the creation and configuration of an `ApplicationToolkit` class. The data originates from the parameters provided to the `get_toolkit` method, which include `client`, `application_id`, `application_version_id`, `app_api_key`, and an optional list of `selected_tools`. These parameters are used to fetch application and version details from the `client` object. The fetched details are then used to configure an `AlitaChatModel` with specific settings such as `deployment`, `model`, `api_key`, `project_id`, `integration_uid`, `max_tokens`, `top_p`, `top_k`, and `temperature`. This configured model is then used to create an `Application` object, which is added to the `tools` list of the `ApplicationToolkit` class. The data flow can be summarized as follows: input parameters -> fetch details from client -> configure model -> create application -> add to toolkit.

Example:
```python
app_details = client.get_app_details(application_id)
version_details = client.get_app_version_details(application_id, application_version_id)
settings = {
    "deployment": client.base_url,
    "model": version_details['llm_settings']['model_name'],
    "api_key": app_api_key,
    "project_id": client.project_id,
    "integration_uid": version_details['llm_settings']['integration_uid'],
    "max_tokens": version_details['llm_settings']['max_tokens'],
    "top_p": version_details['llm_settings']['top_p'],
    "top_k": version_details['llm_settings']['top_k'],
    "temperature": version_details['llm_settings']['temperature'],
}
```

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. It includes fields for `client`, `application_id`, `application_version_id`, and `app_api_key`, each with specific types and descriptions.

### `get_toolkit`

This class method is responsible for creating and configuring an `ApplicationToolkit` instance. It takes parameters such as `client`, `application_id`, `application_version_id`, `app_api_key`, and an optional list of `selected_tools`. It fetches application and version details from the `client`, configures an `AlitaChatModel` with the fetched settings, creates an `Application` object, and returns an `ApplicationToolkit` instance with the created application added to its `tools` list.

### `get_tools`

This method returns the list of tools in the `ApplicationToolkit` instance.

## Dependencies Used and Their Descriptions

### `pydantic`

Used for creating and validating data models. The `create_model` and `BaseModel` are used to define the schema for the toolkit configuration.

### `langchain_community.agent_toolkits.base`

Provides the `BaseToolkit` class, which `ApplicationToolkit` inherits from.

### `langchain_core.tools`

Provides the `BaseTool` class, which is used as the type for the `tools` list in `ApplicationToolkit`.

### `..tools.application`

Imports `Application` and `applicationToolSchema`, which are used to create and configure the application tool.

### `..llms.alita`

Imports `AlitaChatModel`, which is used to configure the language model settings for the application.

## Functional Flow

1. **Initialization**: The `ApplicationToolkit` class is defined with a `tools` list and three methods: `toolkit_config_schema`, `get_toolkit`, and `get_tools`.
2. **Configuration Schema**: The `toolkit_config_schema` method defines the schema for the toolkit configuration using Pydantic.
3. **Toolkit Creation**: The `get_toolkit` method fetches application and version details from the `client`, configures an `AlitaChatModel` with the fetched settings, creates an `Application` object, and returns an `ApplicationToolkit` instance with the created application added to its `tools` list.
4. **Tool Retrieval**: The `get_tools` method returns the list of tools in the `ApplicationToolkit` instance.

## Endpoints Used/Created

No explicit endpoints are defined or used within this file. The `client` object is assumed to have methods for fetching application and version details, but these are not explicitly defined in this file.