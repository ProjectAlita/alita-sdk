"""Parser for MixedAgentTools."""
import logging
from typing import  List, Tuple, Dict, Any
from uuid import uuid4
from langchain_core.tools import BaseTool
from langchain_core.agents import AgentAction
from langchain_core.messages import ToolMessage, AIMessage, BaseMessage, SystemMessage, HumanMessage, FunctionMessage
logger = logging.getLogger(__name__)

def render_text_description_and_args(tools: List[BaseTool]) -> str:
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
        thoughts += "Tool: " + action.tool + " PARAMS of tool: " + str(action.tool_input) + "\n"
        thoughts += action.log
        thoughts += f"\nTool Result:\n{result}"
    return thoughts

def format_to_messages(intermediate_steps: List[Tuple[AgentAction, str]]) -> List[BaseMessage]:
    """Format the intermediate steps to messages."""
    messages = []
    for action, result in intermediate_steps:
        messages.append(
            {"role": "ai", "content": action.log}
        )
        messages.append(
            {"role": "tool", "content": result, "tool_call_id": str(uuid4())}
        )
    return messages

def format_to_langmessages(intermediate_steps: List[Tuple[AgentAction, str]]) -> List[Dict[str, Any]]:
    """Format the intermediate steps to messages."""
    messages = []
    for action, result in intermediate_steps:
        messages.append(AIMessage(content=action.log))
        messages.append(FunctionMessage(name=action.tool, content=result, id=str(uuid4())))
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