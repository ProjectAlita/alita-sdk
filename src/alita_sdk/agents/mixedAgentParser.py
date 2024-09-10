import json
from typing import Union

from langchain_core.agents import AgentAction, AgentFinish

from langchain.agents.agent import AgentOutputParser

from .utils import unpack_json

FORMAT_INSTRUCTIONS = """Respond only with JSON format as described below
{
    "thoughts": {
        "text": "message to a user in crisp and clear business language",
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


class UnexpectedResponseError(Exception):
    pass


class MixedAgentOutputParser(AgentOutputParser):
    """ Parser for JSON Style Communication Agent """

    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        try:
            response = unpack_json(text)
        except json.JSONDecodeError:
            return AgentAction("echo", json.dumps({"text": text}), log=f"Echoing: {text}")

        tool = response.get("tool")
        action, tool_input = None, {}

        if tool:
            if isinstance(tool, dict):
                action: str | None = tool.get("name")
                tool_input: dict = tool.get("args", {})
            elif isinstance(tool, str):
                action: str | None = tool
                tool_input: dict = response.get("args", {})
            else:
                raise UnexpectedResponseError(f'Unexpected response {response}')

        thoughts = response.get("thoughts", {})
        log = json.dumps(response, indent=2)

        if not isinstance(thoughts, dict):
            return AgentFinish({"output": f'Unexpected Format: {response}'}, log=log)

        # plan: str = "\n".join(thoughts.get("plan", []))  # not used

        txt = thoughts.get("text", '')

        if action in ['complete_task', 'respond', 'ask_user']:
            output = next(iter(tool_input.values()), tool_input)
            if isinstance(output, str) and output.strip() == "final_answer":
                output = txt
            return AgentFinish({"output": output}, log=log)
        elif action:
            return AgentAction(action, tool_input, log)
        elif txt:
            return AgentFinish({"output": txt}, log=log)
        else:
            return AgentFinish({"output": f"{response}. \n\n *NOTE: Response format wasn't followed*"}, log=log)

    @property
    def _type(self) -> str:
        return "mixed-agent-parser"
