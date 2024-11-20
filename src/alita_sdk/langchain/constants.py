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
