# constants.py

**Path:** `src/alita_sdk/langchain/constants.py`

## Data Flow

The `constants.py` file primarily defines constants that are used throughout the codebase. These constants are templates for different response formats and variables used in the LangChain framework. The data flow in this file is minimal as it only involves the definition and storage of string templates and lists. These constants are likely imported and used in other parts of the application where specific response formats are required.

### Example:
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
This example shows the definition of the `REACT_ADDON` constant, which is a string template for response formats.

## Functions Descriptions

This file does not contain any functions. It only defines constants that are used elsewhere in the codebase.

## Dependencies Used and Their Descriptions

This file does not import or depend on any external libraries or modules. It is self-contained and only provides constant values.

## Functional Flow

The functional flow of this file is straightforward. It defines constants that are used as templates for responses in the LangChain framework. These constants are likely imported and utilized in other parts of the application where specific response formats are needed.

### Example:
```python
XML_ADDON = """You have access to the following tools:

{{tools}}

In order to use a tool, you can use <tool></tool> and <tool_input></tool_input> tags. You will then get back a response in the form <observation></observation>
For example, if you have a tool called 'search' that could run a google search, in order to search for the weather in SF you would respond:

<tool>search</tool><tool_input>weather in SF</tool_input>
<observation>64 degrees</observation>

When you are done, respond with a final answer between <final_answer></final_answer>. For example:

<final_answer>The weather in SF is 64 degrees</final_answer>



User's input
--------------------
{{input}}
"""
```
This example shows the definition of the `XML_ADDON` constant, which is another string template for response formats.

## Endpoints Used/Created

This file does not define or interact with any endpoints. It only provides constant values that are used elsewhere in the codebase.