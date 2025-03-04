# loop_output.py

**Path:** `src/alita_sdk/tools/loop_output.py`

## Data Flow

The data flow within `loop_output.py` revolves around the `LoopToolNode` class, which is designed to handle tool invocations in a loop. The data originates from the `state` parameter, which can be a string, dictionary, or `ToolCall` object. This state is processed to extract input variables and the last user message. The input data is then formatted into a prompt and passed to a language model client for processing. The response from the client is parsed and used to invoke the specified tool. The tool's output is further processed and can be looped back as input for subsequent tool invocations. Temporary storage is used for intermediate variables like `input`, `last_message`, and `accumulated_response`.

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
This snippet shows how input variables are extracted from the state and prepared for processing.

## Functions Descriptions

### `invoke`

The `invoke` function is the core of the `LoopToolNode` class. It processes the input state, formats it into a prompt, and sends it to a language model client. The response is parsed and used to invoke the specified tool. The function handles both structured and unstructured outputs and includes error handling for validation and general exceptions.

**Inputs:**
- `state`: Union[str, dict, ToolCall]
- `config`: Optional[RunnableConfig]
- `kwargs`: Any additional arguments

**Outputs:**
- Returns the tool's output or an error message in case of exceptions.

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
except ValidationError:
    logger.error(f"ValidationError: {format_exc()}")
    return {
        "messages": [{"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {result} raised ValidationError. 
\n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
{input[-1].content}"""}]}
```
This snippet shows the invocation of the tool and error handling.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information and errors.
- `json.dumps`: Used for converting Python objects to JSON strings.
- `traceback.format_exc`: Used for formatting exception tracebacks.
- `langchain_core.callbacks.dispatch_custom_event`: Used for dispatching custom events.
- `langchain_core.runnables.RunnableConfig`: Configuration for runnables.
- `langchain_core.tools.BaseTool`: Base class for tools.
- `langchain_core.messages.HumanMessage`: Represents a human message.
- `langchain_core.utils.function_calling.convert_to_openai_tool`: Converts a tool to an OpenAI-compatible format.
- `pydantic.ValidationError`: Exception raised for validation errors.

These dependencies are crucial for the functionality of the `LoopToolNode` class, providing logging, JSON handling, exception formatting, and integration with the LangChain framework.

## Functional Flow

The functional flow of `loop_output.py` starts with the instantiation of the `LoopToolNode` class. The `invoke` method is called with the input state, which is processed to extract input variables and the last user message. This data is formatted into a prompt and sent to a language model client. The response is parsed and used to invoke the specified tool. The tool's output is processed and can be looped back as input for subsequent tool invocations. Error handling is implemented to manage validation and general exceptions.

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
This snippet shows the creation of the prompt and invocation of the language model client.

## Endpoints Used/Created

The `loop_output.py` file does not explicitly define or call any endpoints. However, it interacts with a language model client, which could be an endpoint depending on the implementation of the `client` object. The specifics of this interaction are abstracted away in the provided code.