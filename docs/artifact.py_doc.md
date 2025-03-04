# artifact.py

**Path:** `src/alita_sdk/toolkits/artifact.py`

## Data Flow

The data flow within `artifact.py` revolves around the `ArtifactToolkit` class, which is designed to manage tools related to artifacts. The data originates from the `ArtifactWrapper` class, which provides available tools. These tools are then filtered and instantiated based on the user's selection. The data is transformed from a list of available tools into a list of instantiated `BaseAction` objects, which are then stored in the `tools` attribute of the `ArtifactToolkit` class. The data flow can be summarized as follows:

1. **Origin:** The data originates from the `ArtifactWrapper` class, which provides a list of available tools.
2. **Transformation:** The list of available tools is filtered based on the user's selection and instantiated as `BaseAction` objects.
3. **Destination:** The instantiated `BaseAction` objects are stored in the `tools` attribute of the `ArtifactToolkit` class.

Example:
```python
available_tools = artifact_wrapper.get_available_tools()
for tool in available_tools:
    if selected_tools:
        if tool["name"] not in selected_tools:
            continue
    tools.append(BaseAction(
        api_wrapper=artifact_wrapper,
        name=tool["name"],
        description=tool["description"],
        args_schema=tool["args_schema"]
    ))
```
In this example, the `available_tools` list is filtered based on the `selected_tools` list, and the resulting tools are instantiated as `BaseAction` objects and appended to the `tools` list.

## Functions Descriptions

### `toolkit_config_schema`

This static method generates a configuration schema for the toolkit. It retrieves the available tools from the `ArtifactWrapper` class and creates a Pydantic model with the necessary fields and metadata.

- **Inputs:** None
- **Processing:** Retrieves available tools, creates a Pydantic model with fields for bucket name and selected tools.
- **Outputs:** Returns a Pydantic model representing the configuration schema.

Example:
```python
selected_tools = {x['name']: x['args_schema'].schema() for x in ArtifactWrapper.model_construct().get_available_tools()}
return create_model(
    "artifact",
    bucket = (str, FieldInfo(description="Bucket name")),
    selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
    __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Artifact", "icon_url": None}})
)
```

### `get_toolkit`

This class method creates an instance of `ArtifactToolkit` with the selected tools. It initializes the `ArtifactWrapper` with the provided client and bucket, retrieves the available tools, filters them based on the selected tools, and instantiates them as `BaseAction` objects.

- **Inputs:** `client` (Any), `bucket` (str), `selected_tools` (list[str])
- **Processing:** Initializes `ArtifactWrapper`, retrieves available tools, filters and instantiates selected tools as `BaseAction` objects.
- **Outputs:** Returns an instance of `ArtifactToolkit` with the selected tools.

Example:
```python
artifact_wrapper = ArtifactWrapper(client=client, bucket=bucket)
available_tools = artifact_wrapper.get_available_tools()
for tool in available_tools:
    if selected_tools:
        if tool["name"] not in selected_tools:
            continue
    tools.append(BaseAction(
        api_wrapper=artifact_wrapper,
        name=tool["name"],
        description=tool["description"],
        args_schema=tool["args_schema"]
    ))
return cls(tools=tools)
```

### `get_tools`

This instance method returns the list of tools stored in the `tools` attribute of the `ArtifactToolkit` instance.

- **Inputs:** None
- **Processing:** None
- **Outputs:** Returns the list of tools.

Example:
```python
def get_tools(self):
    return self.tools
```

## Dependencies Used and Their Descriptions

### `List`, `Any`, `Literal` from `typing`

These are standard Python typing annotations used to specify the types of variables and function parameters.

### `BaseToolkit` from `langchain_community.agent_toolkits.base`

This is the base class for creating toolkits in the LangChain community. It provides the foundational structure for the `ArtifactToolkit` class.

### `BaseTool` from `langchain_core.tools`

This is the base class for creating tools in the LangChain core library. It is used as the type for the `tools` attribute in the `ArtifactToolkit` class.

### `create_model`, `BaseModel`, `ConfigDict`, `Field` from `pydantic`

These are utilities from the Pydantic library used to create and manage data models. They are used to create the configuration schema for the toolkit.

### `FieldInfo` from `pydantic.fields`

This is a utility from the Pydantic library used to provide metadata for fields in a data model.

### `ArtifactWrapper` from `..tools.artifact`

This is a wrapper class for managing artifacts. It provides methods to retrieve available tools and interact with the artifact storage.

### `BaseAction` from `alita_tools.base.tool`

This is the base class for creating actions in the Alita tools library. It is used to instantiate the selected tools in the `get_toolkit` method.

## Functional Flow

The functional flow of `artifact.py` involves the following steps:

1. **Initialization:** The `ArtifactToolkit` class is initialized with an empty list of tools.
2. **Configuration Schema Generation:** The `toolkit_config_schema` method generates a configuration schema for the toolkit.
3. **Toolkit Creation:** The `get_toolkit` method creates an instance of `ArtifactToolkit` with the selected tools.
4. **Tool Retrieval:** The `get_tools` method returns the list of tools stored in the `tools` attribute.

Example:
```python
# Step 1: Initialization
artifact_toolkit = ArtifactToolkit()

# Step 2: Configuration Schema Generation
config_schema = artifact_toolkit.toolkit_config_schema()

# Step 3: Toolkit Creation
artifact_toolkit_instance = ArtifactToolkit.get_toolkit(client, bucket, selected_tools)

# Step 4: Tool Retrieval
tools = artifact_toolkit_instance.get_tools()
```

## Endpoints Used/Created

There are no explicit endpoints used or created in `artifact.py`. The functionality is focused on managing tools related to artifacts within the `ArtifactToolkit` class.