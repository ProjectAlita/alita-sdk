# prompt.py

**Path:** `src/alita_sdk/toolkits/prompt.py`

## Data Flow

The data flow within `prompt.py` revolves around the creation and management of tools within the `PromptToolkit` class. The data originates from the parameters passed to the `get_toolkit` method, specifically the `client` object and the `prompts` list. The `prompts` list contains configurations for each prompt, which are used to retrieve prompt objects from the `client`. These prompt objects are then transformed into `Prompt` tools, which are stored in the `tools` attribute of the `PromptToolkit` class. The data flow can be summarized as follows:

1. **Input Parameters:** The `get_toolkit` method receives `client` and `prompts` as input parameters.
2. **Prompt Retrieval:** For each prompt configuration in the `prompts` list, the corresponding prompt object is retrieved from the `client`.
3. **Tool Creation:** Each retrieved prompt object is used to create a `Prompt` tool, which includes setting its name, description, prompt, argument schema, and return type.
4. **Tool Storage:** The created `Prompt` tools are stored in the `tools` attribute of the `PromptToolkit` class.
5. **Output:** The `get_toolkit` method returns an instance of `PromptToolkit` with the created tools.

Example:
```python
@classmethod
 def get_toolkit(cls, client: Any, prompts: list[list[int, int]]):
 tools = []
 for prompt_config in prompts:
 prmt = client.prompt(prompt_config[0], prompt_config[1], return_tool=True)
 tools.append(Prompt(
 name=prmt.name, description=prmt.description, 
 prompt=prmt, args_schema=prmt.create_pydantic_model(),
 return_type='str'))
 return cls(tools=tools)
```
In this example, the `get_toolkit` method processes the `prompts` list, retrieves prompt objects from the `client`, and creates `Prompt` tools, which are then stored in the `tools` attribute.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. The schema includes two fields: `client` and `prompts`. The `client` field is required and is described as a client object, while the `prompts` field is a list of lists containing prompt IDs and prompt version IDs.

Example:
```python
@staticmethod
 def toolkit_config_schema() -> BaseModel:
 return create_model(
 "prompt",
 client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
 prompts = (list, FieldInfo(description="List of lists for [[prompt_id, prompt_version_id]]"))
 )
```
In this example, the `toolkit_config_schema` method creates and returns a Pydantic model with the specified fields and descriptions.

### `get_toolkit`

This class method is responsible for creating an instance of `PromptToolkit` with the specified tools. It takes two parameters: `client` and `prompts`. The method iterates over the `prompts` list, retrieves the corresponding prompt objects from the `client`, and creates `Prompt` tools. These tools are then stored in the `tools` attribute of the `PromptToolkit` class.

Example:
```python
@classmethod
 def get_toolkit(cls, client: Any, prompts: list[list[int, int]]):
 tools = []
 for prompt_config in prompts:
 prmt = client.prompt(prompt_config[0], prompt_config[1], return_tool=True)
 tools.append(Prompt(
 name=prmt.name, description=prmt.description, 
 prompt=prmt, args_schema=prmt.create_pydantic_model(),
 return_type='str'))
 return cls(tools=tools)
```
In this example, the `get_toolkit` method processes the `prompts` list, retrieves prompt objects from the `client`, and creates `Prompt` tools, which are then stored in the `tools` attribute.

### `get_tools`

This method returns the list of tools stored in the `tools` attribute of the `PromptToolkit` class.

Example:
```python
def get_tools(self):
 return self.tools
```
In this example, the `get_tools` method simply returns the `tools` attribute, which contains the list of created `Prompt` tools.

## Dependencies Used and Their Descriptions

### `typing`

The `typing` module is used to provide type hints for the parameters and return types of the methods in the `PromptToolkit` class. Specifically, `List` and `Any` are imported to define the types of the `tools` attribute and the input parameters of the methods.

### `pydantic`

The `pydantic` module is used to create and manage data models. The `create_model` function and `BaseModel` class are used to define the schema for the toolkit configuration. The `FieldInfo` class is used to provide additional information about the fields in the schema.

### `langchain_community.agent_toolkits.base`

The `BaseToolkit` class is imported from this module and is used as the base class for `PromptToolkit`. This inheritance allows `PromptToolkit` to leverage the functionality provided by `BaseToolkit`.

### `langchain_core.tools`

The `BaseTool` class is imported from this module and is used as the type for the `tools` attribute in the `PromptToolkit` class. This ensures that all tools in the `tools` list are instances of `BaseTool`.

### `..tools.prompt`

The `Prompt` class is imported from this module and is used to create `Prompt` tools. Each `Prompt` tool is initialized with a name, description, prompt object, argument schema, and return type.

## Functional Flow

The functional flow of `prompt.py` involves the creation and management of `Prompt` tools within the `PromptToolkit` class. The process begins with the definition of the toolkit configuration schema using the `toolkit_config_schema` method. The `get_toolkit` method is then used to create an instance of `PromptToolkit` with the specified tools. This method retrieves prompt objects from the `client` based on the configurations in the `prompts` list and creates `Prompt` tools. These tools are stored in the `tools` attribute of the `PromptToolkit` class. Finally, the `get_tools` method can be used to retrieve the list of created tools.

Example:
1. Define the toolkit configuration schema:
```python
@staticmethod
 def toolkit_config_schema() -> BaseModel:
 return create_model(
 "prompt",
 client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
 prompts = (list, FieldInfo(description="List of lists for [[prompt_id, prompt_version_id]]"))
 )
```
2. Create an instance of `PromptToolkit` with the specified tools:
```python
@classmethod
 def get_toolkit(cls, client: Any, prompts: list[list[int, int]]):
 tools = []
 for prompt_config in prompts:
 prmt = client.prompt(prompt_config[0], prompt_config[1], return_tool=True)
 tools.append(Prompt(
 name=prmt.name, description=prmt.description, 
 prompt=prmt, args_schema=prmt.create_pydantic_model(),
 return_type='str'))
 return cls(tools=tools)
```
3. Retrieve the list of created tools:
```python
def get_tools(self):
 return self.tools
```

## Endpoints Used/Created

The `prompt.py` file does not explicitly define or call any endpoints. The functionality is focused on creating and managing `Prompt` tools within the `PromptToolkit` class. The interaction with the `client` object to retrieve prompt objects is abstracted and not explicitly defined within the file.