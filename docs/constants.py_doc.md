# constants.py

**Path:** `src/alita_sdk/langchain/constants.py`

## Data Flow

The data flow within `constants.py` is relatively straightforward as it primarily involves the definition of constants that are used throughout the application. These constants are defined as string literals and lists, which are then imported and utilized by other modules in the application. The constants serve as templates and placeholders for various functionalities, such as tool usage instructions and response format guidelines. The data flow can be summarized as follows:

1. **Definition of Constants:** The file defines several constants, including `REACT_ADDON`, `XML_ADDON`, `REACT_VARS`, and `DEFAULT_MULTIMODAL_PROMPT`.
2. **Usage of Constants:** These constants are imported and used by other modules to provide consistent instructions and templates for tool usage and response formatting.

Example:
```python
REACT_ADDON = """
TOOLS
------
Assistant can ask the user to use tools to look up information that may be helpful in answering the users original question. The tools the human can use are:

{{tools}}

RESPONSE FORMAT INSTRUCTIONS
----------------------------

When responding to me, please output a response in one of two formats:

**Option 1:**
Use this if you want the human to use a tool.
Markdown code snippet formatted in the following schema:

```json
{
    "action": string, \ The action to take. Must be one of {{tool_names}}
    "action_input": string \ The input to the action
}
```

**Option #2:**
Use this if you want to respond directly to the human. Markdown code snippet formatted in the following schema:

```json
{
    "action": "Final Answer",
    "action_input": string \ You should put what you want to return to use here
}
```

USER'S INPUT
--------------------
Here is the user's input (remember to respond with a markdown code snippet of a json blob with a single action, and NOTHING else):

{{input}}
"""
```
This example shows the definition of the `REACT_ADDON` constant, which provides a template for tool usage instructions and response formatting.

## Functions Descriptions

The `constants.py` file does not contain any functions. Instead, it focuses on defining constants that are used throughout the application. These constants are essential for maintaining consistency in tool usage instructions and response formatting across different modules.

## Dependencies Used and Their Descriptions

The `constants.py` file does not explicitly import or call any external dependencies. Its primary purpose is to define constants that are used by other modules in the application. Therefore, it does not rely on any external libraries or modules.

## Functional Flow

The functional flow of the `constants.py` file is straightforward. It involves the definition of constants that are used by other modules to provide consistent instructions and templates for tool usage and response formatting. The sequence of operations is as follows:

1. **Definition of Constants:** The file defines several constants, including `REACT_ADDON`, `XML_ADDON`, `REACT_VARS`, and `DEFAULT_MULTIMODAL_PROMPT`.
2. **Usage of Constants:** These constants are imported and used by other modules to provide consistent instructions and templates for tool usage and response formatting.

## Endpoints Used/Created

The `constants.py` file does not define or interact with any endpoints. Its primary purpose is to define constants that are used by other modules in the application. Therefore, it does not involve any network communication or endpoint interactions.
