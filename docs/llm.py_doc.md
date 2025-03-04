# llm.py

**Path:** `src/alita_sdk/tools/llm.py`

## Data Flow

The data flow within `llm.py` revolves around the creation and processing of inputs for a language model (LLM) and handling its responses. The primary data elements include prompts, parameters, and keyword arguments, which are transformed into a list of `BaseMessage` objects. These messages are then processed by the LLM client to generate responses. The data flow can be summarized as follows:

1. **Input Data:** The function `create_llm_input` takes a dictionary `prompt`, a dictionary `params`, and additional keyword arguments `kwargs`.
2. **Transformation:** Depending on the type of prompt, the function formats the prompt using the parameters or appends it to existing messages.
3. **Output Data:** The transformed data is returned as a list of `BaseMessage` objects.
4. **LLM Processing:** The `LLMNode` class processes these messages using its client, handling structured and unstructured outputs.
5. **Error Handling:** The code includes error handling to manage exceptions and return appropriate error messages.

Example:
```python
# Example of creating LLM input
prompt = {'type': 'fstring', 'value': 'Hello, {name}!'}
params = {'name': 'World'}
kwargs = {}
llm_input = create_llm_input(prompt, params, kwargs)
# llm_input will be [HumanMessage(content='Hello, World!')]
```

## Functions Descriptions

### `create_llm_input`

This function is responsible for creating the input for the LLM based on the provided prompt, parameters, and keyword arguments.

- **Inputs:**
  - `prompt` (Dict[str, str]): A dictionary containing the type and value of the prompt.
  - `params` (Dict[str, Any]): A dictionary of parameters to format the prompt.
  - `kwargs` (Dict[str, Any]): Additional keyword arguments, including existing messages.
- **Processing:**
  - If the prompt type is 'fstring' and parameters are provided, it formats the prompt using the parameters.
  - Otherwise, it appends the prompt value to existing messages.
- **Outputs:**
  - Returns a list of `BaseMessage` objects.

### `LLMNode`

This class represents a tool node for the LLM, encapsulating the logic for processing inputs and handling responses.

- **Attributes:**
  - `name` (str): The name of the node.
  - `prompt` (Dict[str, str]): The prompt to be used.
  - `description` (str): A description of the node.
  - `client` (Any): The LLM client.
  - `return_type` (str): The type of the return value.
  - `response_key` (str): The key for the response.
  - `output_variables` (Optional[List[str]]): The output variables.
  - `input_variables` (Optional[List[str]]): The input variables.
  - `structured_output` (Optional[bool]): Whether the output is structured.
- **Methods:**
  - `_run(self, *args, **kwargs)`: Processes the input variables, creates LLM input, and handles the response.

Example:
```python
# Example of using LLMNode
node = LLMNode(prompt={'type': 'fstring', 'value': 'Hello, {name}!'}, client=llm_client)
response = node._run(name='World')
# response will contain the processed output from the LLM
```

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information and errors.
- `format_exc` from `traceback`: Used for formatting exception tracebacks.
- `Any`, `Optional`, `Dict`, `List` from `typing`: Used for type hinting.
- `HumanMessage`, `BaseMessage` from `langchain_core.messages`: Used for creating message objects for the LLM.
- `BaseTool` from `langchain_core.tools`: The base class for creating tool nodes.
- `_extract_json`, `create_pydantic_model`, `create_params` from `..langchain.utils`: Utility functions for handling JSON extraction, creating Pydantic models, and creating parameters.

## Functional Flow

1. **Initialization:** The `LLMNode` class is initialized with the necessary attributes, including the prompt and client.
2. **Input Processing:** The `_run` method processes the input variables and creates the LLM input using `create_llm_input`.
3. **LLM Invocation:** The method invokes the LLM client with the created input and handles the response.
4. **Structured Output Handling:** If structured output is enabled, it creates a Pydantic model and processes the response accordingly.
5. **Error Handling:** The method includes error handling to manage exceptions and return appropriate error messages.

## Endpoints Used/Created

The `llm.py` file does not explicitly define or call any external endpoints. The interactions are primarily with the LLM client, which is assumed to be an internal component or service.