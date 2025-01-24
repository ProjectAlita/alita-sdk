# tool.py

**Path:** `src/alita_sdk/tools/tool.py`

## Data Flow

The data flow within `tool.py` revolves around the `ToolNode` class, which is designed to handle the invocation of tools within the Alita SDK framework. The data originates from the state, which can be a string, dictionary, or `ToolCall` object. This state is processed to extract input variables and the last user message. The data is then formatted into a prompt and passed to the client for further processing. The client generates a completion, which is either structured or unstructured, based on the `ToolNode` configuration. The result is then used to run the tool, and the final output is returned. Intermediate variables such as `params`, `struct_params`, `input`, and `last_message` are used to store and manipulate data during this process.

Example:
```python
params = convert_to_openai_tool(self.tool).get(
    'function', {'parameters': {}}).get(
    'parameters', {'properties': {}}).get('properties', {})
parameters = ''
struct_params = {}
for key in params.keys():
    parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
    struct_params[key] = {"type": params[key].get('type', 'str'),
                          "description": params[key].get('description', '')}
```
This snippet shows how the parameters for the tool are extracted and formatted.

## Functions Descriptions

### `invoke`

The `invoke` function is the core function of the `ToolNode` class. It takes the state, configuration, and additional keyword arguments as inputs. The function extracts parameters for the tool, formats the input variables, and generates a prompt. It then invokes the client to get a completion, which is processed to extract the result. The result is used to run the tool, and the final output is returned. The function handles both structured and unstructured outputs and includes error handling for validation errors.

### `_run`

The `_run` function is a wrapper for the `invoke` function. It simply calls `invoke` with the provided keyword arguments.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information and errors.
- `json.dumps`: Used for converting Python objects to JSON strings.
- `traceback.format_exc`: Used for formatting exception tracebacks.
- `langchain_core.callbacks.dispatch_custom_event`: Used for dispatching custom events.
- `langchain_core.runnables.RunnableConfig`: Used for configuring runnables.
- `langchain_core.tools.BaseTool`: Base class for tools.
- `typing.Any`, `Optional`, `Union`: Used for type hinting.
- `langchain_core.messages.HumanMessage`, `ToolCall`: Used for handling messages and tool calls.
- `..langchain.utils._extract_json`, `create_pydantic_model`: Utility functions for JSON extraction and Pydantic model creation.
- `langchain_core.utils.function_calling.convert_to_openai_tool`: Used for converting tools to OpenAI format.
- `pydantic.ValidationError`: Used for handling validation errors.

## Functional Flow

The functional flow of `tool.py` starts with the instantiation of the `ToolNode` class. The `invoke` function is called with the state, configuration, and additional keyword arguments. The function extracts parameters for the tool, formats the input variables, and generates a prompt. The client is invoked to get a completion, which is processed to extract the result. The result is used to run the tool, and the final output is returned. The `_run` function serves as a wrapper for `invoke`.

## Endpoints Used/Created

There are no explicit endpoints used or created in `tool.py`. The functionality revolves around invoking tools and processing their outputs within the Alita SDK framework.