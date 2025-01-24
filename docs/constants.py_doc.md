# constants.py

**Path:** `src/alita_sdk/langchain/constants.py`

## Data Flow

The `constants.py` file primarily defines constants that are used throughout the codebase. These constants are predefined strings that serve as templates or placeholders for various functionalities. The data flow in this file is straightforward as it involves the declaration of constants which are then imported and used in other parts of the application. The constants defined here do not undergo any transformations; they are static values that provide a consistent reference for other modules. For example, the `REACT_ADDON` constant is a multi-line string that outlines the format for tool usage and response instructions. This constant is likely used in modules that handle user interactions or tool integrations.

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

## Functions Descriptions

This file does not contain any functions. It is solely dedicated to defining constants that are used across the application. Each constant is a string that serves a specific purpose, such as providing templates for tool usage (`REACT_ADDON`) or XML-based tool instructions (`XML_ADDON`). These constants are likely imported into other modules where they are used to standardize responses and interactions.

## Dependencies Used and Their Descriptions

The `constants.py` file does not import any external libraries or modules. It is a standalone file that defines constants. The lack of dependencies makes this file highly portable and easy to maintain. The constants defined here are used by other parts of the application, but this file itself does not rely on any external code.

## Functional Flow

The functional flow of this file is minimal as it only involves the declaration of constants. These constants are then used by other modules in the application. The file serves as a centralized location for defining reusable strings that standardize various functionalities across the codebase. For example, the `REACT_ADDON` constant provides a template for tool usage instructions, which can be used by modules that handle user interactions.

## Endpoints Used/Created

This file does not define or interact with any endpoints. Its sole purpose is to define constants that are used throughout the application. The constants themselves do not make any network requests or handle any endpoint interactions. They are static values that provide a consistent reference for other parts of the codebase.