# tool.py

**Path:** `src/alita_sdk/tools/tool.py`

## Data Flow

The data flow within `tool.py` revolves around the `ToolNode` class, which is designed to handle the invocation of tools based on user input and conversation history. The data originates from the user input, which is processed and formatted into a structured or unstructured output that can be used as arguments for tool calls. The data is then passed to the specified tool, and the result is returned to the user. The data flow can be summarized as follows:

1. User input is received and stored in the `state` variable.
2. The `invoke` method extracts the necessary parameters and formats the input data.
3. The formatted input is passed to the tool for execution.
4. The tool's output is processed and returned to the user.

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
input += [
    HumanMessage(self.prompt.format(
        tool_name=self.tool.name,
        tool_description=self.tool.description,
        schema=parameters,
        last_message=dumps(last_message)))
]
```
In this example, the user input is extracted and formatted into a `HumanMessage` object, which is then passed to the tool for execution.

## Functions Descriptions

### `invoke`

The `invoke` method is responsible for executing the specified tool based on the user input and conversation history. It extracts the necessary parameters, formats the input data, and passes it to the tool for execution. The method handles both structured and unstructured outputs and returns the tool's result to the user.

**Inputs:**
- `state`: The current state of the conversation, including user input and messages.
- `config`: Optional configuration for the tool execution.
- `kwargs`: Additional arguments for the tool.

**Outputs:**
- The result of the tool execution, formatted as a dictionary with the output variables and messages.

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
In this example, the method extracts the parameters for the tool and formats them into a string and a dictionary for further processing.

### `_run`

The `_run` method is a wrapper for the `invoke` method, allowing it to be called with positional arguments. It simply calls the `invoke` method with the provided arguments and returns the result.

**Inputs:**
- `args`: Positional arguments for the `invoke` method.
- `kwargs`: Keyword arguments for the `invoke` method.

**Outputs:**
- The result of the `invoke` method.

Example:
```python
def _run(self, *args, **kwargs):
    return self.invoke(**kwargs)
```
In this example, the `_run` method calls the `invoke` method with the provided keyword arguments and returns the result.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging debug and error messages throughout the code. It helps in tracking the flow of execution and identifying issues.

### `json.dumps`

The `dumps` function from the `json` module is used to convert Python objects into JSON strings. It is used to format the input and output data for the tools.

### `traceback.format_exc`

The `format_exc` function from the `traceback` module is used to format exception tracebacks as strings. It is used to log detailed error messages when exceptions occur.

### `langchain_core.callbacks.dispatch_custom_event`

The `dispatch_custom_event` function is used to dispatch custom events during the tool execution. It helps in tracking the tool's execution and handling custom logic based on the events.

### `langchain_core.runnables.RunnableConfig`

The `RunnableConfig` class is used to configure the execution of runnables, including tools. It provides options for customizing the tool execution.

### `langchain_core.tools.BaseTool`

The `BaseTool` class is the base class for all tools in the LangChain framework. The `ToolNode` class inherits from `BaseTool` and extends its functionality.

### `typing`

The `typing` module is used for type hints and annotations throughout the code. It helps in improving code readability and maintainability.

### `langchain_core.messages.HumanMessage`

The `HumanMessage` class is used to represent user messages in the conversation. It is used to format the user input and pass it to the tools.

### `langchain_core.messages.ToolCall`

The `ToolCall` class is used to represent tool calls in the conversation. It is used to store the state of the tool execution and pass it between methods.

### `..langchain.utils._extract_json`

The `_extract_json` function is used to extract JSON data from strings. It is used to parse the tool's output and convert it into a dictionary.

### `..langchain.utils.create_pydantic_model`

The `create_pydantic_model` function is used to create Pydantic models dynamically. It is used to create structured output models for the tools.

### `langchain_core.utils.function_calling.convert_to_openai_tool`

The `convert_to_openai_tool` function is used to convert tools into OpenAI-compatible tools. It is used to extract the parameters and schema for the tools.

### `pydantic.ValidationError`

The `ValidationError` class from the `pydantic` module is used to handle validation errors when creating Pydantic models. It is used to catch and log validation errors during tool execution.

## Functional Flow

The functional flow of `tool.py` involves the following steps:

1. The `ToolNode` class is instantiated with the necessary attributes, including the tool, client, and input/output variables.
2. The `invoke` method is called with the current state, configuration, and additional arguments.
3. The method extracts the parameters for the tool and formats the input data.
4. The formatted input is passed to the tool for execution.
5. The tool's output is processed and returned to the user.
6. If an exception occurs, it is caught and logged, and an error message is returned to the user.

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
    parameters = ''
    struct_params = {}
    for key in params.keys():
        parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
        struct_params[key] = {"type": params[key].get('type', 'str'),
                              "description": params[key].get('description', '')}
    input = []
    last_message = {}
    for var in self.input_variables:
        if 'messages' in self.input_variables:
            messages = state.get('messages', [])[:]
            input = messages[:-1]
            last_message["user_input"] = messages[-1].content
        else:
            last_message[var] = state[var]
    input += [
        HumanMessage(self.prompt.format(
            tool_name=self.tool.name,
            tool_description=self.tool.description,
            schema=parameters,
            last_message=dumps(last_message)))
    ]
    if self.structured_output:
        stuct_model = create_pydantic_model(f"{self.tool.name}Output", struct_params)
        llm = self.client.with_structured_output(stuct_model)
        completion = llm.invoke(input, config=config)
        result = completion.model_dump()
    else:
        input[-1].content += self.unstructured_output
        completion = self.client.invoke(input, config=config)
        result = _extract_json(completion.content.strip())
    try:
        tool_result = self.tool.invoke(result, config=config, kwargs=kwargs)
        dispatch_custom_event(
            "on_tool_node", {
                "input_variables": self.input_variables,
                "tool_result": tool_result,
                "state": state,
            }, config=config
        )
        message_result = tool_result
        if isinstance(tool_result, dict) or isinstance(tool_result, list):
            message_result = dumps(tool_result)
        if not self.output_variables:
            return {"messages": [{"role": "assistant", "content": message_result}]}
        else:
            return {self.output_variables[0]: tool_result,
                    "messages": [{"role": "assistant", "content": message_result}]}
    except ValidationError:
        return {
            "messages": [{"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {result} raised ValidationError. 
    \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
    {input[-1].content}"""}]}
```
In this example, the `invoke` method extracts the parameters, formats the input data, and passes it to the tool for execution. The tool's output is then processed and returned to the user.

## Endpoints Used/Created

The `tool.py` file does not explicitly define or call any endpoints. The primary focus of the file is to handle the invocation and execution of tools based on user input and conversation history. The interaction with external services or APIs is abstracted away by the tools themselves, which are passed to the `ToolNode` class for execution.