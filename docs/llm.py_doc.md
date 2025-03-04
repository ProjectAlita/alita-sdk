# llm.py

**Path:** `src/alita_sdk/tools/llm.py`

## Data Flow

The data flow within `llm.py` revolves around the creation and processing of inputs for a language model (LLM) and the handling of its outputs. The primary function, `create_llm_input`, takes a prompt, parameters, and additional keyword arguments to generate a list of `BaseMessage` objects. This function formats the prompt based on the provided parameters and appends it to any existing messages. The `LLMNode` class, which inherits from `BaseTool`, uses this function to prepare inputs for the LLM client. The `_run` method of `LLMNode` processes these inputs, invokes the LLM client, and handles the outputs, including structured outputs if specified. The data flow involves transforming the prompt and parameters into a format suitable for the LLM, invoking the LLM, and then processing the LLM's response to extract relevant information.

Example:
```python
def create_llm_input(prompt: Dict[str, str], params: Dict[str, Any], kwargs: Dict[str, Any]) -> list[BaseMessage]:
    logger.info(f"Creating LLM input with prompt: {prompt}, params: {params}, kwargs: {kwargs}")
    if prompt.get('type') == 'fstring' and params:
        return [HumanMessage(content=prompt['value'].format(**params))]
    else:
        return kwargs.get("messages") + [HumanMessage(prompt['value'])]
```
This function formats the prompt using the provided parameters and appends it to any existing messages.

## Functions Descriptions

### `create_llm_input`

This function generates a list of `BaseMessage` objects based on the provided prompt, parameters, and additional keyword arguments. It formats the prompt using the parameters if the prompt type is 'fstring' and appends it to any existing messages.

- **Inputs:**
  - `prompt` (Dict[str, str]): The prompt to be formatted and used.
  - `params` (Dict[str, Any]): Parameters for formatting the prompt.
  - `kwargs` (Dict[str, Any]): Additional keyword arguments, including existing messages.
- **Outputs:**
  - list[BaseMessage]: A list of formatted messages for the LLM.

### `LLMNode`

This class represents a tool node for interacting with an LLM. It inherits from `BaseTool` and defines several attributes and methods for handling LLM inputs and outputs.

- **Attributes:**
  - `name` (str): The name of the tool node.
  - `prompt` (Dict[str, str]): The prompt to be used by the LLM.
  - `description` (str): A description of the tool node.
  - `client` (Any): The LLM client to be used.
  - `return_type` (str): The type of the return value.
  - `response_key` (str): The key for the response data.
  - `output_variables` (Optional[List[str]]): The variables to be included in the output.
  - `input_variables` (Optional[List[str]]): The variables to be included in the input.
  - `structured_output` (Optional[bool]): Whether to use structured output.

- **Methods:**
  - `_run(self, *args, **kwargs)`: Processes the inputs, invokes the LLM client, and handles the outputs.

Example:
```python
class LLMNode(BaseTool):
    name: str = 'LLMNode'
    prompt: Dict[str, str]
    description: str = 'This is tool node for LLM'
    client: Any = None
    return_type: str = "str"
    response_key: str = "messages"
    output_variables: Optional[List[str]] = None
    input_variables: Optional[List[str]] = None
    structured_output: Optional[bool] = False

    def _run(self, *args, **kwargs):
        params = create_params(self.input_variables, kwargs)
        logger.info(f"LLM Node params: {params}")
        llm_input = create_llm_input(self.prompt, params, kwargs)
        try:
            if self.structured_output and len(self.output_variables) > 0:
                struct_params = {var: {"type": "str", "description": ""} for var in self.output_variables}
                stuct_model = create_pydantic_model(f"LLMOutput", struct_params)
                llm = self.client.with_structured_output(stuct_model)
                completion = llm.invoke(llm_input)
                result = completion.model_dump()
                return result
            else:
                completion = self.client.invoke(llm_input)
                result = completion.content.strip()
                response = _extract_json(result) or {}
                response_data = {key: response[key] for key in response if key in self.output_variables}
                if not response_data.get('messages'):
                    response_data['messages'] = [
                        {"role": "assistant", "content": response_data.get(self.response_key) or result}]
                return response_data
        except ValueError:
            if self.output_variables:
                return {self.output_variables[0]: result, "messages": [{"role": "assistant", "content": result}]}
            else:
                return {"messages": [{"role": "assistant", "content": result}]}
        except Exception as e:
            logger.error(f"Error in LLM Node: {format_exc()}")
            return {"messages": [{"role": "assistant", "content": f"Error: {e}"}]}
```
This class handles the creation of LLM inputs, invocation of the LLM client, and processing of the outputs.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information and errors within the module.
- `format_exc` from `traceback`: Used to format exception tracebacks for logging.
- `Any`, `Optional`, `Dict`, `List` from `typing`: Used for type hinting.
- `HumanMessage`, `BaseMessage` from `langchain_core.messages`: Used to represent messages for the LLM.
- `BaseTool` from `langchain_core.tools`: The base class for creating tool nodes.
- `_extract_json`, `create_pydantic_model`, `create_params` from `..langchain.utils`: Utility functions for handling JSON extraction, creating Pydantic models, and creating parameters.

## Functional Flow

1. **Initialization**: The `LLMNode` class is initialized with the necessary attributes, including the prompt, client, and configuration for input and output variables.
2. **Input Creation**: The `_run` method is called, which uses the `create_llm_input` function to generate the LLM input messages based on the prompt and parameters.
3. **LLM Invocation**: The LLM client is invoked with the generated input messages. If structured output is enabled, a Pydantic model is created for the output, and the LLM client is configured to use it.
4. **Output Handling**: The output from the LLM client is processed. If structured output is used, the result is converted to a dictionary. Otherwise, the output is parsed, and relevant information is extracted based on the specified output variables.
5. **Error Handling**: Errors during the LLM invocation or output processing are caught and logged. A default error message is returned in case of exceptions.

## Endpoints Used/Created

This module does not explicitly define or call any endpoints. The interaction with the LLM client is abstracted through the `client` attribute, which is expected to be an instance of a class that provides the `invoke` method for processing LLM inputs and outputs.