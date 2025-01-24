# loop.py

**Path:** `src/alita_sdk/tools/loop.py`

## Data Flow

The data flow within `loop.py` revolves around the `LoopNode` class, which is designed to handle tool invocations in a loop. The data originates from the `state` parameter, which can be a string, dictionary, or `ToolCall` object. This state is processed to extract input variables and context, which are then used to formulate a prompt for the language model (LLM). The LLM generates a list of JSON objects representing tool call arguments, which are then iterated over to invoke the specified tool. The responses from these tool invocations are accumulated and processed based on the specified return type (`str` or `dict`). The final accumulated response is then dispatched as a custom event.

Example:
```python
params = convert_to_openai_tool(self.tool).get(
    'function', {'parameters': {}}).get(
    'parameters', {'properties': {}}).get('properties', {})
parameters = ''
for key in params.keys():
    parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
```
*This snippet shows how the tool parameters are extracted and formatted for inclusion in the LLM prompt.*

## Functions Descriptions

### `process_response`

This function processes the response from a tool invocation. It appends the response to the accumulated response based on the specified return type. If the return type is `str`, the response is appended as a string. If the return type is `dict`, the response is appended to the last message's content in the accumulated response.

**Inputs:**
- `response`: The response from the tool invocation.
- `return_type`: The specified return type (`str` or `dict`).
- `accumulated_response`: The accumulated response so far.

**Outputs:**
- The updated accumulated response.

### `LoopNode`

This class represents a loop node for tool invocations. It inherits from `BaseTool` and includes several attributes such as `name`, `description`, `client`, `tool`, `task`, `output_variables`, `input_variables`, `return_type`, and `prompt`. The main method, `invoke`, handles the tool invocation loop, processing the state to generate tool call arguments, invoking the tool, and accumulating the responses.

**Inputs:**
- `state`: The current state, which can be a string, dictionary, or `ToolCall` object.
- `config`: Optional configuration for the invocation.
- `kwargs`: Additional keyword arguments.

**Outputs:**
- The accumulated response from the tool invocations.

Example:
```python
completion = self.client.invoke(predict_input, config=config)
loop_data = _old_extract_json(completion.content.strip())
if self.return_type == "str":
    accumulated_response = ''
else:
    accumulated_response = {"messages": [{"role": "assistant", "content": ""}]}
```
*This snippet shows how the LLM completion is processed and the initial accumulated response is set based on the return type.*

## Dependencies Used and Their Descriptions

### `logging`

Used for logging information, errors, and debugging messages throughout the code.

### `json`

Provides functions to serialize and deserialize JSON data (`dumps` and `loads`).

### `langchain_core`

Includes several modules such as `callbacks`, `runnables`, `tools`, `messages`, and `utils` for handling various aspects of the tool invocation and LLM interaction.

### `pydantic`

Used for data validation and settings management through the `ValidationError` exception.

### `openai`

Includes the `BadRequestError` exception for handling errors related to OpenAI API requests.

### `traceback`

Provides the `format_exc` function to format stack traces for logging exceptions.

## Functional Flow

1. **Initialization:** The `LoopNode` class is initialized with attributes such as `name`, `description`, `client`, `tool`, `task`, `output_variables`, `input_variables`, `return_type`, and `prompt`.
2. **Invoke Method:** The `invoke` method is called with the current state, optional configuration, and additional keyword arguments.
3. **Parameter Extraction:** The tool parameters are extracted and formatted for inclusion in the LLM prompt.
4. **Context and Input Variables:** The context and input variables are processed from the state.
5. **LLM Invocation:** The LLM is invoked with the formatted prompt to generate a list of JSON objects representing tool call arguments.
6. **Tool Invocation Loop:** The tool is invoked for each JSON object in the list, and the responses are accumulated.
7. **Response Processing:** The responses are processed based on the specified return type and accumulated.
8. **Custom Event Dispatch:** The final accumulated response is dispatched as a custom event.

Example:
```python
predict_input = llm_input[:] + [
    HumanMessage(self.prompt.format(
        tool_name=self.tool.name,
        tool_description=self.tool.description,
        context=context,
        schema=parameters,
        task=self.task))]
completion = self.client.invoke(predict_input, config=config)
loop_data = _old_extract_json(completion.content.strip())
```
*This snippet shows the LLM invocation and extraction of JSON data from the completion content.*

## Endpoints Used/Created

No explicit endpoints are defined or called within this file. The interactions are primarily with the LLM client and tool invocations.