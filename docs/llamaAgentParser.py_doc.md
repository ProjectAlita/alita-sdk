# llamaAgentParser.py

**Path:** `src/alita_sdk/agents/llamaAgentParser.py`

## Data Flow

The data flow within `llamaAgentParser.py` revolves around parsing text input to extract structured information using regular expressions and converting it into specific agent actions or final responses. The primary data elements are the input text, the extracted function name, and parameters, which are then transformed into a dictionary format. This dictionary is used to create instances of `AgentAction` or `AgentFinish` based on the presence of a tool in the response. The data flow can be summarized as follows:

1. **Input Text:** The text input is provided to the `parse` method of the `LlamaAgentOutputParser` class.
2. **Regex Extraction:** The `extract_using_regex` function uses a regular expression to extract the function name and parameters from the input text.
3. **Dictionary Creation:** The extracted information is converted into a dictionary format, with keys `tool` and `final_response`.
4. **Action Determination:** The `parse` method checks for the presence of a tool in the response. If a tool is present, it creates an `AgentAction` instance; otherwise, it creates an `AgentFinish` instance.

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
In this example, the `extract_using_regex` function extracts the function name and parameters from the input text using a regular expression and returns them in a dictionary format.

## Functions Descriptions

### `extract_using_regex`

This function is responsible for extracting the function name and parameters from the input text using a regular expression. It takes a single parameter, `text`, which is the input text to be parsed. The function returns a dictionary with either a `tool` key containing the function name and parameters or a `final_response` key containing the original text.

- **Parameters:**
  - `text` (str): The input text to be parsed.
- **Returns:**
  - dict: A dictionary containing the extracted function name and parameters or the original text.

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

### `LlamaAgentOutputParser`

This class is responsible for parsing the output of a JSON-style communication agent. It inherits from the `AgentOutputParser` class and implements the `parse` method to convert the input text into an `AgentAction` or `AgentFinish` instance.

- **Methods:**
  - `parse(text: str) -> Union[AgentAction, AgentFinish]`: Parses the input text and returns an `AgentAction` or `AgentFinish` instance.
  - `_type -> str`: A property that returns the type of the parser.

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

    @property
    def _type(self) -> str:
        return "llama-agent-parser"
```

## Dependencies Used and Their Descriptions

### `json`

The `json` module is used to parse JSON strings into Python dictionaries. It is used in the `extract_using_regex` function to convert the extracted parameters from a JSON string to a dictionary.

### `re`

The `re` module provides support for regular expressions in Python. It is used in the `extract_using_regex` function to search for patterns in the input text and extract the function name and parameters.

### `typing`

The `typing` module is used to provide type hints for function parameters and return types. It is used in the `LlamaAgentOutputParser` class to specify the return type of the `parse` method.

### `langchain_core.agents`

The `langchain_core.agents` module provides the `AgentAction` and `AgentFinish` classes, which are used to represent the actions and final responses of the agent.

### `langchain.agents.agent`

The `langchain.agents.agent` module provides the `AgentOutputParser` class, which is the base class for the `LlamaAgentOutputParser` class.

## Functional Flow

The functional flow of `llamaAgentParser.py` involves the following steps:

1. **Input Text Parsing:** The `parse` method of the `LlamaAgentOutputParser` class is called with the input text.
2. **Regex Extraction:** The `extract_using_regex` function is called to extract the function name and parameters from the input text.
3. **Response Handling:** The `parse` method checks the response from `extract_using_regex` for the presence of a tool.
4. **Action or Finish Creation:** Based on the presence of a tool, the `parse` method creates an `AgentAction` or `AgentFinish` instance and returns it.

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

## Endpoints Used/Created

There are no explicit endpoints used or created in `llamaAgentParser.py`. The functionality is focused on parsing input text and converting it into structured agent actions or final responses.