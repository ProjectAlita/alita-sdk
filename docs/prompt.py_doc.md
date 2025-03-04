# prompt.py

**Path:** `src/alita_sdk/toolkits/prompt.py`

## Data Flow

The data flow within `prompt.py` revolves around the creation and management of prompt tools using the `PromptToolkit` class. The data originates from the `client` object and a list of prompt configurations (`prompts`). Each prompt configuration is a list containing a prompt ID and a prompt version ID. The `get_toolkit` class method processes these configurations, retrieves the corresponding prompt objects from the client, and creates `Prompt` tools. These tools are then stored in the `tools` attribute of the `PromptToolkit` instance. The data flow can be summarized as follows:

1. **Input:** The `client` object and `prompts` list are provided as inputs to the `get_toolkit` method.
2. **Processing:** The method iterates over the `prompts` list, retrieves prompt objects from the client, and creates `Prompt` tools.
3. **Output:** The created `Prompt` tools are stored in the `tools` attribute of the `PromptToolkit` instance.

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
In this example, the `get_toolkit` method processes the `prompts` list, retrieves prompt objects from the client, and creates `Prompt` tools, which are then stored in the `tools` attribute.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. The schema includes a single field, `prompts`, which is a list of lists containing prompt IDs and prompt version IDs.

Example:
```python
@staticmethod
 def toolkit_config_schema() -> BaseModel:
 return create_model(
 "prompt",
 prompts = (list, FieldInfo(description="List of lists for [[prompt_id, prompt_version_id]]"))
 )
```
In this example, the `toolkit_config_schema` method creates and returns a Pydantic model with a single field, `prompts`.

### `get_toolkit`

This class method creates a `PromptToolkit` instance by processing the provided `client` object and `prompts` list. It retrieves prompt objects from the client, creates `Prompt` tools, and stores them in the `tools` attribute of the `PromptToolkit` instance.

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
In this example, the `get_toolkit` method processes the `prompts` list, retrieves prompt objects from the client, and creates `Prompt` tools, which are then stored in the `tools` attribute.

### `get_tools`

This method returns the list of `Prompt` tools stored in the `tools` attribute of the `PromptToolkit` instance.

Example:
```python
def get_tools(self):
 return self.tools
```
In this example, the `get_tools` method simply returns the list of `Prompt` tools stored in the `tools` attribute.

## Dependencies Used and Their Descriptions

### `typing`

The `typing` module is used to provide type hints for the function signatures and class attributes. In this file, it is used to specify the types of the `tools` attribute and the parameters of the `get_toolkit` method.

### `pydantic`

The `pydantic` module is used to create data models and perform data validation. In this file, it is used to create the schema for the toolkit configuration using the `create_model` function and the `BaseModel` class.

### `langchain_community.agent_toolkits.base`

The `BaseToolkit` class from the `langchain_community.agent_toolkits.base` module is used as the base class for the `PromptToolkit` class. It provides the basic structure and functionality for creating and managing toolkits.

### `langchain_core.tools`

The `BaseTool` class from the `langchain_core.tools` module is used as the base class for the `Prompt` tools created by the `PromptToolkit` class. It provides the basic structure and functionality for creating and managing tools.

### `..tools.prompt`

The `Prompt` class from the `..tools.prompt` module is used to create the `Prompt` tools. It provides the structure and functionality for creating and managing prompt tools.

## Functional Flow

The functional flow of `prompt.py` involves the creation and management of prompt tools using the `PromptToolkit` class. The process begins with the definition of the `PromptToolkit` class, which inherits from the `BaseToolkit` class. The `toolkit_config_schema` static method defines the schema for the toolkit configuration, and the `get_toolkit` class method processes the provided `client` object and `prompts` list to create `Prompt` tools. These tools are stored in the `tools` attribute of the `PromptToolkit` instance and can be retrieved using the `get_tools` method.

Example:
```python
class PromptToolkit(BaseToolkit):
 tools: List[BaseTool] = []
 
 @staticmethod
 def toolkit_config_schema() -> BaseModel:
 return create_model(
 "prompt",
 prompts = (list, FieldInfo(description="List of lists for [[prompt_id, prompt_version_id]]"))
 )
 
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
 
 def get_tools(self):
 return self.tools
```
In this example, the `PromptToolkit` class defines the structure and functionality for creating and managing prompt tools. The `toolkit_config_schema` method defines the schema for the toolkit configuration, the `get_toolkit` method processes the `client` object and `prompts` list to create `Prompt` tools, and the `get_tools` method returns the list of created tools.

## Endpoints Used/Created

There are no explicit endpoints used or created within the `prompt.py` file. The functionality is focused on creating and managing prompt tools using the `PromptToolkit` class and the provided `client` object and `prompts` list.