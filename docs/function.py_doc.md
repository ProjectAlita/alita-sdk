# function.py

**Path:** `src/alita_sdk/tools/function.py`

## Data Flow

The data flow within `function.py` revolves around the `FunctionTool` class, which is designed to handle the invocation of tools. The data originates from the `invoke` method's parameters, which include `state`, `config`, and additional keyword arguments. The `state` parameter can be a string, dictionary, or `ToolCall` object, and it represents the current state of the tool's execution. The `config` parameter is an optional `RunnableConfig` object that provides configuration settings for the tool's execution.

Within the `invoke` method, the data undergoes several transformations. First, the `convert_to_openai_tool` function is called to convert the tool into an OpenAI-compatible format. This function returns a dictionary containing the tool's parameters, which are then extracted and stored in the `params` variable. Next, the `propagate_the_input_mapping` function is called to map the input variables to their corresponding values based on the provided `state`. This function returns a dictionary of function arguments, which are stored in the `func_args` variable.

The tool is then invoked with the `func_args` and `config` parameters, and the result is stored in the `tool_result` variable. If the tool invocation is successful, a custom event is dispatched using the `dispatch_custom_event` function, and the result is logged. The method then checks if there are any output variables specified. If not, it returns a dictionary containing the tool result as a message. If output variables are specified, it returns a dictionary containing the tool result and the output variables.

If a `ValidationError` occurs during the tool invocation, the method returns a dictionary containing an error message with details about the validation error and the tool's schema.

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

The `invoke` method is the core function of the `FunctionTool` class. It is responsible for invoking the tool with the provided state and configuration. The method takes the following parameters:
- `state`: A string, dictionary, or `ToolCall` object representing the current state of the tool's execution.
- `config`: An optional `RunnableConfig` object providing configuration settings for the tool's execution.
- `kwargs`: Additional keyword arguments.

The method performs the following steps:
1. Converts the tool into an OpenAI-compatible format using the `convert_to_openai_tool` function.
2. Extracts the tool's parameters and stores them in the `params` variable.
3. Maps the input variables to their corresponding values based on the provided `state` using the `propagate_the_input_mapping` function.
4. Invokes the tool with the mapped function arguments and configuration, storing the result in the `tool_result` variable.
5. Dispatches a custom event with the tool result using the `dispatch_custom_event` function.
6. Logs the tool result.
7. Checks if there are any output variables specified and returns the appropriate response.
8. Handles `ValidationError` exceptions by returning an error message with details about the validation error and the tool's schema.

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

The `_run` method is a helper function that calls the `invoke` method with the provided keyword arguments. It is designed to be used internally within the `FunctionTool` class.

Example:
```python
def _run(self, *args, **kwargs):
    return self.invoke(**kwargs)
```

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used to log information, warnings, and errors within the `FunctionTool` class. It provides a flexible framework for emitting log messages from Python programs. In this file, it is used to log the tool's response and any validation errors that occur during the tool invocation.

### `dumps` from `json`

The `dumps` function from the `json` module is used to serialize Python objects into JSON format. In this file, it is used to serialize the tool's schema when a validation error occurs.

### `dispatch_custom_event` from `langchain_core.callbacks`

The `dispatch_custom_event` function is used to dispatch custom events within the `FunctionTool` class. It is called after the tool invocation to emit an event with the tool result and other relevant information.

### `ToolCall` from `langchain_core.messages`

The `ToolCall` class is used to represent a tool call message. It is one of the possible types for the `state` parameter in the `invoke` method.

### `RunnableConfig` from `langchain_core.runnables`

The `RunnableConfig` class is used to provide configuration settings for the tool's execution. It is an optional parameter in the `invoke` method.

### `BaseTool` from `langchain_core.tools`

The `BaseTool` class is the base class for all tools in the `langchain_core` library. The `FunctionTool` class inherits from `BaseTool` and extends its functionality to handle tool invocations.

### `Any`, `Optional`, `Union`, `Annotated` from `typing`

These type hints from the `typing` module are used to specify the types of parameters and return values in the `FunctionTool` class. They provide better code readability and help with type checking.

### `convert_to_openai_tool` from `langchain_core.utils.function_calling`

The `convert_to_openai_tool` function is used to convert a tool into an OpenAI-compatible format. It is called in the `invoke` method to extract the tool's parameters.

### `InjectedStore` from `langgraph.prebuilt`

The `InjectedStore` class is used to represent a prebuilt store in the `langgraph` library. It is imported but not used in the `function.py` file.

### `BaseStore` from `langgraph.store.base`

The `BaseStore` class is the base class for all stores in the `langgraph` library. It is imported but not used in the `function.py` file.

### `ValidationError` from `pydantic`

The `ValidationError` class is used to handle validation errors that occur during the tool invocation. It is caught in the `invoke` method to return an error message with details about the validation error and the tool's schema.

### `propagate_the_input_mapping` from `..langchain.utils`

The `propagate_the_input_mapping` function is used to map the input variables to their corresponding values based on the provided `state`. It is called in the `invoke` method to prepare the function arguments for the tool invocation.

## Functional Flow

The functional flow of `function.py` begins with the instantiation of the `FunctionTool` class. The class is initialized with several attributes, including `name`, `description`, `tool`, `return_type`, `input_variables`, `input_mapping`, and `output_variables`.

The primary method in this file is the `invoke` method, which is responsible for invoking the tool with the provided state and configuration. The method starts by converting the tool into an OpenAI-compatible format and extracting its parameters. It then maps the input variables to their corresponding values based on the provided state.

Next, the tool is invoked with the mapped function arguments and configuration. If the invocation is successful, a custom event is dispatched with the tool result, and the result is logged. The method then checks if there are any output variables specified and returns the appropriate response. If a validation error occurs, the method returns an error message with details about the validation error and the tool's schema.

The `_run` method is a helper function that calls the `invoke` method with the provided keyword arguments. It is designed to be used internally within the `FunctionTool` class.

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

The `function.py` file does not explicitly define or call any endpoints. The primary focus of this file is to handle the invocation of tools within the `FunctionTool` class. The interactions are primarily internal, involving the conversion of tools to an OpenAI-compatible format, mapping input variables, invoking tools, and handling validation errors. There are no external API calls or endpoints defined within this file.