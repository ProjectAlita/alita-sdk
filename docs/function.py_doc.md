# function.py

**Path:** `src/alita_sdk/tools/function.py`

## Data Flow

The data flow within `function.py` revolves around the `FunctionTool` class, which is designed to handle the invocation of tools and manage their input and output. The data originates from the `invoke` method, which receives the state and configuration as inputs. The state can be a string, dictionary, or `ToolCall` object, and the configuration is an optional `RunnableConfig` object. The method processes these inputs to extract the necessary parameters for the tool invocation.

The `invoke` method uses the `convert_to_openai_tool` function to convert the tool into a format compatible with OpenAI's tool schema. It then propagates the input mapping using the `propagate_the_input_mapping` function, which maps the input variables to the corresponding values in the state. The resulting function arguments are used to invoke the tool.

The tool's result is dispatched as a custom event using the `dispatch_custom_event` function, and the result is logged. If the `output_variables` attribute is not set, the method returns a dictionary with a single message containing the tool result. Otherwise, it returns a dictionary with the first output variable and the tool result.

Example:
```python
params = convert_to_openai_tool(self.tool).get(
    'function', {'parameters': {}}).get(
    'parameters', {'properties': {}}).get('properties', {})
func_args = propagate_the_input_mapping(input_mapping=self.input_mapping, input_variables=self.input_variables,
                                        state=state)
try:
    tool_result = self.tool.invoke(func_args, config, **kwargs)
    dispatch_custom_event(
        "on_function_tool_node", {
            "input_mapping": self.input_mapping,
            "input_variables": self.input_variables,
            "state": state,
            "tool_result": tool_result,
        }, config=config
    )
    logger.info(f"ToolNode response: {tool_result}")
    if not self.output_variables:
        return {"messages": [{"role": "assistant", "content": tool_result}]}
    else:
        return {
            self.output_variables[0]: tool_result,
            "messages": [{"role": "assistant", "content": tool_result}]
        }
except ValidationError:
    return {"messages": [
        {"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {func_args} raised ValidationError. 
\n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
{func_args}"""}]}
```

## Functions Descriptions

### `invoke`

The `invoke` method is the core function of the `FunctionTool` class. It is responsible for invoking the tool with the provided state and configuration. The method first converts the tool to an OpenAI-compatible format using the `convert_to_openai_tool` function. It then propagates the input mapping to generate the function arguments. The tool is invoked with these arguments, and the result is dispatched as a custom event. The method returns the tool result, either as a single message or as a dictionary with the first output variable and the tool result.

**Parameters:**
- `state`: The state of the tool, which can be a string, dictionary, or `ToolCall` object.
- `config`: An optional `RunnableConfig` object.
- `kwargs`: Additional keyword arguments.

**Returns:**
- A dictionary containing the tool result.

### `_run`

The `_run` method is a wrapper for the `invoke` method. It simply calls the `invoke` method with the provided arguments.

**Parameters:**
- `args`: Positional arguments.
- `kwargs`: Keyword arguments.

**Returns:**
- The result of the `invoke` method.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used to log information about the tool's execution. It is configured to log messages at the INFO level.

### `dumps` from `json`

The `dumps` function from the `json` module is used to serialize the tool schema to a JSON string for logging purposes.

### `dispatch_custom_event` from `langchain_core.callbacks`

The `dispatch_custom_event` function is used to dispatch custom events with the tool's input and output data.

### `ToolCall` from `langchain_core.messages`

The `ToolCall` class is used to represent the state of the tool when it is invoked.

### `RunnableConfig` from `langchain_core.runnables`

The `RunnableConfig` class is used to represent the configuration of the tool when it is invoked.

### `BaseTool` from `langchain_core.tools`

The `BaseTool` class is the base class for all tools in the LangChain framework. The `FunctionTool` class inherits from this class.

### `convert_to_openai_tool` from `langchain_core.utils.function_calling`

The `convert_to_openai_tool` function is used to convert the tool to a format compatible with OpenAI's tool schema.

### `InjectedStore` from `langgraph.prebuilt`

The `InjectedStore` class is used to manage the state of the tool when it is invoked.

### `BaseStore` from `langgraph.store.base`

The `BaseStore` class is the base class for all stores in the LangGraph framework. The `InjectedStore` class inherits from this class.

### `ValidationError` from `pydantic`

The `ValidationError` class is used to handle validation errors when the tool's input data does not match the expected schema.

### `propagate_the_input_mapping` from `..langchain.utils`

The `propagate_the_input_mapping` function is used to map the input variables to the corresponding values in the state.

## Functional Flow

The functional flow of `function.py` begins with the instantiation of the `FunctionTool` class. The `invoke` method is called with the state and configuration as inputs. The method converts the tool to an OpenAI-compatible format and propagates the input mapping to generate the function arguments. The tool is invoked with these arguments, and the result is dispatched as a custom event. The method returns the tool result, either as a single message or as a dictionary with the first output variable and the tool result.

The `_run` method is a wrapper for the `invoke` method. It simply calls the `invoke` method with the provided arguments.

Example:
```python
def _run(self, *args, **kwargs):
    return self.invoke(**kwargs)
```

## Endpoints Used/Created

There are no explicit endpoints used or created in `function.py`. The functionality is focused on invoking tools and managing their input and output within the LangChain framework.
