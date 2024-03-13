"""Parser for MixedAgentTools."""
import logging
from typing import  List, Tuple, Dict, Any
from langchain_core.tools import BaseTool
from langchain_core.agents import AgentAction
from langchain_core.messages import ToolMessage, AIMessage
logger = logging.getLogger(__name__)

def render_text_description_and_args(tools: List[BaseTool]) -> str:
    """Render the tool name, description, and args in plain text."""
    tool_strings = []
    for tool in tools:
        args_schema = ""
        for arg in tool.args.keys():
            args_schema += f"{arg} ({tool.args[arg]['type']}): \"{tool.args[arg].get('description', arg)}\"; "
        tool_strings.append(f' - {tool.description}: tool: "{tool.name}", agrs: {args_schema}')
    return "\n".join(tool_strings)

def format_log_to_str(
    x: Dict[str, Any],
) -> str:
    """Construct the scratchpad that lets the agent continue its thought process."""
    thoughts = ""
    if x.get("memory"):
        x("memory").save_context({"input": action.log, "output": result})
    # TODO: In case I'll pass chat_history to an agent this is the prace I can fill it up
    for action, result in x['intermediate_steps']:
        thoughts += action.log
        thoughts += f"\nTool Result:\n{result}"
    return thoughts
