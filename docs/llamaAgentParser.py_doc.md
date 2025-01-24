# llamaAgentParser.py

**Path:** `src/alita_sdk/agents/llamaAgentParser.py`

## Data Flow

The data flow within `llamaAgentParser.py` revolves around parsing text input to extract structured information using regular expressions and JSON parsing. The primary function responsible for this is `extract_using_regex`, which takes a text input and applies a regex pattern to extract function names and parameters. The extracted data is then converted into a dictionary format. This dictionary is used by the `LlamaAgentOutputParser` class to determine the appropriate action or final response.

For example, the `extract_using_regex` function processes the text as follows:

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

In this snippet, the regex pattern searches for a specific format in the text, extracts the function name and parameters, and returns them in a dictionary. If no match is found, it returns the original text as the final response.

## Functions Descriptions

### `extract_using_regex(text) -> dict`

This function extracts function names and parameters from a given text using a regex pattern. It returns a dictionary containing the extracted information.

- **Parameters:**
  - `text` (str): The input text to be parsed.
- **Returns:**
  - `dict`: A dictionary with the extracted function name and parameters, or the original text if no match is found.

### `LlamaAgentOutputParser`

A class that extends `AgentOutputParser` to parse the output of a communication agent. It uses the `extract_using_regex` function to process the text and determine the appropriate action or final response.

- **Methods:**
  - `parse(self, text: str) -> Union[AgentAction, AgentFinish]`
    - Parses the input text and returns an `AgentAction` or `AgentFinish` object based on the extracted information.
  - `@property def _type(self) -> str`
    - Returns the type of the parser as a string.

## Dependencies Used and Their Descriptions

### `json`

Used for parsing JSON strings into Python dictionaries and vice versa. This is essential for handling the parameters extracted from the text.

### `re`

The `re` module is used for applying regular expressions to search and extract specific patterns from the text. This is crucial for identifying function names and parameters within the input text.

### `typing`

Provides type hints for better code readability and maintainability. In this file, it is used to specify the return types of functions and methods.

### `langchain_core.agents`

Imports `AgentAction` and `AgentFinish` classes, which are used to represent the actions and final responses of the agent.

### `langchain.agents.agent`

Imports the `AgentOutputParser` class, which is extended by `LlamaAgentOutputParser` to implement custom parsing logic.

## Functional Flow

The functional flow of `llamaAgentParser.py` starts with the `LlamaAgentOutputParser` class, which is designed to parse the output of a communication agent. When the `parse` method is called with a text input, it uses the `extract_using_regex` function to extract structured information from the text. Based on the extracted information, it either returns an `AgentAction` object (if a function name and parameters are found) or an `AgentFinish` object (if no function name is found).

For example, the `parse` method processes the text as follows:

```python
response = extract_using_regex(text)

if tool:
    if isinstance(tool, dict):
        action = tool.get("name")
        tool_input = tool.get("args", {})
    elif isinstance(tool, str):
        action = tool
        tool_input = response.get("args", {})
    else:
        raise UnexpectedResponseError(f'Unexpected response {response}')
    return AgentAction(action, tool_input, text)
else:
    return AgentFinish({"output": response.get("final_response", text)}, log=text)
```

In this snippet, the `parse` method first calls `extract_using_regex` to get the response. It then checks if a tool is present in the response and constructs the appropriate `AgentAction` or `AgentFinish` object based on the extracted information.

## Endpoints Used/Created

There are no explicit endpoints used or created in `llamaAgentParser.py`. The file focuses on parsing text input and does not interact with external services or APIs.