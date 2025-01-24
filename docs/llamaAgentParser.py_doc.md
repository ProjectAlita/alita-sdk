# llamaAgentParser.py

**Path:** `src/alita_sdk/agents/llamaAgentParser.py`

## Data Flow

The data flow within `llamaAgentParser.py` revolves around parsing text inputs to extract structured information using regular expressions and then converting this information into specific agent actions or final responses. The primary data elements are the text inputs provided to the `parse` method of the `LlamaAgentOutputParser` class. This text is processed by the `extract_using_regex` function, which uses a regular expression to identify and extract function names and their parameters embedded within the text. The extracted data is then returned as a dictionary, which is further processed by the `parse` method to determine the appropriate agent action or final response.

For example, consider the following code snippet from the `extract_using_regex` function:

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

In this snippet, the regular expression pattern is used to search for function tags within the text. If a match is found, the function name and parameters are extracted and returned as a dictionary. If no match is found, the entire text is returned as the final response.

## Functions Descriptions

### `extract_using_regex(text) -> dict`

This function is responsible for extracting function names and their parameters from the provided text using a regular expression. It returns a dictionary containing the extracted information. If no function tags are found, it returns the entire text as the final response.

- **Inputs:**
  - `text` (str): The input text to be parsed.
- **Outputs:**
  - A dictionary containing the extracted function name and parameters, or the entire text as the final response.

### `LlamaAgentOutputParser`

This class is a parser for JSON-style communication agents. It inherits from `AgentOutputParser` and provides methods to parse text inputs and convert them into agent actions or final responses.

#### `parse(self, text: str) -> Union[AgentAction, AgentFinish]`

This method parses the provided text to determine the appropriate agent action or final response. It uses the `extract_using_regex` function to extract information from the text and then processes this information to create an `AgentAction` or `AgentFinish` object.

- **Inputs:**
  - `text` (str): The input text to be parsed.
- **Outputs:**
  - An `AgentAction` object if a function name and parameters are extracted.
  - An `AgentFinish` object if no function tags are found.

#### `@property def _type(self) -> str`

This property returns the type of the parser, which is "llama-agent-parser".

- **Outputs:**
  - A string representing the type of the parser.

## Dependencies Used and Their Descriptions

### `json`

The `json` module is used to parse JSON-formatted strings into Python dictionaries. In this file, it is used to convert the extracted parameters from the text into a dictionary format.

### `re`

The `re` module provides support for regular expressions in Python. It is used in the `extract_using_regex` function to search for and extract function tags from the input text.

### `typing`

The `typing` module is used to provide type hints for function signatures. In this file, it is used to specify the return types of the `parse` method and the `extract_using_regex` function.

### `langchain_core.agents`

This module provides the `AgentAction` and `AgentFinish` classes, which are used to represent the actions and final responses of the agent.

### `langchain.agents.agent`

This module provides the `AgentOutputParser` class, which is the base class for the `LlamaAgentOutputParser` class.

## Functional Flow

The functional flow of `llamaAgentParser.py` begins with the `parse` method of the `LlamaAgentOutputParser` class being called with a text input. This method calls the `extract_using_regex` function to extract function names and parameters from the text. The extracted information is then used to create an `AgentAction` or `AgentFinish` object, which is returned as the output of the `parse` method.

For example, consider the following code snippet from the `parse` method:

```python
response = extract_using_regex(text)

        tool: dict | str | None = response.get("tool", None)
        action = None
        tool_input = {}
        if tool:
            if isinstance(tool, dict):
                action: str | None = tool.get("name")
                tool_input: dict = tool.get("args", {})
            elif isinstance(tool, str):
                action: str | None = tool
                tool_input: dict = response.get("args", {})
            else:
                raise UnexpectedResponseError(f'Unexpected response {response}')
            return AgentAction(action, tool_input, text)
        else:
            return AgentFinish({"output": response.get("final_response", text)}, log=text)
```

In this snippet, the `extract_using_regex` function is called to extract information from the text. The extracted information is then used to create an `AgentAction` or `AgentFinish` object, which is returned as the output of the `parse` method.

## Endpoints Used/Created

There are no explicit endpoints used or created within `llamaAgentParser.py`. The file focuses on parsing text inputs and converting them into agent actions or final responses.