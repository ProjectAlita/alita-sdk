# llamaAgentParser.py

**Path:** `src/alita_sdk/agents/llamaAgentParser.py`

## Data Flow

The data flow within `llamaAgentParser.py` revolves around parsing text inputs to extract structured information using regular expressions and JSON parsing. The primary function, `extract_using_regex`, takes a text input and applies a regex pattern to extract function names and parameters. If a match is found, it returns a dictionary with the function name and arguments; otherwise, it returns the text as the final response. This parsed data is then used by the `LlamaAgentOutputParser` class to determine the appropriate action or final response.

Example:
```python
pattern = r'<function=(.*?)>(.*?)</?function>'
match = re.search(pattern, text)
if match:
    function_name = match.group(1)
    params = match.group(2)
    return {
        "tool": {
            "name": function_name,
            "args": json.loads(params) if params else {}
        }
    }
else:
    return {
        "final_response": text
```
In this example, the regex pattern is used to extract the function name and parameters from the text, which are then returned as a dictionary.

## Functions Descriptions

### `extract_using_regex(text) -> dict`

This function extracts function names and parameters from a given text using a regex pattern. It returns a dictionary with the function name and arguments if a match is found, or the text as the final response if no match is found.

- **Parameters:**
  - `text` (str): The input text to be parsed.
- **Returns:**
  - `dict`: A dictionary containing the function name and arguments or the final response.

### `LlamaAgentOutputParser`

This class is responsible for parsing the output of the Llama agent. It uses the `extract_using_regex` function to extract structured information from the text and determine the appropriate action or final response.

#### `parse(self, text: str) -> Union[AgentAction, AgentFinish]`

This method parses the input text to extract the action and tool input using the `extract_using_regex` function. It returns an `AgentAction` if a tool is found, or an `AgentFinish` if no tool is found.

- **Parameters:**
  - `text` (str): The input text to be parsed.
- **Returns:**
  - `Union[AgentAction, AgentFinish]`: The parsed action or final response.

#### `@property _type(self) -> str`

This property returns the type of the parser, which is "llama-agent-parser".

- **Returns:**
  - `str`: The type of the parser.

## Dependencies Used and Their Descriptions

### `json`

The `json` module is used to parse JSON strings into Python dictionaries and vice versa. It is used in the `extract_using_regex` function to parse the parameters extracted from the text.

### `re`

The `re` module provides support for regular expressions in Python. It is used in the `extract_using_regex` function to search for patterns in the input text.

### `typing`

The `typing` module provides support for type hints in Python. It is used in the `LlamaAgentOutputParser` class to specify the return types of the methods.

### `langchain_core.agents`

This module provides the `AgentAction` and `AgentFinish` classes, which are used to represent the actions and final responses of the agent.

### `langchain.agents.agent`

This module provides the `AgentOutputParser` class, which is the base class for the `LlamaAgentOutputParser` class.

## Functional Flow

1. The `extract_using_regex` function is called with the input text.
2. The function applies a regex pattern to extract the function name and parameters from the text.
3. If a match is found, the function returns a dictionary with the function name and arguments; otherwise, it returns the text as the final response.
4. The `LlamaAgentOutputParser` class uses the `extract_using_regex` function to parse the input text.
5. The `parse` method of the `LlamaAgentOutputParser` class determines the appropriate action or final response based on the parsed data.
6. The `_type` property of the `LlamaAgentOutputParser` class returns the type of the parser.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file. The functionality is focused on parsing text inputs and determining actions or final responses based on the parsed data.