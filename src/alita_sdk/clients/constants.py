REACT_ADDON = """

### Use the tools from this list of available tools: {{tool_names}}
### When calling "complete_task" tool, provide as much details as possible to address user's request and strictly forward format of anwer if defined

### Tools:
{{tools}} 
- Respond tool: "complete_task", args: "final_answer"  - complete message to be communicated to the user,  must contain generated tests code and as much details as possible for user to understand next steps

### Scratchpad
{{agent_scratchpad}}

### Chat History
{{chat_history}}

### User Input:
{{input}}

### Response format
{
    "thoughts": {
        "text": "message to a user follow the style of your persona",
        "plan": "short bulleted, list that conveys long-term plan",
        "criticism": "constructive self-criticism",
    },
    "tool": {
        "name": "tool name",
        "args": { "arg name": "value" }
    }
}
You must answer with only JSON and it could be parsed by Python json.loads
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
### Response format
{
    "thoughts": {
        "text": "message to a user follow the style of your persona",
        "plan": "short bulleted, list that conveys long-term plan",
        "criticism": "constructive self-criticism",
    },
    "tool": {
        "name": "tool name",
        "args": { "arg name": "value" }
    }
}
You must answer with only JSON and it could be parsed by Python json.loads
"""

ALITA_VARS = ["tool_names", "tools"]