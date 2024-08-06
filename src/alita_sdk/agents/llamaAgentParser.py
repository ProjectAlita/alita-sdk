import json
import re
from typing import Union

from langchain_core.agents import AgentAction, AgentFinish

from langchain.agents.agent import AgentOutputParser

class UnexpectedResponseError(Exception):
    pass


def extract_using_regex(text) -> dict:
 # Extracting the thoughts section
    pattern = r'<function=(.*?)>(.*?)</?function>'
    match = re.search(pattern, text)
    if match:
        function_name = match.group(1)
        params = match.group(2)
        print(params)
        return {
            "tool": {
                "name": function_name,
                "args": json.loads(params) if params else {}
            }
        }
    else:
        return {
            "final_response": text
        }


class LlamaAgentOutputParser(AgentOutputParser):
    """ Parser for JSON Style Communication Agent """

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        response = extract_using_regex(text)
        
        tool: dict | str | None = response.get("tool", None)
        action = None
        tool_input = {}
        if tool:
            if isinstance(tool, dict):
                action: str | None = tool.get("name")
                tool_input: dict = tool.get("args", {})
            elif isinstance(tool, str):
                action: str | None = tool
                tool_input: dict = response.get("args", {})
            else:
                raise UnexpectedResponseError(f'Unexpected response {response}')
            return AgentAction(action, tool_input, text)
        else:
            return AgentFinish({"output": response.get("final_response", text)}, log=text)

    @property
    def _type(self) -> str:
        return "llama-agent-parser"
