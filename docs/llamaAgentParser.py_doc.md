# llamaAgentParser.py

**Path:** `src/alita_sdk/agents/llamaAgentParser.py`

## Data Flow

The data flow within the `llamaAgentParser.py` file revolves around parsing text input to extract specific information using regular expressions and then converting this information into structured data. The primary function responsible for this is `extract_using_regex`, which takes a string input and searches for patterns that match a predefined regular expression. If a match is found, it extracts the function name and parameters, converts the parameters from JSON format if necessary, and returns them in a dictionary. If no match is found, it returns the original text as the final response.

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
}
```
In this example, the regular expression pattern is used to search for a function name and its parameters within the input text. If a match is found, the function name and parameters are extracted and returned in a dictionary. If no match is found, the original text is returned as the final response.

## Functions Descriptions

### `extract_using_regex(text) -> dict`

This function is designed to extract information from a given text using a regular expression. It searches for a pattern that matches a function name and its parameters enclosed within specific tags. If a match is found, it extracts the function name and parameters, converts the parameters from JSON format if necessary, and returns them in a dictionary. If no match is found, it returns the original text as the final response.

**Inputs:**
- `text` (str): The input text to be parsed.

**Outputs:**
- (dict): A dictionary containing the extracted function name and parameters, or the original text as the final response.

### `LlamaAgentOutputParser.parse(self, text: str) -> Union[AgentAction, AgentFinish]`

This method is responsible for parsing the input text and determining the appropriate action or final response. It uses the `extract_using_regex` function to extract information from the text and then processes this information to determine the action to be taken. If a tool is identified, it creates an `AgentAction` object with the tool name and parameters. If no tool is identified, it creates an `AgentFinish` object with the final response.

**Inputs:**
- `text` (str): The input text to be parsed.

**Outputs:**
- (Union[AgentAction, AgentFinish]): An `AgentAction` object if a tool is identified, or an `AgentFinish` object if no tool is identified.

### `LlamaAgentOutputParser._type(self) -> str`

This property method returns the type of the parser, which is "llama-agent-parser".

**Inputs:**
- None

**Outputs:**
- (str): The type of the parser.

## Dependencies Used and Their Descriptions

### `json`

The `json` module is used to parse JSON strings into Python dictionaries and vice versa. In this file, it is used to convert the parameters extracted from the input text into a dictionary format.

### `re`

The `re` module provides support for regular expressions in Python. It is used in this file to search for patterns within the input text and extract relevant information.

### `Union`

The `Union` type hint from the `typing` module is used to indicate that a function can return multiple types. In this file, it is used to specify that the `parse` method can return either an `AgentAction` or an `AgentFinish` object.

### `AgentAction`, `AgentFinish`

These classes are imported from the `langchain_core.agents` module and are used to represent the actions and final responses of the agent. The `parse` method returns instances of these classes based on the extracted information from the input text.

### `AgentOutputParser`

This class is imported from the `langchain.agents.agent` module and serves as the base class for the `LlamaAgentOutputParser` class. It provides the structure and basic functionality for parsing agent output.

## Functional Flow

The functional flow of the `llamaAgentParser.py` file begins with the `extract_using_regex` function, which is called by the `parse` method of the `LlamaAgentOutputParser` class. The `parse` method processes the input text to extract relevant information and determine the appropriate action or final response. If a tool is identified, it creates an `AgentAction` object with the tool name and parameters. If no tool is identified, it creates an `AgentFinish` object with the final response.

Example:
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
In this example, the `parse` method calls the `extract_using_regex` function to extract information from the input text. It then processes the extracted information to determine the appropriate action or final response.

## Endpoints Used/Created

There are no explicit endpoints used or created within the `llamaAgentParser.py` file. The file focuses on parsing input text and determining the appropriate action or final response based on the extracted information.