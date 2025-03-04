# prompt.py

**Path:** `src/alita_sdk/toolkits/prompt.py`

## Data Flow

The data flow within `prompt.py` revolves around the creation and management of prompt tools within the `PromptToolkit` class. The data originates from the `client` and `prompts` parameters passed to the `get_toolkit` method. The `client` is expected to provide prompt configurations based on the `prompts` list, which contains pairs of `prompt_id` and `prompt_version_id`. These configurations are then used to create `Prompt` objects, which are stored in the `tools` attribute of the `PromptToolkit` instance.

For example, in the `get_toolkit` method:

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

In this snippet, the `client.prompt` method fetches the prompt configuration, which is then used to create a `Prompt` object. This object is appended to the `tools` list, which is eventually returned as part of the `PromptToolkit` instance. The data flow is thus from the `client` to the `PromptToolkit` via the `prompts` list, with intermediate transformations occurring in the creation of `Prompt` objects.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. It includes a single field, `prompts`, which is a list of lists containing `prompt_id` and `prompt_version_id` pairs. This schema is used to validate the configuration data passed to the toolkit.

### `get_toolkit`

This class method is responsible for creating an instance of `PromptToolkit`. It takes two parameters: `client` and `prompts`. The `client` is used to fetch prompt configurations based on the `prompts` list. Each prompt configuration is then used to create a `Prompt` object, which is added to the `tools` list. The method returns an instance of `PromptToolkit` with the `tools` list populated.

### `get_tools`

This instance method simply returns the `tools` attribute of the `PromptToolkit` instance. This attribute contains the list of `Prompt` objects created in the `get_toolkit` method.

## Dependencies Used and Their Descriptions

### `typing`

The `typing` module is used for type hinting. In this file, it is used to specify the types of the `tools` attribute and the parameters of the `get_toolkit` method.

### `pydantic`

The `pydantic` library is used for data validation and settings management. In this file, it is used to create a schema for the toolkit configuration using the `create_model` function and the `BaseModel` class.

### `langchain_community.agent_toolkits.base`

This module provides the `BaseToolkit` class, which `PromptToolkit` inherits from. It likely contains common functionality for all toolkits in the LangChain community.

### `langchain_core.tools`

This module provides the `BaseTool` class, which is used as the type for the `tools` attribute in `PromptToolkit`. It likely defines the basic interface for all tools in the LangChain core library.

### `..tools.prompt`

This module provides the `Prompt` class, which is used to create prompt tools. The `Prompt` class is instantiated with a name, description, prompt configuration, argument schema, and return type.

## Functional Flow

The functional flow of `prompt.py` begins with the definition of the `PromptToolkit` class, which inherits from `BaseToolkit`. The class has a single attribute, `tools`, which is a list of `BaseTool` objects. The `toolkit_config_schema` static method defines the schema for the toolkit configuration, while the `get_toolkit` class method is responsible for creating an instance of `PromptToolkit` with the appropriate tools. The `get_tools` instance method simply returns the `tools` attribute.

The flow is as follows:
1. The `PromptToolkit` class is defined.
2. The `toolkit_config_schema` static method is defined to return the configuration schema.
3. The `get_toolkit` class method is defined to create and return an instance of `PromptToolkit`.
4. The `get_tools` instance method is defined to return the `tools` attribute.

## Endpoints Used/Created

There are no explicit endpoints used or created in `prompt.py`. The file focuses on defining the `PromptToolkit` class and its methods for managing prompt tools.