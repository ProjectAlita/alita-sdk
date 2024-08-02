REACT_ADDON = """
### Use the tools from this list of available tools: {{tool_names}}
### When calling "complete_task" tool, provide as much details as possible to address user's request and strictly forward format of anwer if defined

### Tools:
{{tools}} 
- Respond tool: "complete_task", args: "final_answer"  - complete message to be communicated to the user,  must contain generated tests code and as much details as possible for user to understand next steps

To use tool, use following format:
```
{
    "thoughts": {
        "text": "message to a user follow the style of your persona",
        "plan": "short bulleted, list that conveys long-term plan",
    },
    "tool": {
        "name": "tool name",
        "args": { "arg name": "value" }
    }
}
```

To respond to a user, use the following format:
```
{
    "tool": {
        "name": "complete_task",
        "args": { "final_answer": "<complete message to be communicated to the user,  must contain generated tests code and as much details as possible for user to understand next steps>" }
    }
}
```

Begin!

### Previous Conversation History
{{chat_history}}

### User Request:
{{input}}

### Agent Scratchpad:
{{agent_scratchpad}}

"""

REACT_VARS = ["tool_names", "tools", "agent_scratchpad", "chat_history", "input"]


ALITA_ADDON = """
### Use the tools from this list of available tools: {{tool_names}}
### When calling "complete_task" tool, provide as much details as possible to address user's request and strictly forward format of anwer if defined

### Tools:
{{tools}} 
- Respond tool: "complete_task", args: "final_answer"  - complete message to be communicated to the user,  must contain generated tests code and as much details as possible for user to understand next steps
"""

ALITA_OUTPUT_FORMAT = """
```
{
    "thoughts": {
        "text": "message to a user follow the style of your persona",
        "plan": "short bulleted, list that conveys long-term plan",
    },
    "tool": {
        "name": "tool name",
        "args": { "arg name": "value" }
    }
}
```

To respond to a user, use the following format:
```
{
    "tool": {
        "name": "complete_task",
        "args": { "final_answer": "<complete message to be communicated to the user,  must contain generated tests code and as much details as possible for user to understand next steps>" }
    }
}
```
"""

ALITA_VARS = ["tool_names", "tools"]


LLAMA_ADDON = """You have access to the following functions:

{{tools}}
Think very carefully before calling functions.
If you choose to call a function ONLY reply in the following format with no prefix or suffix:

<function=example_function_name>{"example_name": "example_value"}</function>

Reminder:
- If looking for real time information use relevant functions before falling back to brave_search
- Function calls MUST follow the specified format, start with <function= and end with </function>
- Required parameters MUST be specified
- Only call one function at a time from the list of {{tool_names}}
- Put the entire function call reply on one line
"""

LLAMA_VARS = ["tools"]