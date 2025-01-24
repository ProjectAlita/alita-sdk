# loop_output.py

**Path:** `src/alita_sdk/tools/loop_output.py`

## Data Flow

The data flow within `loop_output.py` revolves around the `LoopToolNode` class, which is designed to handle tool invocations in a loop. The data originates from the state, which can be a string, dictionary, or `ToolCall` object. This state is processed to extract input variables and the last user message. The input is then formatted into a prompt and passed to a language model client for completion. The response from the client is parsed, and the tool is invoked with the parsed result. The tool's output is then processed and potentially passed to another tool in a loop. The final accumulated response is returned as the output. Temporary storage is used for input variables, last messages, and accumulated responses.

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
This snippet shows how input variables and the last message are extracted from the state.

## Functions Descriptions

### `invoke`

The `invoke` function is the core of the `LoopToolNode` class. It processes the state to extract input variables and the last user message, formats them into a prompt, and passes them to a language model client for completion. The response is parsed, and the tool is invoked with the parsed result. The tool's output is processed and potentially passed to another tool in a loop. The final accumulated response is returned as the output.

Inputs:
- `state`: Union[str, dict, ToolCall]
- `config`: Optional[RunnableConfig]
- `kwargs`: Any

Outputs:
- `Any`: The final accumulated response.

Example:
```python
completion = self.client.invoke(input, config=config)
result = _extract_json(completion.content.strip())
tool_result = self.tool.run(result, config=config)
```
This snippet shows how the client is invoked, the response is parsed, and the tool is run with the parsed result.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information, errors, and debugging messages.
- `json.dumps`: Used for converting Python objects to JSON strings.
- `traceback.format_exc`: Used for formatting exception tracebacks.
- `langchain_core.callbacks.dispatch_custom_event`: Used for dispatching custom events.
- `langchain_core.runnables.RunnableConfig`: Used for configuring runnables.
- `langchain_core.tools.BaseTool`: Base class for tools.
- `langchain_core.messages.HumanMessage`: Represents a human message.
- `langchain_core.messages.ToolCall`: Represents a tool call.
- `langchain_core.utils.function_calling.convert_to_openai_tool`: Converts a tool to an OpenAI tool.
- `pydantic.ValidationError`: Used for handling validation errors.

## Functional Flow

The functional flow of `loop_output.py` starts with the invocation of the `invoke` function. The state is processed to extract input variables and the last user message. These are formatted into a prompt and passed to a language model client for completion. The response is parsed, and the tool is invoked with the parsed result. The tool's output is processed and potentially passed to another tool in a loop. The final accumulated response is returned as the output. Error handling is implemented to catch and log validation errors and other exceptions.

Example:
```python
try:
    tool_result = self.tool.run(result, config=config)
    dispatch_custom_event(
        "on_loop_tool_node", {
            "input_variables": self.input_variables,
            "tool_result": tool_result,
            "state": state,
        }, config=config
    )
except ValidationError:
    logger.error(f"ValidationError: {format_exc()}")
```
This snippet shows how the tool is run, custom events are dispatched, and errors are handled.

## Endpoints Used/Created

No explicit endpoints are defined or called within `loop_output.py`. The functionality is focused on processing input and invoking tools in a loop.