# application.py

**Path:** `src/alita_sdk/tools/application.py`

## Data Flow

The data flow within `application.py` begins with the import of necessary modules and dependencies. The primary data elements are the `task` and `chat_history`, which are part of the `applicationToolSchema` model. The `formulate_query` function processes these elements, converting the `chat_history` into a suitable format based on its type (list of `BaseMessage`, dictionary, or string). The processed data is then used as input for the `Application` class's `_run` method, which invokes the `application` with the formulated query and returns the response. The data flow is straightforward, with data being transformed and passed through functions and methods to achieve the desired output.

Example:
```python
applicationToolSchema = create_model(
    "applicatrionSchema", 
    task = (str, FieldInfo(description="Task for Application")), 
    chat_history = (Optional[list], FieldInfo(description="Chat History relevant for Application", default=[]))
)
```
This snippet defines the schema for the input data, specifying the `task` and `chat_history` fields.

## Functions Descriptions

### `formulate_query(kwargs)`

This function processes the input arguments (`kwargs`) to format the `chat_history` appropriately. It checks the type of the last element in `chat_history` and converts it to a list of `AIMessage` objects if necessary. The function returns a dictionary with the `task` and the formatted `chat_history`.

Example:
```python
if isinstance(kwargs.get('chat_history')[-1], BaseMessage):
    chat_history = convert_message_to_json(kwargs.get('chat_history')[:])
```
This snippet checks if the last element in `chat_history` is a `BaseMessage` and converts it accordingly.

### `Application` Class

This class inherits from `BaseTool` and represents an application tool with attributes such as `name`, `description`, `application`, `args_schema`, and `return_type`. The `_run` method invokes the `application` with the formulated query and returns the response based on the `return_type`.

Example:
```python
response = self.application.invoke(formulate_query(kwargs))
if self.return_type == "str":
    return response["output"]
else:
    return {"messages": [{"role": "assistant", "content": response["output"]}]}
```
This snippet shows how the `_run` method processes the response from the `application` and returns it based on the `return_type`.

## Dependencies Used and Their Descriptions

- `json`: Used for handling JSON data.
- `langchain_core.runnables.RunnableConfig`: Configuration for runnable components.
- `..utils.utils.clean_string`: Utility function to clean strings.
- `langchain_core.tools.BaseTool`: Base class for tools.
- `langchain_core.messages.{BaseMessage, AIMessage, ToolCall}`: Message classes for handling chat messages.
- `pydantic.{create_model, field_validator, BaseModel, FieldInfo}`: Used for creating and validating data models.
- `..langchain.mixedAgentRenderes.convert_message_to_json`: Utility function to convert messages to JSON format.
- `logging.getLogger`: Used for logging.

## Functional Flow

1. **Import Dependencies**: The file starts by importing necessary modules and dependencies.
2. **Define Schema**: The `applicationToolSchema` model is defined to specify the structure of the input data.
3. **Formulate Query**: The `formulate_query` function processes the input arguments to format the `chat_history` appropriately.
4. **Application Class**: The `Application` class is defined with attributes and methods to represent an application tool.
5. **Run Method**: The `_run` method of the `Application` class invokes the `application` with the formulated query and returns the response based on the `return_type`.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The primary focus is on processing input data and invoking the `application` with the formulated query.