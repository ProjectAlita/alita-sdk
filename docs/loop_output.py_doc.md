# loop_output.py

**Path:** `src/alita_sdk/tools/loop_output.py`

## Data Flow

The data flow within `loop_output.py` revolves around the `LoopToolNode` class, which is designed to handle the invocation of tools in a looped manner. The data originates from the `state` parameter, which can be a string, dictionary, or `ToolCall` object. This state is processed to extract input variables and the last user message. The input is then formatted into a prompt and passed to the client for invocation. The response from the client is processed to extract JSON data, which is then used to invoke the specified tool. The tool's result is further processed and potentially passed to a loop tool for additional processing. The final accumulated response is returned as the output.

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

The `invoke` function is the core of the `LoopToolNode` class. It processes the input state, formats it into a prompt, and invokes the client to get a response. The response is then used to invoke the specified tool, and the tool's result is processed and potentially passed to a loop tool for additional processing. The function handles various exceptions, including `ValidationError` and general exceptions, logging errors and returning appropriate responses.

Example:
```python
try:
    tool_result = self.tool.invoke(result, config=config, kwargs=kwargs)
    dispatch_custom_event(
        "on_loop_tool_node", {
            "input_variables": self.input_variables,
            "tool_result": tool_result,
            "state": state,
        }, config=config
    )
```
This snippet shows the invocation of the specified tool and the dispatching of a custom event with the tool's result.

### `_run`

The `_run` function is a simple wrapper that calls the `invoke` function with the provided arguments.

Example:
```python
def _run(self, *args, **kwargs):
    return self.invoke(**kwargs)
```
This snippet shows the straightforward implementation of the `_run` function.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information, errors, and debugging messages.
- `json.dumps`: Used for converting Python objects to JSON strings.
- `traceback.format_exc`: Used for formatting exception tracebacks.
- `langchain_core.callbacks.dispatch_custom_event`: Used for dispatching custom events.
- `langchain_core.runnables.RunnableConfig`: Used for configuring runnable objects.
- `langchain_core.tools.BaseTool`: Base class for tools.
- `langchain_core.messages.HumanMessage`: Represents a human message.
- `langchain_core.messages.ToolCall`: Represents a tool call.
- `langchain_core.utils.function_calling.convert_to_openai_tool`: Converts a tool to an OpenAI tool.
- `pydantic.ValidationError`: Exception raised for validation errors.

## Functional Flow

The functional flow of `loop_output.py` starts with the invocation of the `invoke` function. The input state is processed to extract input variables and the last user message. The input is formatted into a prompt and passed to the client for invocation. The response from the client is processed to extract JSON data, which is then used to invoke the specified tool. The tool's result is further processed and potentially passed to a loop tool for additional processing. The final accumulated response is returned as the output. The `_run` function serves as a simple wrapper for the `invoke` function.

Example:
```python
input += [
    HumanMessage(self.prompt.format(
        tool_name=self.tool.name,
        tool_description=self.tool.description,
        schema=parameters,
        last_message=dumps(last_message)))
]
completion = self.client.invoke(input, config=config)
result = _extract_json(completion.content.strip())
```
This snippet shows the formatting of the input into a prompt and the invocation of the client to get a response.

## Endpoints Used/Created

No explicit endpoints are defined or called within `loop_output.py`. The functionality revolves around invoking tools and processing their responses within the `LoopToolNode` class.