# application.py

**Path:** `src/alita_sdk/toolkits/application.py`

## Data Flow

The data flow within `application.py` revolves around the creation and configuration of an `ApplicationToolkit` class. The data originates from the parameters passed to the `get_toolkit` method, which include `client`, `application_id`, `application_version_id`, and `app_api_key`. These parameters are used to fetch application details and version details from the client. The fetched details are then used to configure an `AlitaChatModel` with specific settings. This model is subsequently used to create an `Application` instance, which is added to the `tools` list of the `ApplicationToolkit` class. The data flow can be summarized as follows:

1. Input parameters are received by the `get_toolkit` method.
2. Application and version details are fetched from the client.
3. An `AlitaChatModel` is configured using the fetched details.
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
app = client.application(AlitaChatModel(**settings), application_id, application_version_id)
```

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. The schema includes fields for `client`, `application_id`, `application_version_id`, and `app_api_key`, each with specific descriptions and requirements.

### `get_toolkit`

This class method is responsible for creating and configuring an `ApplicationToolkit` instance. It takes parameters such as `client`, `application_id`, `application_version_id`, `app_api_key`, and an optional `selected_tools` list. The method fetches application and version details from the client, configures an `AlitaChatModel` with the fetched details, creates an `Application` instance, and adds it to the `tools` list of the `ApplicationToolkit` class.

### `get_tools`

This method returns the list of tools associated with the `ApplicationToolkit` instance. In this case, it returns the `tools` list containing the `Application` instance created in the `get_toolkit` method.

## Dependencies Used and Their Descriptions

### `pydantic`

- **Purpose:** Used for creating and validating data models.
- **Usage:** The `create_model` function and `BaseModel` class from Pydantic are used to define the schema for the toolkit configuration.

### `langchain_community.agent_toolkits.base`

- **Purpose:** Provides the base class for creating toolkits.
- **Usage:** The `BaseToolkit` class is extended to create the `ApplicationToolkit` class.

### `langchain_core.tools`

- **Purpose:** Provides the base class for creating tools.
- **Usage:** The `BaseTool` class is used as the type for the `tools` list in the `ApplicationToolkit` class.

### `..tools.application`

- **Purpose:** Provides the `Application` class and `applicationToolSchema` used in the toolkit.
- **Usage:** The `Application` class is instantiated and added to the `tools` list, and `applicationToolSchema` is used as the schema for the `Application` instance.

### `..llms.alita`

- **Purpose:** Provides the `AlitaChatModel` class used for creating the application model.
- **Usage:** The `AlitaChatModel` class is instantiated with specific settings and used to create the `Application` instance.

## Functional Flow

1. The `ApplicationToolkit` class is defined, extending the `BaseToolkit` class.
2. The `toolkit_config_schema` static method is defined to return the configuration schema.
3. The `get_toolkit` class method is defined to create and configure an `ApplicationToolkit` instance.
4. The `get_tools` method is defined to return the list of tools associated with the `ApplicationToolkit` instance.
5. When `get_toolkit` is called, it fetches application and version details, configures an `AlitaChatModel`, creates an `Application` instance, and adds it to the `tools` list.
6. The `get_tools` method can be called to retrieve the list of tools, which includes the `Application` instance.

## Endpoints Used/Created

The `application.py` file does not explicitly define or call any endpoints. However, it interacts with a `client` object that is expected to have methods for fetching application details (`get_app_details`) and version details (`get_app_version_details`). These methods are assumed to make API calls to retrieve the necessary information.