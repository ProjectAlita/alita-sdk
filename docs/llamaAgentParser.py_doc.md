# llamaAgentParser.py

**Path:** `src/alita_sdk/agents/llamaAgentParser.py`

## Data Flow

The data flow within `llamaAgentParser.py` revolves around parsing text to extract structured information using regular expressions and then converting this information into specific agent actions or final responses. The primary data elements are the input text, the extracted function name and parameters, and the resulting agent actions or final responses. The data originates from the input text provided to the `parse` method of the `LlamaAgentOutputParser` class. This text is then processed by the `extract_using_regex` function, which uses a regular expression to identify and extract the function name and parameters embedded within the text. The extracted data is then returned as a dictionary. The `parse` method further processes this dictionary to determine whether the text corresponds to an agent action or a final response. If an agent action is identified, it creates an `AgentAction` object with the extracted function name and parameters. If no action is identified, it creates an `AgentFinish` object with the final response text. The data flow is thus a linear progression from input text to extracted data to the creation of agent-specific objects.

Example:
```python
def extract_using_regex(text) -> dict:
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
In this example, the `extract_using_regex` function takes the input text, applies a regular expression to extract the function name and parameters, and returns them in a dictionary format.

## Functions Descriptions

### `extract_using_regex`

This function is responsible for extracting structured information from a given text using a regular expression. It takes a single parameter, `text`, which is the input text to be processed. The function applies a regular expression pattern to search for a specific format within the text, specifically looking for a function name and its parameters enclosed within `<function>` tags. If a match is found, it extracts the function name and parameters, converts the parameters from a JSON string to a dictionary (if present), and returns them in a dictionary format. If no match is found, it returns the entire text as the final response.

Example:
```python
def extract_using_regex(text) -> dict:
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
In this example, the function successfully extracts the function name and parameters from the input text and returns them in a structured format.

### `LlamaAgentOutputParser.parse`

This method is part of the `LlamaAgentOutputParser` class and is responsible for parsing the input text to determine the appropriate agent action or final response. It takes a single parameter, `text`, which is the input text to be parsed. The method first calls the `extract_using_regex` function to extract structured information from the text. It then checks if the extracted data contains a tool (function name and parameters). If a tool is present, it creates an `AgentAction` object with the extracted function name and parameters. If no tool is present, it creates an `AgentFinish` object with the final response text.

Example:
```python
def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
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
In this example, the `parse` method processes the input text, extracts the function name and parameters, and creates the appropriate agent-specific object based on the extracted data.

## Dependencies Used and Their Descriptions

### `json`

The `json` module is used to parse JSON strings into Python dictionaries. In this file, it is used within the `extract_using_regex` function to convert the extracted parameters from a JSON string to a dictionary format.

### `re`

The `re` module provides support for regular expressions in Python. It is used in the `extract_using_regex` function to search for and extract specific patterns within the input text.

### `typing`

The `typing` module is used to provide type hints for function parameters and return types. In this file, it is used to specify the return types of the `parse` method and the `extract_using_regex` function.

### `langchain_core.agents`

This module provides the `AgentAction` and `AgentFinish` classes, which are used to represent the actions and final responses of the agent. These classes are used in the `parse` method to create the appropriate agent-specific objects based on the extracted data.

### `langchain.agents.agent`

This module provides the `AgentOutputParser` class, which is the base class for the `LlamaAgentOutputParser` class. The `LlamaAgentOutputParser` class inherits from `AgentOutputParser` and implements the `parse` method to process the input text and extract structured information.

## Functional Flow

The functional flow of `llamaAgentParser.py` begins with the input text being passed to the `parse` method of the `LlamaAgentOutputParser` class. The `parse` method calls the `extract_using_regex` function to extract structured information from the text. The extracted data is then processed to determine whether it contains a tool (function name and parameters) or a final response. If a tool is present, an `AgentAction` object is created with the extracted function name and parameters. If no tool is present, an `AgentFinish` object is created with the final response text. The resulting agent-specific object is then returned as the output of the `parse` method.

Example:
```python
class LlamaAgentOutputParser(AgentOutputParser):
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
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
In this example, the `parse` method processes the input text, extracts the function name and parameters, and creates the appropriate agent-specific object based on the extracted data.

## Endpoints Used/Created

There are no explicit endpoints used or created within `llamaAgentParser.py`. The file focuses on parsing input text and extracting structured information to create agent-specific objects. The interactions are primarily internal, involving the processing of text and the creation of `AgentAction` and `AgentFinish` objects based on the extracted data.