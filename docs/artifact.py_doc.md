# artifact.py

**Path:** `src/alita_sdk/toolkits/artifact.py`

## Data Flow

The data flow within `artifact.py` revolves around the `ArtifactToolkit` class, which is designed to manage tools related to artifacts. The data originates from the parameters passed to the `get_toolkit` method, specifically the `client`, `bucket`, and `selected_tools`. The `client` parameter is expected to be an object that can interact with artifacts, while `bucket` is a string representing the storage location, and `selected_tools` is a list of tool names to be used.

Within the `get_toolkit` method, the `client` object is used to access the artifact in the specified `bucket`. The method then iterates over the available `artifact_tools`, filtering them based on the `selected_tools` list. Each selected tool is instantiated with the artifact and added to the `tools` list, which is then used to create an instance of `ArtifactToolkit`.

Here is a code snippet illustrating the key data transformation:

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

In this snippet, the `client` object retrieves the artifact from the `bucket`, and the `tools` list is populated with the selected tools, demonstrating the flow of data from input parameters to the final toolkit instance.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. It includes fields for `client`, `bucket`, and `selected_tools`, each with specific types and descriptions. The `client` field is marked as required and is expected to be autopopulated.

### `get_toolkit`

This class method is responsible for creating an instance of `ArtifactToolkit`. It takes three parameters: `client`, `bucket`, and `selected_tools`. The method retrieves the artifact from the specified `bucket` using the `client` object and filters the available tools based on the `selected_tools` list. It then instantiates the selected tools with the artifact and returns an `ArtifactToolkit` instance containing these tools.

### `get_tools`

This instance method simply returns the list of tools contained within the `ArtifactToolkit` instance. It does not take any parameters and directly accesses the `tools` attribute of the instance.

## Dependencies Used and Their Descriptions

- `List`, `Any` from `typing`: Used for type annotations to specify the expected types of variables and function parameters.
- `BaseToolkit` from `langchain_community.agent_toolkits.base`: The base class that `ArtifactToolkit` extends, providing common functionality for toolkits.
- `BaseTool` from `langchain_core.tools`: The base class for individual tools that can be included in the toolkit.
- `create_model`, `BaseModel` from `pydantic`: Used to create and define the schema for the toolkit configuration.
- `FieldInfo` from `pydantic.fields`: Used to provide additional metadata for fields in the Pydantic model.
- `artifact_tools` from `..tools.artifact`: A list of available artifact tools that can be included in the toolkit.

## Functional Flow

The functional flow of `artifact.py` begins with the definition of the `ArtifactToolkit` class, which includes the `toolkit_config_schema`, `get_toolkit`, and `get_tools` methods. The primary entry point is the `get_toolkit` method, which is called to create an instance of `ArtifactToolkit` with the specified parameters.

1. The `get_toolkit` method is called with `client`, `bucket`, and `selected_tools` parameters.
2. The method retrieves the artifact from the specified `bucket` using the `client` object.
3. It iterates over the available `artifact_tools`, filtering them based on the `selected_tools` list.
4. Each selected tool is instantiated with the artifact and added to the `tools` list.
5. An instance of `ArtifactToolkit` is created with the populated `tools` list and returned.
6. The `get_tools` method can be called on the `ArtifactToolkit` instance to retrieve the list of tools.

## Endpoints Used/Created

The `artifact.py` file does not explicitly define or call any endpoints. The interactions are primarily with the `client` object, which is expected to provide access to artifacts stored in a specified `bucket`. The exact nature of these interactions would depend on the implementation of the `client` object, which is not detailed in this file.