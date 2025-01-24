# mixedAgentRenderes.py

**Path:** `src/alita_sdk/langchain/mixedAgentRenderes.py`

## Data Flow

The data flow within `mixedAgentRenderes.py` revolves around the transformation and formatting of agent actions and tool definitions into various string and message formats. The primary data elements include tool definitions, intermediate steps of agent actions, and conversation messages. These elements are manipulated through a series of functions that convert them into specific formats required for logging, displaying, or further processing by the agent.

For example, the function `format_log_to_str` takes a list of intermediate steps, each consisting of an `AgentAction` and a result string, and constructs a formatted string representing the agent's thought process:

```python
thoughts = ""
for action, result in intermediate_steps:
    if action.tool == "echo":
        continue 
    thoughts += "Tool: " + action.tool + " PARAMS of tool: " + str(action.tool_input) + "\n"
    thoughts += action.log
    thoughts += f"\nTool Result:\n{result}"
```

This snippet shows how the function iterates over the intermediate steps, skipping any actions with the tool `echo`, and concatenates the tool name, parameters, log, and result into a single string.

## Functions Descriptions

### `get_instruction_string(custom_tool_definition) -> str`

This function generates an instruction string for a given tool definition. It takes a `custom_tool_definition` object and returns a formatted string instructing the use of the tool.

### `get_parameters_string(custom_tool_definition: BaseTool) -> str`

This function creates a JSON string representation of a tool's parameters. It iterates over the tool's arguments and constructs a dictionary with parameter names, types, and descriptions, which is then converted to a JSON string.

### `render_llama_text_description_and_args(tools: List[BaseTool]) -> str`

This function renders the name, description, and arguments of a list of tools in plain text. It concatenates the instruction and parameter strings for each tool and returns the combined result.

### `render_react_text_description_and_args(tools: List[BaseTool]) -> str`

Similar to the previous function, this one renders the tool information in plain text but formats the arguments differently, using a schema-like representation.

### `format_log_to_str(intermediate_steps: List[Tuple[AgentAction, str]]) -> str`

This function constructs a formatted string representing the agent's thought process based on the intermediate steps of agent actions. It concatenates the tool name, parameters, log, and result for each step.

### `format_to_messages(intermediate_steps: List[Tuple[AgentAction, str]]) -> List[BaseMessage]`

This function converts the intermediate steps into a list of message objects. It creates AI and tool messages based on the action logs and results, and handles special cases for the `echo` tool.

### `format_to_langmessages(intermediate_steps: List[Tuple[AgentAction, str]]) -> List[Dict[str, Any]]`

Similar to `format_to_messages`, this function converts the intermediate steps into a list of message dictionaries, using specific message types from the `langchain_core` library.

### `conversation_to_messages(conversation: List[Dict[str, str]]) -> List[BaseMessage]`

This function formats a conversation (a list of message dictionaries) into a list of `BaseMessage` objects, converting each dictionary based on its role (user, AI, tool, or system).

### `convert_message_to_json(conversation: List[BaseMessage]) -> List[Dict[str, str]]`

This function converts a list of `BaseMessage` objects into a list of message dictionaries, mapping each message type to its corresponding role and content.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging errors and information within the module.
- `json.dumps`: Used to convert Python dictionaries to JSON strings.
- `typing`: Provides type hints for function parameters and return types.
- `uuid.uuid4`: Generates unique identifiers for tool call messages.
- `langchain_core.tools.BaseTool`: Represents a tool definition with name, description, and arguments.
- `langchain_core.agents.AgentAction`: Represents an action taken by an agent, including the tool used and input parameters.
- `langchain_core.messages`: Provides various message types (AIMessage, BaseMessage, SystemMessage, HumanMessage, FunctionMessage) used for formatting conversations and intermediate steps.
- `mixedAgentParser.FORMAT_INSTRUCTIONS`: A constant string used for formatting instructions in the agent's thought process.

## Functional Flow

The functional flow of `mixedAgentRenderes.py` involves several steps:

1. **Tool Definition Rendering**: Functions like `get_instruction_string`, `get_parameters_string`, `render_llama_text_description_and_args`, and `render_react_text_description_and_args` are used to generate text descriptions and argument schemas for tools.
2. **Intermediate Step Formatting**: Functions like `format_log_to_str`, `format_to_messages`, and `format_to_langmessages` process intermediate steps of agent actions, converting them into formatted strings or message objects.
3. **Conversation Formatting**: Functions like `conversation_to_messages` and `convert_message_to_json` handle the conversion of conversations between different formats, ensuring compatibility with the agent's messaging system.

For example, the function `format_to_messages` converts intermediate steps into a list of message objects:

```python
messages = []
for action, result in intermediate_steps:
    if action.tool == "echo":
        continue 
    messages.append(
        {"role": "ai", "content": action.log}
    )
    messages.append(
        {"role": "tool", "content": result, "tool_call_id": str(uuid4())}
    )
```

This snippet shows how the function iterates over the intermediate steps, skipping any actions with the tool `echo`, and creates AI and tool messages based on the action logs and results.

## Endpoints Used/Created

The `mixedAgentRenderes.py` file does not explicitly define or call any external endpoints. Its primary focus is on formatting and rendering data for agent tools and actions within the LangChain framework.