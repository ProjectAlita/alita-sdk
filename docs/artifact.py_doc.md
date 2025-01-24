# artifact.py

**Path:** `src/alita_sdk/toolkits/artifact.py`

## Data Flow

The data flow within `artifact.py` revolves around the creation and configuration of an `ArtifactToolkit` class. The data originates from the parameters passed to the `get_toolkit` method, which include a `client` object, a `bucket` name, and an optional list of `selected_tools`. These inputs are used to configure the toolkit and instantiate the necessary tools.

The `client` object is used to create an `artifact` instance associated with the specified `bucket`. The `selected_tools` list determines which tools from the `artifact_tools` module are included in the toolkit. The data is transformed as it passes through the `get_toolkit` method, where the `artifact` instance is used to initialize each tool, and the tools are collected into a list that is assigned to the `tools` attribute of the `ArtifactToolkit` instance.

Example:
```python
artifact = client.artifact(bucket)
tools = []
for tool in artifact_tools:
    if selected_tools:
        if tool['name'] not in selected_tools:
            continue
    tools.append(tool['tool'](artifact=artifact))
return cls(tools=tools)
```
In this example, the `artifact` instance is created using the `client` and `bucket` parameters. The `tools` list is populated with tool instances that are initialized with the `artifact` instance.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. The schema includes fields for the `client` object, `bucket` name, and `selected_tools` list. The `client` field is required and is automatically populated, while the `bucket` and `selected_tools` fields have default values.

Example:
```python
@staticmethod
def toolkit_config_schema() -> BaseModel:
    return create_model(
        "artifact",
        client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
        bucket = (str, FieldInfo(description="Bucket name")),
        selected_tools = (list, FieldInfo(description="List of selected tools", default=[list(tool.keys())[0] for tool in artifact_tools]))
    )
```
This method defines the configuration schema for the toolkit, specifying the required and optional fields.

### `get_toolkit`

This class method creates and returns an instance of `ArtifactToolkit`. It takes three parameters: `client`, `bucket`, and `selected_tools`. The method initializes an `artifact` instance using the `client` and `bucket` parameters, and then iterates over the `artifact_tools` to create tool instances based on the `selected_tools` list. The tools are collected into a list and used to instantiate the `ArtifactToolkit`.

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
This method demonstrates how the toolkit is configured and instantiated based on the provided parameters.

### `get_tools`

This instance method returns the list of tools associated with the `ArtifactToolkit` instance. It does not take any parameters and simply returns the `tools` attribute.

Example:
```python
def get_tools(self):
    return self.tools
```
This method provides access to the tools that have been configured for the toolkit.

## Dependencies Used and Their Descriptions

### `typing`

The `typing` module is used to specify type hints for the `List` and `Any` types. This helps with type checking and code readability.

### `langchain_community.agent_toolkits.base`

The `BaseToolkit` class is imported from this module and serves as the base class for `ArtifactToolkit`. It provides common functionality for toolkits.

### `langchain_core.tools`

The `BaseTool` class is imported from this module and is used as the base class for individual tools in the toolkit. It defines the common interface and behavior for tools.

### `pydantic`

The `pydantic` module is used to create the configuration schema for the toolkit. The `create_model` function and `BaseModel` class are used to define the schema, and the `FieldInfo` class is used to specify field metadata.

### `..tools.artifact`

The `artifact_tools` list is imported from this module and contains the definitions of the available tools. These tools are used to populate the `tools` attribute of the `ArtifactToolkit`.

## Functional Flow

1. **Toolkit Configuration Schema**: The `toolkit_config_schema` method defines the configuration schema for the toolkit, specifying the required and optional fields.
2. **Toolkit Initialization**: The `get_toolkit` method is called with the `client`, `bucket`, and `selected_tools` parameters. It initializes an `artifact` instance and iterates over the `artifact_tools` to create tool instances based on the `selected_tools` list.
3. **Tool Collection**: The tools are collected into a list and used to instantiate the `ArtifactToolkit`.
4. **Tool Access**: The `get_tools` method provides access to the tools that have been configured for the toolkit.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The functionality is focused on configuring and instantiating a toolkit with a set of tools based on the provided parameters.