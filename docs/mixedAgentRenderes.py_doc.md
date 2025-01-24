# mixedAgentRenderes.py

**Path:** `src/alita_sdk/langchain/mixedAgentRenderes.py`

## Data Flow

The data flow within `mixedAgentRenderes.py` revolves around the transformation and formatting of tool descriptions and intermediate steps into various message formats. The primary data elements include tool definitions, intermediate steps, and conversation messages. These elements are manipulated through functions that convert them into strings or structured message formats. The data originates from tool definitions and intermediate steps, which are then processed and transformed into formatted strings or message objects. The final destination of the data is typically a log or a message queue that facilitates further processing or communication.

Example:
```python
for action, result in intermediate_steps:
    if action.tool == "echo":
        continue 
    thoughts += "Tool: " + action.tool + " PARAMS of tool: " + str(action.tool_input) + "\n"
    thoughts += action.log
    thoughts += f"\nTool Result:\n{result}"
```
In this snippet, intermediate steps are processed to construct a string representation of the tool's actions and results.

## Functions Descriptions

1. **get_instruction_string(custom_tool_definition)**
   - **Purpose:** Generates an instruction string for a given tool definition.
   - **Inputs:** `custom_tool_definition` (object containing tool name and description)
   - **Outputs:** A formatted string instruction.
   - **Example:**
   ```python
   return f"Use the function '{custom_tool_definition.name}' to '{custom_tool_definition.description}'"
   ```

2. **get_parameters_string(custom_tool_definition: BaseTool)**
   - **Purpose:** Generates a JSON string of the tool's parameters.
   - **Inputs:** `custom_tool_definition` (BaseTool object)
   - **Outputs:** A JSON string of the tool's parameters.
   - **Example:**
   ```python
   for arg in custom_tool_definition.args.keys():
       tool['parameters'][f'{arg} ({custom_tool_definition.args[arg].get("type", "str")})'] = custom_tool_definition.args[arg].get('description', arg)
   return dumps(tool)
   ```

3. **render_llama_text_description_and_args(tools: List[BaseTool])**
   - **Purpose:** Renders tool descriptions and arguments in plain text.
   - **Inputs:** `tools` (List of BaseTool objects)
   - **Outputs:** A plain text string of tool descriptions and arguments.
   - **Example:**
   ```python
   for tool in tools:
       tool_str += get_instruction_string(tool) + "\n"
       tool_str += get_parameters_string(tool) + "\n\n"
   return tool_str
   ```

4. **render_react_text_description_and_args(tools: List[BaseTool])**
   - **Purpose:** Renders tool descriptions and arguments in plain text for React.
   - **Inputs:** `tools` (List of BaseTool objects)
   - **Outputs:** A plain text string of tool descriptions and arguments.
   - **Example:**
   ```python
   for tool in tools:
       args_schema = ""
       for arg in tool.args.keys():
           args_schema += f"{arg} ({tool.args[arg].get('type', 'str')}): \"{tool.args[arg].get('description', arg)}\"; "
       tool_strings.append(f' - {tool.description}: tool: "{tool.name}", agrs: {args_schema}')
   return "\n".join(tool_strings)
   ```

5. **format_log_to_str(intermediate_steps: List[Tuple[AgentAction, str]])**
   - **Purpose:** Constructs a scratchpad for the agent's thought process.
   - **Inputs:** `intermediate_steps` (List of tuples containing AgentAction and result strings)
   - **Outputs:** A formatted string representing the agent's thought process.
   - **Example:**
   ```python
   for action, result in intermediate_steps:
       if action.tool == "echo":
           continue 
       thoughts += "Tool: " + action.tool + " PARAMS of tool: " + str(action.tool_input) + "\n"
       thoughts += action.log
       thoughts += f"\nTool Result:\n{result}"
   ```

