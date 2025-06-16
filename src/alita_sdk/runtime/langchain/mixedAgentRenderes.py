"""Parser for MixedAgentTools."""
import logging
from json import dumps
from typing import  List, Tuple, Dict, Any
from uuid import uuid4
from langchain_core.tools import BaseTool
from langchain_core.agents import AgentAction
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage, FunctionMessage
from .mixedAgentParser import FORMAT_INSTRUCTIONS
logger = logging.getLogger(__name__)

def get_instruction_string(custom_tool_definition) -> str:
    return f"Use the function '{custom_tool_definition.name}' to '{custom_tool_definition.description}'"

def get_parameters_string(custom_tool_definition: BaseTool) -> str:
    tool = {
        "name": custom_tool_definition.name,
        "description": custom_tool_definition.description,
        "parameters": {}
    }
    print(custom_tool_definition)
    for arg in custom_tool_definition.args.keys():
        tool['parameters'][f'{arg} ({custom_tool_definition.args[arg].get("type", "str")})'] = custom_tool_definition.args[arg].get('description', arg)
    return dumps(tool)


def render_llama_text_description_and_args(tools: List[BaseTool]) -> str:
    """Render the tool name, description, and args in plain text."""
    tool_str = ''
    for tool in tools:
        tool_str += get_instruction_string(tool) + "\n"
        tool_str += get_parameters_string(tool) + "\n\n"
    return tool_str

def render_react_text_description_and_args(tools: List[BaseTool]) -> str:
    """Render the tool name, description, and args in plain text."""
    tool_strings = []
    for tool in tools:
        args_schema = ""
        for arg in tool.args.keys():
            args_schema += f"{arg} ({tool.args[arg].get('type', 'str')}): \"{tool.args[arg].get('description', arg)}\"; "
        tool_strings.append(f' - {tool.description}: tool: "{tool.name}", agrs: {args_schema}')
    return "\n".join(tool_strings)

def format_log_to_str(
    intermediate_steps: List[Tuple[AgentAction, str]],
) -> str:
    """Construct the scratchpad that lets the agent continue its thought process."""
    thoughts = ""
    for action, result in intermediate_steps:
        if action.tool == "echo":
            continue 
        thoughts += "Tool: " + action.tool + " PARAMS of tool: " + str(action.tool_input) + "\n"
        thoughts += action.log
        thoughts += f"\nTool Result:\n{result}"
    try:
        if len(intermediate_steps) and intermediate_steps[-1][0].tool == "echo":
            thoughts += "Your answer was: {intermediate_steps[-1][1]}\nIMPORTANT: YOU MUST ANSWER IN FORMAT: \n{FORMAT_INSTRUCTIONS}"
    except IndexError:
        logger.error("Index error in intermediate state: {intermediate_steps}")
        pass
    return thoughts

def format_to_messages(intermediate_steps: List[Tuple[AgentAction, str]]) -> List[BaseMessage]:
    """Format the intermediate steps to messages."""
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
    try:
        if len(intermediate_steps) and intermediate_steps[-1][0].tool == "echo":
            messages.append({"role": "human", 
                            "content": f"Your answer was: {intermediate_steps[-1][1]}\nIMPORTANT: YOU MUST ANSWER IN FORMAT: \n{FORMAT_INSTRUCTIONS}"})
    except IndexError:
        logger.error("Index error in intermediate state: {intermediate_steps}")
        pass
    return messages

def format_to_langmessages(intermediate_steps: List[Tuple[AgentAction, str]]) -> List[Dict[str, Any]]:
    """Format the intermediate steps to messages."""
    messages = []
    for action, result in intermediate_steps:
        if action.tool == "echo":
            continue 
        messages.append(AIMessage(content=action.log))
        messages.append(FunctionMessage(name=action.tool, content=result, id=str(uuid4())))
    try:
        if len(intermediate_steps) and intermediate_steps[-1][0].tool == "echo":
            messages.append(HumanMessage(content=f"Your answer was: {intermediate_steps[-1][1]}\nIMPORTANT: YOU MUST ANSWER IN FORMAT: \n{FORMAT_INSTRUCTIONS}"))
    except IndexError:
        logger.error("Index error in intermediate state: {intermediate_steps}")
        pass
    return messages

def conversation_to_messages(conversation: List[Dict[str, str]]) -> List[BaseMessage]:
    """Format the conversation to messages."""
    messages = []
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
    return messages

def convert_message_to_json(conversation: List[BaseMessage]) -> List[Dict[str, str]]:
    """Format the conversation to List of Dict"""
    messages = []
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
    return messages