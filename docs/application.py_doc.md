# application.py

**Path:** `src/alita_sdk/tools/application.py`

## Data Flow

The data flow within `application.py` begins with the importation of necessary modules and libraries, such as `json`, `RunnableConfig` from `langchain_core.runnables`, and various utilities and classes from other modules. The primary data elements include the `task` and `chat_history`, which are defined in the `applicationToolSchema` model. These elements are manipulated within the `formulate_query` function and the `Application` class.

The `formulate_query` function processes the `kwargs` dictionary to extract and format the `chat_history` and `task`. The `chat_history` can be a list of `BaseMessage` objects, dictionaries, or strings, and is converted accordingly. The function returns a dictionary containing the `input` (task) and the formatted `chat_history`.

In the `Application` class, the `_run` method invokes the `application` with the query formulated by `formulate_query`. The response is then processed based on the `return_type` attribute, which can be either a string or a dictionary containing messages.

Example:
```python
class Application(BaseTool):
    name: str
    description: str
    application: Any
    args_schema: Type[BaseModel] = applicationToolSchema
    return_type: str = "str"
    
    def _run(self, *args, **kwargs):
        response = self.application.invoke(formulate_query(kwargs))
        if self.return_type == "str":
            return response["output"]
        else:
            return {"messages": [{"role": "assistant", "content": response["output"]}]}
```
This snippet shows how the `_run` method processes the response from the `application` and formats it based on the `return_type`.

## Functions Descriptions

### `formulate_query`

The `formulate_query` function is responsible for processing the `kwargs` dictionary to extract and format the `chat_history` and `task`. It handles different types of `chat_history` (list of `BaseMessage` objects, dictionaries, or strings) and converts them into a consistent format. The function returns a dictionary containing the `input` (task) and the formatted `chat_history`.

**Inputs:**
- `kwargs`: A dictionary containing the `task` and `chat_history`.

**Outputs:**
- A dictionary with `input` and `chat_history` keys.

Example:
```python
def formulate_query(kwargs):
    chat_history = []
    if kwargs.get('chat_history'):
        if isinstance(kwargs.get('chat_history')[-1], BaseMessage):
            chat_history = convert_message_to_json(kwargs.get('chat_history')[:])
        elif isinstance(kwargs.get('chat_history')[-1], dict):
            if all([True if message.get('role') and message.get('content') else False for message in kwargs.get('chat_history')]):
                chat_history = kwargs.get('chat_history')[:]
            else:
                for each in kwargs.get('chat_history')[:]:
                    chat_history.append(AIMessage(json.dumps(each)))
        elif isinstance(kwargs.get('chat_history')[-1], str):
            chat_history = []
            for each in kwargs.get('chat_history')[:]:
                chat_history.append(AIMessage(each))
    return {"input": kwargs.get('task'), "chat_history": chat_history}
```
This snippet shows the `formulate_query` function handling different types of `chat_history` and returning the formatted query.

### `Application` Class

The `Application` class inherits from `BaseTool` and represents a tool that can be used to run applications with specific tasks and chat history. It defines the schema for the arguments (`args_schema`) and the return type (`return_type`). The `_run` method is responsible for invoking the application with the formulated query and processing the response.

**Attributes:**
- `name`: The name of the application.
- `description`: A description of the application.
- `application`: The application to be invoked.
- `args_schema`: The schema for the arguments, defined as `applicationToolSchema`.
- `return_type`: The return type of the response, either `str` or a dictionary containing messages.

**Methods:**
- `_run`: Invokes the application with the formulated query and processes the response.

Example:
```python
class Application(BaseTool):
    name: str
    description: str
    application: Any
    args_schema: Type[BaseModel] = applicationToolSchema
    return_type: str = "str"
    
    def _run(self, *args, **kwargs):
        response = self.application.invoke(formulate_query(kwargs))
        if self.return_type == "str":
            return response["output"]
        else:
            return {"messages": [{"role": "assistant", "content": response["output"]}]}
```
This snippet shows the `Application` class and its `_run` method, which processes the response from the application.

## Dependencies Used and Their Descriptions

### `json`

The `json` module is used for encoding and decoding JSON data. In this file, it is used to convert dictionaries to JSON strings and vice versa.

### `RunnableConfig` from `langchain_core.runnables`

`RunnableConfig` is imported from `langchain_core.runnables`, but it is not used in the provided code snippet. It is likely intended for configuring runnable tasks in the application.

### `clean_string` from `..utils.utils`

The `clean_string` function is imported from the `utils` module and is used to remove spaces from the `name` attribute in the `Application` class.

### `BaseTool` from `langchain_core.tools`

`BaseTool` is a base class for creating tools in the LangChain framework. The `Application` class inherits from `BaseTool` to define a custom tool.

### `BaseMessage`, `AIMessage`, `ToolCall` from `langchain_core.messages`

These classes are used for handling messages in the LangChain framework. `BaseMessage` is a base class for messages, `AIMessage` represents messages from an AI, and `ToolCall` represents a call to a tool.

### `create_model`, `field_validator`, `BaseModel` from `pydantic`

These functions and classes are used for creating and validating data models. `create_model` is used to create the `applicationToolSchema` model, `field_validator` is used to define a validator for the `name` attribute, and `BaseModel` is the base class for data models.

### `convert_message_to_json` from `..langchain.mixedAgentRenderes`

The `convert_message_to_json` function is used to convert `BaseMessage` objects to JSON format.

### `getLogger` from `logging`

The `getLogger` function is used to create a logger for logging messages in the application.

## Functional Flow

1. **Import Modules and Libraries:** The file begins by importing necessary modules and libraries, such as `json`, `RunnableConfig`, and various utilities and classes from other modules.
2. **Define `applicationToolSchema`:** A Pydantic model is created to define the schema for the `task` and `chat_history` arguments.
3. **Define `formulate_query` Function:** This function processes the `kwargs` dictionary to extract and format the `chat_history` and `task`.
4. **Define `Application` Class:** The `Application` class inherits from `BaseTool` and represents a tool that can be used to run applications with specific tasks and chat history. It defines the schema for the arguments (`args_schema`) and the return type (`return_type`).
5. **Define `_run` Method:** The `_run` method in the `Application` class invokes the application with the formulated query and processes the response based on the `return_type` attribute.

## Endpoints Used/Created

No explicit endpoints are defined or used within the provided code snippet. The functionality appears to be focused on processing tasks and chat history within the application, rather than interacting with external endpoints.
