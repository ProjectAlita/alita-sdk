# function.py

**Path:** `src/alita_sdk/tools/function.py`

## Data Flow

The data flow within `function.py` revolves around the `FunctionTool` class, which is designed to handle the invocation of tools. The data originates from the `invoke` method's parameters, which include `state`, `config`, and additional keyword arguments. The `state` parameter can be a string, dictionary, or `ToolCall` object, representing the input data for the tool. This data is then processed by the `convert_to_openai_tool` function to extract the tool's parameters. The `propagate_the_input_mapping` function is used to map the input variables to the tool's expected input format. The processed data is then passed to the tool's `invoke` method, which executes the tool's functionality and returns the result. The result is logged and dispatched as a custom event, and the final output is formatted and returned based on the presence of `output_variables`.

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

The `invoke` method is the core function of the `FunctionTool` class. It is responsible for executing the tool's functionality. The method takes the following parameters:
- `state`: A string, dictionary, or `ToolCall` object representing the input data for the tool.
- `config`: An optional `RunnableConfig` object for additional configuration.
- `kwargs`: Additional keyword arguments.

The method processes the input data using the `convert_to_openai_tool` and `propagate_the_input_mapping` functions to map the input variables to the tool's expected input format. It then calls the tool's `invoke` method with the processed data and configuration. The result is logged, dispatched as a custom event, and formatted based on the presence of `output_variables`. If a `ValidationError` occurs, an error message is returned.

Example:
```python
def invoke(
        self,
        state: Union[str, dict, ToolCall],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
) -> Any:
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

### `_run`

The `_run` method is a wrapper for the `invoke` method. It simply calls the `invoke` method with the provided keyword arguments.

Example:
```python
def _run(self, *args, **kwargs):
    return self.invoke(**kwargs)
```

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used to log information and errors within the `FunctionTool` class. It provides a way to track the execution flow and debug issues.

### `dumps` from `json`

The `dumps` function from the `json` module is used to convert Python objects into JSON strings. It is used in the `invoke` method to format the tool schema and input data for error messages.

### `dispatch_custom_event` from `langchain_core.callbacks`

The `dispatch_custom_event` function is used to dispatch custom events within the `FunctionTool` class. It is used in the `invoke` method to dispatch the `on_function_tool_node` event with the input data and tool result.

### `ToolCall` from `langchain_core.messages`

The `ToolCall` class is used to represent the input data for the tool. It is one of the possible types for the `state` parameter in the `invoke` method.

### `RunnableConfig` from `langchain_core.runnables`

The `RunnableConfig` class is used to provide additional configuration for the tool. It is an optional parameter in the `invoke` method.

### `BaseTool` from `langchain_core.tools`

The `BaseTool` class is the base class for all tools. The `FunctionTool` class inherits from `BaseTool` and uses it to represent the tool being invoked.

### `Any`, `Optional`, `Union`, `Annotated` from `typing`

These types from the `typing` module are used to provide type hints for the parameters and return values of the methods in the `FunctionTool` class.

### `convert_to_openai_tool` from `langchain_core.utils.function_calling`

The `convert_to_openai_tool` function is used to convert the tool to the OpenAI tool format. It is used in the `invoke` method to extract the tool's parameters.

### `InjectedStore` from `langgraph.prebuilt`

The `InjectedStore` class is used to represent a prebuilt store. It is imported but not used in the `FunctionTool` class.

### `BaseStore` from `langgraph.store.base`

The `BaseStore` class is the base class for all stores. It is imported but not used in the `FunctionTool` class.

### `ValidationError` from `pydantic`

The `ValidationError` class is used to handle validation errors. It is used in the `invoke` method to catch validation errors when invoking the tool.

### `propagate_the_input_mapping` from `..langchain.utils`

The `propagate_the_input_mapping` function is used to map the input variables to the tool's expected input format. It is used in the `invoke` method to process the input data.

## Functional Flow

The functional flow of `function.py` starts with the instantiation of the `FunctionTool` class. The `invoke` method is the main entry point for executing the tool's functionality. The method processes the input data, calls the tool's `invoke` method, logs the result, dispatches a custom event, and formats the final output. If a validation error occurs, an error message is returned. The `_run` method is a wrapper for the `invoke` method and simply calls it with the provided keyword arguments.

Example:
```python
class FunctionTool(BaseTool):
    name: str = 'FunctionalTool'
    description: str = 'This is direct call node for tools'
    tool: BaseTool = None
    return_type: str = "str"
    input_variables: Optional[list[str]] = None
    input_mapping: Optional[dict[str, dict]] = None
    output_variables: Optional[list[str]] = None

    def invoke(
            self,
            state: Union[str, dict, ToolCall],
            config: Optional[RunnableConfig] = None,
            **kwargs: Any,
    ) -> Any:
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

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
```

## Endpoints Used/Created

There are no explicit endpoints used or created in `function.py`. The functionality is focused on invoking tools and processing their input and output data.