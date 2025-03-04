# artifact.py

**Path:** `src/alita_sdk/toolkits/artifact.py`

## Data Flow

The data flow within `artifact.py` revolves around the `ArtifactToolkit` class, which is designed to manage tools related to artifacts. The data originates from the `ArtifactWrapper` class, which provides available tools. These tools are then filtered and instantiated based on the user's selection. The data is transformed from a list of available tools into a list of instantiated `BaseAction` objects, which are then stored in the `tools` attribute of the `ArtifactToolkit` class. The data flow can be summarized as follows:

1. **Input:** The `get_toolkit` method receives `client`, `bucket`, and `selected_tools` as inputs.
2. **Processing:** The method initializes an `ArtifactWrapper` instance and retrieves available tools. It then filters these tools based on `selected_tools` and instantiates `BaseAction` objects for each selected tool.
3. **Output:** The instantiated `BaseAction` objects are stored in the `tools` attribute of the `ArtifactToolkit` class.

Example:
```python
@classmethod
 def get_toolkit(cls, client: Any, bucket: str, selected_tools: list[str] = []):
 if selected_tools is None:
 selected_tools = []
 tools = []
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
In this example, the `get_toolkit` method processes the input parameters, retrieves available tools, filters them, and stores the resulting `BaseAction` objects in the `tools` attribute.

## Functions Descriptions

### `toolkit_config_schema`

This static method generates a configuration schema for the toolkit. It retrieves available tools from the `ArtifactWrapper` and constructs a Pydantic model with the tool names and their argument schemas. The method returns a Pydantic model that includes metadata for the toolkit.

**Inputs:** None

**Processing:**
- Retrieves available tools from `ArtifactWrapper`.
- Constructs a Pydantic model with tool names and argument schemas.
- Adds metadata to the model.

**Outputs:** A Pydantic model representing the toolkit configuration schema.

Example:
```python
@staticmethod
 def toolkit_config_schema() -> BaseModel:
 selected_tools = {x['name']: x['args_schema'].schema() for x in ArtifactWrapper.model_construct().get_available_tools()}
 return create_model(
 "artifact",
 bucket = (str, FieldInfo(description="Bucket name")),
 selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
 __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Artifact", "icon_url": None}})
 )
```

### `get_toolkit`

This class method creates an instance of `ArtifactToolkit` with the selected tools. It initializes an `ArtifactWrapper` with the provided `client` and `bucket`, retrieves available tools, filters them based on `selected_tools`, and instantiates `BaseAction` objects for each selected tool.

**Inputs:**
- `client`: Any
- `bucket`: str
- `selected_tools`: list[str]

**Processing:**
- Initializes `ArtifactWrapper` with `client` and `bucket`.
- Retrieves available tools.
- Filters tools based on `selected_tools`.
- Instantiates `BaseAction` objects for each selected tool.

**Outputs:** An instance of `ArtifactToolkit` with the selected tools.

Example:
```python
@classmethod
 def get_toolkit(cls, client: Any, bucket: str, selected_tools: list[str] = []):
 if selected_tools is None:
 selected_tools = []
 tools = []
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

This method returns the list of tools stored in the `tools` attribute of the `ArtifactToolkit` instance.

**Inputs:** None

**Processing:** None

**Outputs:** A list of `BaseTool` objects.

Example:
```python
def get_tools(self):
 return self.tools
```

## Dependencies Used and Their Descriptions

### `List`, `Any`, `Literal` from `typing`

These are standard Python type hints used for type annotations. `List` is used to specify a list of items, `Any` is used for variables that can be of any type, and `Literal` is used to specify that a variable can only take on specific values.

### `BaseToolkit` from `langchain_community.agent_toolkits.base`

`BaseToolkit` is a base class for creating toolkits in the LangChain community. It provides a structure for defining and managing tools.

### `BaseTool` from `langchain_core.tools`

`BaseTool` is a base class for individual tools in the LangChain core library. It provides a structure for defining tool behavior and interactions.

### `create_model`, `BaseModel`, `ConfigDict`, `Field` from `pydantic`

These are components from the Pydantic library used for data validation and settings management. `create_model` is used to create dynamic models, `BaseModel` is the base class for all Pydantic models, `ConfigDict` is used for model configuration, and `Field` is used to define model fields.

### `FieldInfo` from `pydantic.fields`

`FieldInfo` is used to provide additional information about model fields, such as descriptions and default values.

### `ArtifactWrapper` from `..tools.artifact`

`ArtifactWrapper` is a class that provides methods for interacting with artifacts. It is used to retrieve available tools and manage artifact-related operations.

### `BaseAction` from `alita_tools.base.tool`

`BaseAction` is a class that represents an action or tool in the Alita tools library. It is used to define the behavior and interactions of individual tools.

## Functional Flow

The functional flow of `artifact.py` involves the following steps:

1. **Initialization:** The `ArtifactToolkit` class is defined with a `tools` attribute and three methods: `toolkit_config_schema`, `get_toolkit`, and `get_tools`.
2. **Configuration Schema Generation:** The `toolkit_config_schema` method generates a configuration schema for the toolkit by retrieving available tools from `ArtifactWrapper` and constructing a Pydantic model.
3. **Toolkit Creation:** The `get_toolkit` method creates an instance of `ArtifactToolkit` by initializing an `ArtifactWrapper`, retrieving available tools, filtering them based on `selected_tools`, and instantiating `BaseAction` objects for each selected tool.
4. **Tool Retrieval:** The `get_tools` method returns the list of tools stored in the `tools` attribute of the `ArtifactToolkit` instance.

Example:
```python
class ArtifactToolkit(BaseToolkit):
 tools: List[BaseTool] = []
 
 @staticmethod
 def toolkit_config_schema() -> BaseModel:
 selected_tools = {x['name']: x['args_schema'].schema() for x in ArtifactWrapper.model_construct().get_available_tools()}
 return create_model(
 "artifact",
 bucket = (str, FieldInfo(description="Bucket name")),
 selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
 __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Artifact", "icon_url": None}})
 )
 
 @classmethod
 def get_toolkit(cls, client: Any, bucket: str, selected_tools: list[str] = []):
 if selected_tools is None:
 selected_tools = []
 tools = []
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
 
 def get_tools(self):
 return self.tools
```

## Endpoints Used/Created

There are no explicit endpoints used or created in `artifact.py`. The file focuses on defining the `ArtifactToolkit` class and its methods for managing artifact-related tools.