# constants.py

**Path:** `src/alita_sdk/langchain/constants.py`

## Data Flow

The `constants.py` file primarily defines constant values that are used throughout the codebase. These constants are used to standardize certain strings and formats, ensuring consistency across different parts of the application. The data flow in this file is minimal as it mainly involves the definition and storage of constant values. These constants are then imported and used in other parts of the application where needed. For example, the `REACT_ADDON` and `XML_ADDON` constants define templates for tool usage instructions and response formats, which are likely used in generating responses or instructions in the application.

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
This example shows the definition of the `REACT_ADDON` constant, which is a template for tool usage instructions and response formats.

## Functions Descriptions

This file does not contain any functions. It is solely dedicated to defining constants that are used throughout the application.

## Dependencies Used and Their Descriptions

This file does not import or depend on any external libraries or modules. It is self-contained and only defines constant values.

## Functional Flow

The functional flow of this file is straightforward. It involves the definition of several constants that are used in other parts of the application. These constants are defined at the top level of the file and are not encapsulated within any functions or classes. The constants include templates for tool usage instructions and response formats (`REACT_ADDON` and `XML_ADDON`), as well as a list of variables used in the REACT template (`REACT_VARS`).

## Endpoints Used/Created

This file does not define or interact with any endpoints. It is solely focused on defining constants that are used elsewhere in the application.