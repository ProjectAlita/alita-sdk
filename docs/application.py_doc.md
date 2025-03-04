# application.py

**Path:** `src/alita_sdk/tools/application.py`

## Data Flow

The data flow within `application.py` begins with the importation of necessary modules and libraries, such as `json`, `RunnableConfig` from `langchain_core.runnables`, and various utilities and classes from other parts of the codebase. The primary data elements include the `task` and `chat_history`, which are encapsulated within the `applicationToolSchema` model. The `formulate_query` function processes these elements, transforming the `chat_history` into a suitable format based on its type (list of `BaseMessage`, dictionary, or string). The transformed data is then used as input for the `Application` class's `_run` method, which invokes the `application` with the formulated query and returns the response.

Example:
```python
applicationToolSchema = create_model(
    "applicatrionSchema", 
    task = (str, FieldInfo(description="Task for Application")), 
    chat_history = (Optional[list], FieldInfo(description="Chat History relevant for Application", default=[]))
)
```
This snippet shows the creation of the `applicationToolSchema` model, which defines the structure of the data elements used in the application.

## Functions Descriptions

### `formulate_query(kwargs)`

This function processes the input arguments (`kwargs`) to format the `chat_history` appropriately. It checks the type of the last element in `chat_history` and converts it to a list of `AIMessage` objects if necessary. The function returns a dictionary with the `task` and the formatted `chat_history`.

Example:
```python
if isinstance(kwargs.get('chat_history')[-1], BaseMessage):
    chat_history = convert_message_to_json(kwargs.get('chat_history')[:])
```
This snippet shows how the function checks the type of `chat_history` and converts it accordingly.

### `Application` Class

This class inherits from `BaseTool` and represents an application tool with attributes like `name`, `description`, `application`, `args_schema`, and `return_type`. The `_run` method invokes the application with the formulated query and returns the response based on the `return_type`.

Example:
```python
def _run(self, *args, **kwargs):
    response = self.application.invoke(formulate_query(kwargs))
    if self.return_type == "str":
        return response["output"]
    else:
        return {"messages": [{"role": "assistant", "content": response["output"]}]}
```
This snippet shows the `_run` method, which processes the input arguments, invokes the application, and returns the response.

## Dependencies Used and Their Descriptions

- `json`: Used for handling JSON data.
- `RunnableConfig` from `langchain_core.runnables`: Likely used for configuration purposes.
- `clean_string` from `..utils.utils`: Utility function for cleaning strings.
- `BaseTool` from `langchain_core.tools`: Base class for creating tools.
- `BaseMessage`, `AIMessage`, `ToolCall` from `langchain_core.messages`: Classes for handling messages and tool calls.
- `create_model`, `field_validator`, `BaseModel`, `FieldInfo` from `pydantic`: Used for creating and validating data models.
- `convert_message_to_json` from `..langchain.mixedAgentRenderes`: Utility function for converting messages to JSON format.
- `getLogger` from `logging`: Used for logging purposes.

## Functional Flow

1. **Imports and Schema Definition**: The file starts with importing necessary modules and defining the `applicationToolSchema` model.
2. **Query Formulation**: The `formulate_query` function processes the input arguments to format the `chat_history` and returns the formulated query.
3. **Application Class**: The `Application` class is defined with attributes and methods for running the application tool.
4. **Run Method**: The `_run` method of the `Application` class invokes the application with the formulated query and returns the response based on the `return_type`.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The primary focus is on processing input data and invoking the application tool with the formulated query.