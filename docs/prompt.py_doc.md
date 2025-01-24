# prompt.py

**Path:** `src/alita_sdk/toolkits/prompt.py`

## Data Flow

The data flow within `prompt.py` revolves around the creation and management of prompt tools using the `PromptToolkit` class. The data originates from the `client` object and a list of prompt configurations (`prompts`). These configurations are passed to the `get_toolkit` class method, which iterates over each prompt configuration, retrieves the corresponding prompt from the client, and creates a `Prompt` object. These `Prompt` objects are then stored in the `tools` attribute of the `PromptToolkit` instance. The data flow can be summarized as follows:

1. **Input Data:** The `client` object and `prompts` list are provided as inputs.
2. **Processing:** The `get_toolkit` method processes each prompt configuration, retrieves the prompt from the client, and creates a `Prompt` object.
3. **Output Data:** The `Prompt` objects are stored in the `tools` attribute of the `PromptToolkit` instance.

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
In this example, the `get_toolkit` method processes the `prompts` list, retrieves each prompt from the `client`, and creates a `Prompt` object, which is then added to the `tools` list.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. It includes two fields: `client` and `prompts`. The `client` field is of type `Any` and is required, while the `prompts` field is a list of lists containing prompt IDs and prompt version IDs.

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
In this example, the `toolkit_config_schema` method creates a Pydantic model with the specified fields and their descriptions.

### `get_toolkit`

This class method takes a `client` object and a list of prompt configurations (`prompts`). It iterates over the `prompts` list, retrieves each prompt from the `client`, and creates a `Prompt` object. These `Prompt` objects are then stored in the `tools` attribute of the `PromptToolkit` instance.

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
In this example, the `get_toolkit` method processes the `prompts` list, retrieves each prompt from the `client`, and creates a `Prompt` object, which is then added to the `tools` list.

### `get_tools`

This instance method returns the list of `Prompt` objects stored in the `tools` attribute of the `PromptToolkit` instance.

Example:
```python
def get_tools(self):
 return self.tools
```
In this example, the `get_tools` method simply returns the `tools` attribute, which contains the list of `Prompt` objects.

## Dependencies Used and Their Descriptions

### `typing`

The `typing` module is used to provide type hints for the `List` and `Any` types. This helps in defining the expected types for function parameters and return values.

### `pydantic`

The `pydantic` library is used to create data models and perform data validation. In this file, it is used to create a Pydantic `BaseModel` for the toolkit configuration schema.

### `langchain_community.agent_toolkits.base`

This module provides the `BaseToolkit` class, which is the base class for the `PromptToolkit` class. It provides common functionality for toolkits.

### `langchain_core.tools`

This module provides the `BaseTool` class, which is used as the type for the `tools` attribute in the `PromptToolkit` class.

### `..tools.prompt`

This module provides the `Prompt` class, which is used to create `Prompt` objects that are added to the `tools` attribute in the `PromptToolkit` class.

## Functional Flow

1. **Initialization:** The `PromptToolkit` class is initialized with an empty list of `tools`.
2. **Configuration Schema:** The `toolkit_config_schema` static method is called to create a Pydantic model for the toolkit configuration schema.
3. **Toolkit Creation:** The `get_toolkit` class method is called with a `client` object and a list of prompt configurations (`prompts`). It processes each prompt configuration, retrieves the prompt from the `client`, and creates a `Prompt` object, which is added to the `tools` list.
4. **Retrieve Tools:** The `get_tools` instance method is called to retrieve the list of `Prompt` objects stored in the `tools` attribute.

## Endpoints Used/Created

There are no explicit endpoints used or created in this file. The functionality revolves around creating and managing prompt tools using the `PromptToolkit` class.