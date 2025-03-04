# application.py

**Path:** `src/alita_sdk/toolkits/application.py`

## Data Flow

The data flow within `application.py` revolves around the creation and configuration of an `ApplicationToolkit` class. The data originates from the parameters passed to the `get_toolkit` method, which include `client`, `application_id`, `application_version_id`, `app_api_key`, and `selected_tools`. These parameters are used to fetch application details and version details from the client. The fetched details are then used to configure an `AlitaChatModel` with settings such as `deployment`, `model`, `api_key`, `project_id`, `integration_uid`, `max_tokens`, `top_p`, `top_k`, and `temperature`. This configured model is then used to create an `Application` instance, which is added to the `tools` list of the `ApplicationToolkit` class. The data flow can be summarized as follows:

1. Input parameters are received by the `get_toolkit` method.
2. Application and version details are fetched from the client.
3. An `AlitaChatModel` is configured with the fetched details.
4. An `Application` instance is created using the configured model.
5. The `Application` instance is added to the `tools` list of the `ApplicationToolkit` class.

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

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. The schema includes fields for `application_id`, `application_version_id`, and `app_api_key`. The `application_id` and `application_version_id` are required integer fields, while `app_api_key` is an optional string field with a default value of `None`.

### `get_toolkit`

This class method is responsible for creating and configuring an `ApplicationToolkit` instance. It takes several parameters, including `client`, `application_id`, `application_version_id`, `app_api_key`, and `selected_tools`. The method fetches application and version details from the client, configures an `AlitaChatModel` with the fetched details, creates an `Application` instance using the configured model, and adds the `Application` instance to the `tools` list of the `ApplicationToolkit` class.

### `get_tools`

This method returns the list of tools in the `ApplicationToolkit` instance. It simply returns the `tools` attribute of the class, which contains the `Application` instance created in the `get_toolkit` method.

## Dependencies Used and Their Descriptions

### `pydantic`

The `pydantic` library is used to create a configuration schema for the toolkit. It provides the `create_model` and `BaseModel` classes, which are used to define the schema for the toolkit configuration.

### `langchain_community.agent_toolkits.base`

This module provides the `BaseToolkit` class, which is extended by the `ApplicationToolkit` class. The `BaseToolkit` class provides the basic structure and functionality for creating toolkits.

### `langchain_core.tools`

This module provides the `BaseTool` class, which is used as the type for the `tools` attribute in the `ApplicationToolkit` class. The `BaseTool` class defines the basic structure and functionality for tools in the toolkit.

### `..tools.application`

This module provides the `Application` class and the `applicationToolSchema`. The `Application` class is used to create instances of applications in the toolkit, and the `applicationToolSchema` defines the schema for the application tool.

### `..llms.alita`

This module provides the `AlitaChatModel` class, which is used to configure the application with settings such as `deployment`, `model`, `api_key`, `project_id`, `integration_uid`, `max_tokens`, `top_p`, `top_k`, and `temperature`.

## Functional Flow

The functional flow of `application.py` begins with the definition of the `ApplicationToolkit` class, which extends the `BaseToolkit` class. The `toolkit_config_schema` static method defines the configuration schema for the toolkit. The `get_toolkit` class method is responsible for creating and configuring an `ApplicationToolkit` instance. It fetches application and version details from the client, configures an `AlitaChatModel` with the fetched details, creates an `Application` instance using the configured model, and adds the `Application` instance to the `tools` list of the `ApplicationToolkit` class. The `get_tools` method returns the list of tools in the `ApplicationToolkit` instance.

## Endpoints Used/Created

There are no explicit endpoints defined or used within `application.py`. The functionality primarily revolves around creating and configuring an `ApplicationToolkit` instance using the provided parameters and client methods.