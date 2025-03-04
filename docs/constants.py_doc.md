# constants.py

**Path:** `src/alita_sdk/langchain/constants.py`

## Data Flow

The `constants.py` file primarily defines a set of constants used throughout the `alita_sdk` package. These constants are used to standardize responses and interactions within the SDK, particularly for tool usage and response formatting. The data flow in this file is straightforward as it involves the declaration of string constants and a list. These constants are then imported and used in other parts of the codebase to ensure consistency and reduce the likelihood of errors due to hardcoding values in multiple places.

For example, the `REACT_ADDON` constant is a multi-line string that provides instructions for using tools and formatting responses. This constant is likely used in modules that handle user interactions and tool invocations.

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

This example shows how the `REACT_ADDON` constant is defined and structured. It includes placeholders for dynamic content, which are likely replaced with actual values at runtime.

## Functions Descriptions

The `constants.py` file does not contain any functions. Instead, it defines constants that are used throughout the `alita_sdk` package. These constants include multi-line strings and a list, which are used to standardize responses and interactions within the SDK.

## Dependencies Used and Their Descriptions

The `constants.py` file does not import or depend on any external libraries or modules. It is a standalone file that defines constants used throughout the `alita_sdk` package.

## Functional Flow

The functional flow of the `constants.py` file is straightforward. It involves the declaration of constants that are used in other parts of the `alita_sdk` package. These constants are defined at the top level of the file and are not encapsulated within any functions or classes. The constants include multi-line strings and a list, which are used to standardize responses and interactions within the SDK.

For example, the `DEFAULT_MULTIMODAL_PROMPT` constant is a multi-line string that provides instructions for analyzing different types of images. This constant is likely used in modules that handle image analysis and processing.

```python
DEFAULT_MULTIMODAL_PROMPT = """
## Image Type: Diagrams (e.g., Sequence Diagram, Context Diagram, Component Diagram)
**Prompt**:
"Analyze the given diagram to identify and describe the connections and relationships between components. Provide a detailed flow of interactions, highlighting key elements and their roles within the system architecture. Provide result in functional specification format ready to be used by BA's, Developers and QA's."
## Image Type: Application Screenshots
**Prompt**:
"Examine the application screenshot to construct a functional specification. Detail the user experience by identifying and describing all UX components, their functions, and the overall flow of the screen."
## Image Type: Free Form Screenshots (e.g., Text Documents, Excel Sheets)
**Prompt**:
"Extract and interpret the text from the screenshot. Establish and describe the relationships between the text and any visible components, providing a comprehensive understanding of the content and context."
## Image Type: Mockup Screenshots
**Prompt**:
"Delve into the UX specifics of the mockup screenshot. Offer a detailed description of each component, focusing on design elements, user interactions, and the overall user experience."
### Instructions:
- Ensure clarity and precision in the analysis for each image type.
- Avoid introducing information does not present in the image.
- Maintain a structured and logical flow in the output to enhance understanding and usability.
- Avoid presenting the entire prompt for user.
"""
```

This example shows how the `DEFAULT_MULTIMODAL_PROMPT` constant is defined and structured. It includes instructions for analyzing different types of images and provides a template for generating functional specifications based on the analysis.

## Endpoints Used/Created

The `constants.py` file does not define or interact with any endpoints. It is a standalone file that defines constants used throughout the `alita_sdk` package.