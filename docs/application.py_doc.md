# application.py

**Path:** `src/alita_sdk/tools/application.py`

## Data Flow

The data flow within `application.py` revolves around the `Application` class and its methods. The primary data elements are the `task` and `chat_history`, which are encapsulated in the `applicationToolSchema` model. The `formulate_query` function processes these elements, converting the `chat_history` into a suitable format based on its type (list of `BaseMessage`, dictionary, or string). The processed data is then passed to the `application.invoke` method within the `_run` function of the `Application` class. The response from this invocation is either returned as a string or as a dictionary containing messages.

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
In this snippet, the `_run` method demonstrates the flow of data from the input arguments through the `formulate_query` function to the `application.invoke` method, and finally to the output.

## Functions Descriptions

### `formulate_query`

This function processes the input arguments to prepare a query for the application. It handles different types of `chat_history` (list of `BaseMessage`, dictionary, or string) and converts them into a suitable format for the application.

**Inputs:**
- `kwargs`: A dictionary containing `task` and `chat_history`.

**Processing Logic:**
- Checks the type of `chat_history` and processes it accordingly.
- Converts `chat_history` to JSON if it is a list of `BaseMessage`.
- Converts each message to `AIMessage` if `chat_history` is a dictionary or string.

**Outputs:**
- A dictionary with `input` as the task and `chat_history` as the processed chat history.

### `Application` Class

This class represents a tool that can run an application with a given task and chat history. It uses the `applicationToolSchema` for input validation and processes the input using the `formulate_query` function.

**Attributes:**
- `name`: The name of the application.
- `description`: A description of the application.
- `application`: The application instance to be invoked.
- `args_schema`: The schema for input arguments.
- `return_type`: The type of the return value (default is `str`).

**Methods:**
- `_run`: Invokes the application with the processed input and returns the response.

## Dependencies Used and Their Descriptions

### `langchain_core`

- `RunnableConfig`, `BaseTool`, `BaseMessage`, `AIMessage`, `ToolCall`: These are core components from the `langchain_core` library used for defining and running the application tool.

### `pydantic`

- `create_model`, `field_validator`, `BaseModel`, `FieldInfo`: These are used for creating and validating the input schema for the application tool.

### `utils`

- `clean_string`: A utility function for cleaning strings, used in the `name` field validator.

### `logging`

- `getLogger`: Used for logging within the module.

## Functional Flow

1. **Initialization:** The `Application` class is initialized with the necessary attributes (`name`, `description`, `application`, etc.).
2. **Input Processing:** The `_run` method processes the input arguments using the `formulate_query` function.
3. **Application Invocation:** The processed input is passed to the `application.invoke` method.
4. **Response Handling:** The response from the application is returned as a string or a dictionary containing messages, based on the `return_type` attribute.

## Endpoints Used/Created

There are no explicit endpoints defined or used within this file. The functionality is encapsulated within the `Application` class and its methods.