# loop.py

**Path:** `src/alita_sdk/tools/loop.py`

## Data Flow

The data flow within `loop.py` revolves around the `LoopNode` class, which is designed to handle tool invocations in a loop. The data originates from the `state` parameter, which can be a string, dictionary, or `ToolCall` object. This state is processed to extract input variables and context, which are then used to generate a prompt for the language model (LLM). The LLM's response is parsed into JSON, which is used to invoke the specified tool. The tool's response is accumulated and processed based on the specified return type. The final accumulated response is then dispatched as a custom event.

Example:
```python
params = convert_to_openai_tool(self.tool).get(
    'function', {'parameters': {}}).get(
    'parameters', {'properties': {}}).get('properties', {})
parameters = ''
for key in params.keys():
    parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
```
In this snippet, the parameters for the tool are extracted and formatted into a string, which is later used in the prompt for the LLM.

## Functions Descriptions

### `process_response`

This function processes the response from the tool based on the specified return type. It appends the response to the accumulated response, either as a string or as part of a dictionary.

**Inputs:**
- `response`: The response from the tool.
- `return_type`: The type of the return value (either `str` or `dict`).
- `accumulated_response`: The accumulated response so far.

**Outputs:**
- The updated accumulated response.

Example:
```python
if return_type == "str":
    accumulated_response += f'{response}\n\n'
else:
    if isinstance(response, str):
        accumulated_response['messages'][-1]["content"] += f'{response}\n\n'
```
This snippet shows how the response is appended to the accumulated response based on the return type.

### `invoke`

This method is the core of the `LoopNode` class. It generates the prompt for the LLM, invokes the LLM, parses the response, and invokes the tool with the parsed response. It also handles exceptions and accumulates the tool's responses.

**Inputs:**
- `state`: The current state, which can be a string, dictionary, or `ToolCall` object.
- `config`: Optional configuration for the LLM.
- `kwargs`: Additional keyword arguments.

**Outputs:**
- The accumulated response from the tool invocations.

Example:
```python
completion = self.client.invoke(predict_input, config=config)
loop_data = _old_extract_json(completion.content.strip())
```
This snippet shows how the LLM is invoked and its response is parsed into JSON.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging information, errors, and debugging messages.

### `json.dumps` and `json.loads`

Used for converting Python objects to JSON strings and vice versa.

### `langchain_core`

Contains various modules and functions used for handling tool invocations, messages, and custom events.

### `pydantic.ValidationError`

Used for handling validation errors when invoking tools.

### `openai.BadRequestError`

Used for handling bad request errors from the OpenAI API.

### `traceback.format_exc`

Used for formatting exception tracebacks for logging.

## Functional Flow

1. **Initialization:** The `LoopNode` class is initialized with various attributes like `name`, `description`, `client`, `tool`, `task`, `output_variables`, `input_variables`, `return_type`, and `prompt`.
2. **Invoke Method:** The `invoke` method is called with the current state and optional configuration.
3. **Parameter Extraction:** The parameters for the tool are extracted and formatted into a string.
4. **Context and Input Variables:** The context and input variables are extracted from the state.
5. **Prompt Generation:** A prompt is generated for the LLM using the extracted parameters, context, and task.
6. **LLM Invocation:** The LLM is invoked with the generated prompt, and its response is parsed into JSON.
7. **Tool Invocation:** The tool is invoked with the parsed JSON response, and its response is accumulated.
8. **Exception Handling:** Validation errors and other exceptions are caught and logged, and appropriate error messages are added to the accumulated response.
9. **Custom Event Dispatch:** The final accumulated response is dispatched as a custom event.

## Endpoints Used/Created

No explicit endpoints are defined or used within this file. The interactions are primarily with the LLM client and the tool being invoked.