# artifact.py

**Path:** `src/alita_sdk/toolkits/artifact.py`

## Data Flow

The data flow within the `artifact.py` file revolves around the `ArtifactToolkit` class, which is designed to manage tools related to artifacts. The data originates from the parameters passed to the class methods, such as `client`, `bucket`, and `selected_tools`. These parameters are used to configure and instantiate tools that interact with an artifact storage system. The data is transformed as it passes through the methods, particularly in the `get_toolkit` method, where the `client` and `bucket` parameters are used to create an artifact object, and the `selected_tools` parameter filters the tools to be included in the toolkit. The final destination of the data is the `tools` attribute of the `ArtifactToolkit` instance, which holds the configured tools.

Example:
```python
@classmethod
 def get_toolkit(cls, client: Any, bucket: str, selected_tools: list[str] = []):
 if selected_tools is None:
 selected_tools = []
 artifact = client.artifact(bucket)
 tools = []
 for tool in artifact_tools:
 if selected_tools:
 if tool['name'] not in selected_tools:
 continue
 tools.append(tool['tool'](artifact=artifact))
 return cls(tools=tools)
```
In this example, the `get_toolkit` method takes `client`, `bucket`, and `selected_tools` as inputs, creates an artifact object, filters the tools based on `selected_tools`, and returns an instance of `ArtifactToolkit` with the configured tools.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. It includes fields for `client`, `bucket`, and `selected_tools`, with appropriate descriptions and default values.

### `get_toolkit`

This class method creates and returns an instance of `ArtifactToolkit`. It takes `client`, `bucket`, and `selected_tools` as parameters, creates an artifact object using the `client` and `bucket`, filters the tools based on `selected_tools`, and returns the configured toolkit.

### `get_tools`

This instance method returns the list of tools configured in the `ArtifactToolkit` instance.

## Dependencies Used and Their Descriptions

- `List`, `Any` from `typing`: Used for type annotations.
- `BaseToolkit` from `langchain_community.agent_toolkits.base`: The base class for `ArtifactToolkit`.
- `BaseTool` from `langchain_core.tools`: The base class for tools managed by `ArtifactToolkit`.
- `create_model`, `BaseModel` from `pydantic`: Used to create the configuration schema for the toolkit.
- `FieldInfo` from `pydantic.fields`: Used to provide metadata for the fields in the configuration schema.
- `artifact_tools` from `..tools.artifact`: A list of available artifact tools.

## Functional Flow

1. The `ArtifactToolkit` class is defined, inheriting from `BaseToolkit`.
2. The `toolkit_config_schema` static method is defined to return the configuration schema.
3. The `get_toolkit` class method is defined to create and return an instance of `ArtifactToolkit` with the configured tools.
4. The `get_tools` instance method is defined to return the list of tools in the toolkit.

## Endpoints Used/Created

No explicit endpoints are defined or used within this file. The functionality revolves around configuring and managing tools related to artifacts.