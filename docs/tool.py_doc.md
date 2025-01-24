# tool.py

**Path:** `src/alita_sdk/tools/tool.py`

## Data Flow

The data flow within `tool.py` revolves around the `ToolNode` class, which is designed to handle tool invocations. The data originates from the `state` parameter, which can be a string, dictionary, or `ToolCall` object. This state is processed to extract input variables and the last user message. The `invoke` method then formats these inputs into a prompt for the tool, which is passed to the language model client (`self.client`). The client processes the input and returns a result, which is then used to run the tool (`self.tool.run`). The output is formatted and returned, either as a message or as specified output variables.

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
This snippet shows how input variables are extracted from the state and prepared for the tool invocation.

## Functions Descriptions

### `invoke`

The `invoke` method is the core function of the `ToolNode` class. It takes the current state, configuration, and additional keyword arguments. It extracts parameters for the tool, formats the input, and invokes the language model client. The result is processed and used to run the tool, and the output is formatted and returned.

- **Inputs:** `state` (str, dict, or ToolCall), `config` (optional RunnableConfig), `kwargs` (additional arguments)
- **Processing:** Extracts parameters, formats input, invokes client, processes result, runs tool
- **Outputs:** Formatted result (message or specified output variables)

Example:
```python
completion = self.client.invoke(input, config=config)
result = _extract_json(completion.content.strip())
tool_result = self.tool.run(result, config=config)
```
This snippet shows the invocation of the client and processing of the result.

### `_run`

The `_run` method is a wrapper for the `invoke` method, allowing it to be called with positional and keyword arguments.

- **Inputs:** `args` (positional arguments), `kwargs` (keyword arguments)
- **Processing:** Calls `invoke` with `kwargs`
- **Outputs:** Result of `invoke`

Example:
```python
def _run(self, *args, **kwargs):
    return self.invoke(**kwargs)
```
This snippet shows the simple wrapper function.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information and errors.
- `json.dumps`: Used for converting Python objects to JSON strings.
- `traceback.format_exc`: Used for formatting exception tracebacks.
- `langchain_core.callbacks.dispatch_custom_event`: Used for dispatching custom events.
- `langchain_core.runnables.RunnableConfig`: Configuration for runnables.
- `langchain_core.tools.BaseTool`: Base class for tools.
- `typing.Any`, `Optional`, `Union`: Type hints for function signatures.
- `langchain_core.messages.HumanMessage`, `ToolCall`: Message and tool call classes.
- `..langchain.utils._extract_json`, `create_pydantic_model`: Utility functions for JSON extraction and model creation.
- `langchain_core.utils.function_calling.convert_to_openai_tool`: Converts tools to OpenAI format.
- `pydantic.ValidationError`: Exception class for validation errors.

## Functional Flow

The functional flow of `tool.py` starts with the instantiation of the `ToolNode` class, which sets up the tool's configuration. The `invoke` method is called with the current state and configuration, extracting input variables and formatting them into a prompt. The prompt is passed to the language model client, which processes it and returns a result. The result is used to run the tool, and the output is formatted and returned.

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
tool_result = self.tool.run(result, config=config)
```
This snippet shows the flow from input formatting to tool invocation and result processing.

## Endpoints Used/Created

No explicit endpoints are defined or called within `tool.py`. The functionality is focused on processing inputs and invoking tools through the language model client.