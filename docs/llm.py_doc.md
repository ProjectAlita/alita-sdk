# llm.py

**Path:** `src/alita_sdk/tools/llm.py`

## Data Flow

The data flow within `llm.py` revolves around the creation and processing of inputs for a language model (LLM) and the handling of its outputs. The primary function, `create_llm_input`, takes in a prompt, parameters, and additional keyword arguments to generate a list of `HumanMessage` objects. These messages are then used by the `LLMNode` class to interact with the LLM client. The data originates from the prompt and parameters provided to the function, which are then transformed into a format suitable for the LLM. The output from the LLM is processed and returned in a structured format if specified. Intermediate variables such as `params` and `llm_input` are used to store the transformed data before it is sent to the LLM client.

Example:
```python
params = {var: kwargs.get(var, "") for var in self.input_variables if var != 'messages'}
logger.info(f"LLM Node params: {params}")
llm_input = create_llm_input(self.prompt, params, kwargs)
```
In this snippet, `params` is an intermediate variable that stores the parameters extracted from `kwargs`, and `llm_input` is the transformed data ready to be sent to the LLM client.

## Functions Descriptions

### create_llm_input

This function generates a list of `HumanMessage` objects based on the provided prompt, parameters, and additional keyword arguments. It supports different types of prompts (`fstring` and `string`) and formats the messages accordingly. The function returns a list of `HumanMessage` objects that are used as input for the LLM.

**Inputs:**
- `prompt`: A dictionary containing the prompt type and value.
- `params`: A dictionary of parameters to be used in the prompt.
- `kwargs`: Additional keyword arguments, including user input and existing messages.

**Outputs:**
- A list of `HumanMessage` objects.

### LLMNode

The `LLMNode` class is a tool node for interacting with an LLM. It defines various attributes such as `name`, `prompt`, `description`, `client`, `return_type`, `response_key`, `output_variables`, `input_variables`, and `structured_output`. The `_run` method processes the input variables, generates the LLM input using `create_llm_input`, and invokes the LLM client. It handles both structured and unstructured outputs and includes error handling mechanisms.

**Inputs:**
- `args`: Positional arguments.
- `kwargs`: Keyword arguments, including input variables and messages.

**Outputs:**
- A dictionary containing the LLM response, either structured or unstructured.

## Dependencies Used and Their Descriptions

- `json`: Used for handling JSON data.
- `logging`: Used for logging information and errors.
- `format_exc`: Used for formatting exception tracebacks.
- `Any`, `Optional`, `Dict`, `List`: Type hints from the `typing` module.
- `HumanMessage`, `PromptTemplate`, `BaseTool`: Imported from `langchain_core` for creating messages, templates, and tools.
- `_extract_json`, `create_pydantic_model`: Utility functions from `..langchain.utils` for extracting JSON data and creating Pydantic models.

These dependencies are crucial for handling data, logging, type hinting, and interacting with the LLM client.

## Functional Flow

The functional flow begins with the creation of LLM input using the `create_llm_input` function. The `LLMNode` class then processes this input in its `_run` method, invoking the LLM client and handling the response. The flow includes error handling to manage exceptions and ensure robust execution.

1. Extract parameters from `kwargs`.
2. Generate LLM input using `create_llm_input`.
3. Invoke the LLM client with the generated input.
4. Process the LLM response and return it in the specified format.

## Endpoints Used/Created

The `llm.py` file does not explicitly define or call any endpoints. Instead, it focuses on creating and processing inputs for an LLM client and handling the responses.