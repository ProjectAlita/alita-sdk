# loop.py

**Path:** `src/alita_sdk/tools/loop.py`

## Data Flow

The data flow within `loop.py` is centered around the `LoopNode` class, which is designed to handle tool invocations in a loop. The data originates from the `state` parameter, which can be a string, dictionary, or `ToolCall` object. This state is used to extract input variables and context for the tool invocation. The `invoke` method processes this data, formats it into a prompt, and sends it to the `client` for completion. The response from the client is then processed and accumulated. The data flow involves multiple transformations, including formatting the input data, invoking the tool, and processing the tool's response. Intermediate variables such as `params`, `context`, `llm_input`, and `accumulated_response` are used to store and manipulate data throughout the process.

Example:
```python
params = convert_to_openai_tool(self.tool).get(
    'function', {'parameters': {}}).get(
    'parameters', {'properties': {}}).get('properties', {})
parameters = ''
for key in params.keys():
    parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
```
In this snippet, the `params` dictionary is populated with the tool's parameters, and the `parameters` string is constructed to include the parameter names, types, and descriptions.

## Functions Descriptions

### `process_response`

This function processes the response from the tool invocation. It takes three parameters: `response`, `return_type`, and `accumulated_response`. The function appends the response to the `accumulated_response` based on the `return_type`. If the `return_type` is a string, the response is appended as a string. If it is a dictionary, the response is appended to the `messages` key of the `accumulated_response`.

### `invoke`

The `invoke` method is the core function of the `LoopNode` class. It takes the `state`, an optional `config`, and additional keyword arguments. The method extracts input variables from the state, formats them into a prompt, and sends the prompt to the client for completion. The response is then processed and accumulated. The method handles various exceptions, including `ValidationError` and general exceptions, and logs the errors.

### `_run`

The `_run` method is a wrapper for the `invoke` method. It simply calls the `invoke` method with the provided arguments.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging information, errors, and debugging messages.

### `json`

Provides functions for working with JSON data, including `dumps` and `loads`.

### `langchain_core`

Includes various modules such as `callbacks`, `runnables`, `tools`, `messages`, and `utils` for handling tool invocations and processing responses.

### `pydantic`

Used for data validation and error handling with the `ValidationError` class.

### `openai`

Includes the `BadRequestError` class for handling errors related to OpenAI API requests.

### `traceback`

Provides the `format_exc` function for formatting exception tracebacks.

## Functional Flow

The functional flow of `loop.py` begins with the instantiation of the `LoopNode` class. The `invoke` method is called with the `state` and optional `config`. The method extracts input variables from the state, formats them into a prompt, and sends the prompt to the client for completion. The response is processed and accumulated, and any errors are logged. The `_run` method serves as a wrapper for the `invoke` method, allowing it to be called with the provided arguments.

## Endpoints Used/Created

No explicit endpoints are defined or called within `loop.py`. The functionality revolves around invoking tools and processing their responses within the `LoopNode` class.