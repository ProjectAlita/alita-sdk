# loop_output.py

**Path:** `src/alita_sdk/tools/loop_output.py`

## Data Flow

The data flow within `loop_output.py` revolves around the `LoopToolNode` class, which is designed to handle tool invocations in a loop. The data originates from the state, which can be a string, dictionary, or `ToolCall` object. This state is processed to extract input variables and the last user message. The input is then formatted into a prompt and passed to a language model client for completion. The response from the client is parsed and used to invoke the specified tool. The tool's output is then processed and potentially used as input for another tool in the loop. The final accumulated response is returned as the output.

Example:
```python
input = []
last_message = {}
for var in self.input_variables:
    if 'messages' in self.input_variables:
        messages = state.get('messages', [])[:]
        input = messages[:-1]
        last_message["user_input"] = messages[-1].content
    else:
        last_message[var] = state[var]
```
In this snippet, the input variables are extracted from the state, and the last user message is identified for further processing.

## Functions Descriptions

### `invoke`

The `invoke` function is the core of the `LoopToolNode` class. It processes the state and input variables, formats the input for the language model, and handles the tool invocation and response processing.

- **Parameters:**
  - `state`: The current state, which can be a string, dictionary, or `ToolCall` object.
  - `config`: Optional configuration for the `RunnableConfig`.
  - `**kwargs`: Additional keyword arguments.
- **Returns:** The final accumulated response after processing the tool's output.

Example:
```python
completion = self.client.invoke(input, config=config)
result = _extract_json(completion.content.strip())
tool_result = self.tool.run(result, config=config)
```
In this snippet, the input is passed to the client for completion, the result is extracted and used to invoke the tool, and the tool's output is processed.

### `_run`

The `_run` function is a wrapper for the `invoke` function, allowing it to be called with positional and keyword arguments.

- **Parameters:**
  - `*args`: Positional arguments.
  - `**kwargs`: Keyword arguments.
- **Returns:** The result of the `invoke` function.

Example:
```python
def _run(self, *args, **kwargs):
    return self.invoke(**kwargs)
```
In this snippet, the `_run` function simply calls the `invoke` function with the provided keyword arguments.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information and errors.
- `json.dumps`: Used for formatting JSON data.
- `traceback.format_exc`: Used for formatting exception tracebacks.
- `langchain_core.callbacks.dispatch_custom_event`: Used for dispatching custom events.
- `langchain_core.runnables.RunnableConfig`: Used for configuration of runnables.
- `langchain_core.tools.BaseTool`: Base class for tools.
- `langchain_core.messages.HumanMessage`: Represents a human message.
- `langchain_core.messages.ToolCall`: Represents a tool call.
- `langchain_core.utils.function_calling.convert_to_openai_tool`: Converts a tool to an OpenAI tool.
- `pydantic.ValidationError`: Used for handling validation errors.

## Functional Flow

The functional flow of `loop_output.py` involves the following steps:

1. **Initialization:** The `LoopToolNode` class is initialized with the necessary attributes, including the tool, client, and input/output variables.
2. **Invoke Function:** The `invoke` function is called with the current state and configuration. It processes the input variables and formats the input for the language model.
3. **Client Invocation:** The formatted input is passed to the language model client for completion. The response is parsed and used to invoke the specified tool.
4. **Tool Invocation:** The tool is invoked with the parsed response, and the tool's output is processed.
5. **Loop Processing:** If the tool is part of a loop, the output is used as input for the next tool in the loop. The final accumulated response is returned.

Example:
```python
completion = self.client.invoke(input, config=config)
result = _extract_json(completion.content.strip())
tool_result = self.tool.run(result, config=config)
accumulated_response = process_response(tool_run, self.return_type, accumulated_response)
```
In this snippet, the client is invoked with the input, the result is extracted and used to run the tool, and the tool's output is processed and accumulated.

## Endpoints Used/Created

The `loop_output.py` file does not explicitly define or call any endpoints. The primary focus is on processing input and invoking tools within a loop. The interaction with external systems is handled through the language model client and the tools being invoked.