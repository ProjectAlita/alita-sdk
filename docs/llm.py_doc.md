# llm.py

**Path:** `src/alita_sdk/tools/llm.py`

## Data Flow

The data flow within `llm.py` revolves around the creation and processing of inputs for a language model (LLM) and the handling of its outputs. The data originates from the parameters and keyword arguments passed to the functions, which are then used to construct the input for the LLM. This input is processed by the LLM, and the output is subsequently handled and formatted based on the specified requirements.

For example, in the `create_llm_input` function, the data flow can be observed as follows:

```python
params = {var: kwargs.get(var, "") for var in self.input_variables if var != 'messages'}
llm_input = create_llm_input(self.prompt, params, kwargs)
```

Here, `params` are extracted from `kwargs`, and then `llm_input` is created using these parameters along with the prompt. This input is then passed to the LLM for processing.

## Functions Descriptions

### `create_llm_input`

This function is responsible for creating the input for the LLM based on the provided prompt, parameters, and additional keyword arguments. It returns a list of `HumanMessage` objects that represent the input to be fed into the LLM.

**Inputs:**
- `prompt`: A dictionary containing the type and value of the prompt.
- `params`: A dictionary of parameters to be used in the prompt.
- `kwargs`: Additional keyword arguments.

**Outputs:**
- A list of `HumanMessage` objects.

### `LLMNode`

This class represents a tool node for the LLM. It contains various attributes such as `name`, `prompt`, `description`, `client`, `return_type`, `response_key`, `output_variables`, `input_variables`, and `structured_output`. The primary method in this class is `_run`, which executes the LLM node's functionality.

**Inputs:**
- `args`: Positional arguments.
- `kwargs`: Keyword arguments.

**Outputs:**
- The result of the LLM processing, which can be a structured output or a simple response based on the configuration.

## Dependencies Used and Their Descriptions

- `json`: Used for handling JSON data.
- `logging`: Used for logging information and errors.
- `traceback`: Used for formatting exception tracebacks.
- `typing`: Used for type hinting.
- `langchain_core.messages`: Provides the `HumanMessage` class.
- `langchain_core.prompts`: Provides the `PromptTemplate` class.
- `langchain_core.tools`: Provides the `BaseTool` class.
- `..langchain.utils`: Provides utility functions such as `_extract_json` and `create_pydantic_model`.

These dependencies are crucial for the functionality of the LLM node, as they provide the necessary classes and functions for creating prompts, handling messages, and processing the LLM's output.

## Functional Flow

The functional flow of `llm.py` begins with the creation of the LLM input using the `create_llm_input` function. This input is then processed by the LLM node, which is represented by the `LLMNode` class. The `_run` method of this class handles the execution of the LLM node, including the creation of parameters, invocation of the LLM, and handling of the output.

For example, the `_run` method follows this flow:

1. Extract parameters from `kwargs`.
2. Create the LLM input using `create_llm_input`.
3. Invoke the LLM with the created input.
4. Handle the output based on the configuration (structured or simple response).
5. Return the processed output.

## Endpoints Used/Created

There are no explicit endpoints used or created within `llm.py`. The functionality is focused on creating and processing inputs for the LLM and handling its outputs.