6. **format_to_messages(intermediate_steps: List[Tuple[AgentAction, str]])**
   - **Purpose:** Formats intermediate steps into message objects.
   - **Inputs:** `intermediate_steps` (List of tuples containing AgentAction and result strings)
   - **Outputs:** A list of message objects.
   - **Example:**
   ```python
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

7. **format_to_langmessages(intermediate_steps: List[Tuple[AgentAction, str]])**
   - **Purpose:** Formats intermediate steps into language-specific message objects.
   - **Inputs:** `intermediate_steps` (List of tuples containing AgentAction and result strings)
   - **Outputs:** A list of language-specific message objects.
   - **Example:**
   ```python
   for action, result in intermediate_steps:
       if action.tool == "echo":
           continue 
       messages.append(AIMessage(content=action.log))
       messages.append(FunctionMessage(name=action.tool, content=result, id=str(uuid4())))
   ```

8. **conversation_to_messages(conversation: List[Dict[str, str]])**
   - **Purpose:** Formats a conversation into message objects.
   - **Inputs:** `conversation` (List of dictionaries representing conversation messages)
   - **Outputs:** A list of message objects.
   - **Example:**
   ```python
   for message in conversation:
       if isinstance(message, BaseMessage):
           messages.append(message)
       elif isinstance(message, dict):
           if message["role"] == "user":
               messages.append(HumanMessage(content=message["content"]))
           elif message["role"] == "ai" or message["role"] == "bot" or message["role"] == "assistant":
               messages.append(AIMessage(content=message["content"]))
           elif message["role"] == "tool":
               messages.append(HumanMessage(content=message["content"]))
           else:
               messages.append(SystemMessage(content=message["content"]))
   ```

9. **convert_message_to_json(conversation: List[BaseMessage])**
   - **Purpose:** Converts message objects into JSON format.
   - **Inputs:** `conversation` (List of BaseMessage objects)
   - **Outputs:** A list of dictionaries representing the messages in JSON format.
   - **Example:**
   ```python
   for message in conversation:
       if isinstance(message, dict):
           messages.append(message)
       elif message.type == 'human':
           messages.append({"role": "user", "content": message.content})
       elif message.type == 'ai':
           messages.append({"role": "assistant", "content": message.content})
       elif message.type == 'system':
           messages.append({"role": "system", "content": message.content})
       else:
           messages.append({"role": "assistant", "content": message.content})
   ```

## Dependencies Used and Their Descriptions

1. **logging**
   - **Purpose:** Used for logging error messages and debugging information.
   - **Example:**
   ```python
   logger = logging.getLogger(__name__)
   logger.error("Index error in intermediate state: {intermediate_steps}")
   ```

2. **json.dumps**
   - **Purpose:** Converts Python objects into JSON strings.
   - **Example:**
   ```python
   return dumps(tool)
   ```

3. **uuid.uuid4**
   - **Purpose:** Generates unique identifiers for tool calls.
   - **Example:**
   ```python
   messages.append(FunctionMessage(name=action.tool, content=result, id=str(uuid4())))
   ```

4. **langchain_core.tools.BaseTool**
   - **Purpose:** Represents the base class for tools used in the agent.
   - **Example:**
   ```python
   from langchain_core.tools import BaseTool
   ```

5. **langchain_core.agents.AgentAction**
   - **Purpose:** Represents actions taken by the agent.
   - **Example:**
   ```python
   from langchain_core.agents import AgentAction
   ```

6. **langchain_core.messages**
   - **Purpose:** Provides various message classes for communication.
   - **Example:**
   ```python
   from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage, FunctionMessage
   ```

## Functional Flow

The functional flow of `mixedAgentRenderes.py` involves several key steps:
1. **Tool Description Rendering:** Functions like `render_llama_text_description_and_args` and `render_react_text_description_and_args` are used to render tool descriptions and arguments into plain text.
2. **Intermediate Step Formatting:** Functions like `format_log_to_str`, `format_to_messages`, and `format_to_langmessages` are used to format intermediate steps into strings or message objects.
3. **Conversation Formatting:** Functions like `conversation_to_messages` and `convert_message_to_json` are used to format conversations into message objects or JSON format.

Example:
```python
for tool in tools:
    tool_str += get_instruction_string(tool) + "\n"
    tool_str += get_parameters_string(tool) + "\n\n"
return tool_str
```
In this snippet, tool descriptions and arguments are rendered into plain text.

## Endpoints Used/Created

There are no explicit endpoints defined or used within `mixedAgentRenderes.py`. The file primarily focuses on formatting and rendering data for internal processing and communication.