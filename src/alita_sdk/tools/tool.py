import logging
from json import dumps
from langchain_core.tools import BaseTool
from typing import Any, Optional
from langchain_core.messages import  HumanMessage
from ..langchain.utils import _extract_json
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError
logger = logging.getLogger(__name__)

def process_response(response, return_type):
    if return_type == "str":
        return [ response ]
    else:
        if isinstance(response, str):
            return [ {"role": "assistant", "content": response} ]
        elif isinstance(response, dict):
            if response.get('messages'):
                return response['messages']
            else:
                return [ {"role": "assistant", "content": dumps(response)} ]
        else:
            return [ {"role": "assistant", "content": str(response)} ]

class ToolNode(BaseTool):
    name: str = 'ToolNode'
    description: str = 'This is tool node for tools'
    client: Any = None
    tool: BaseTool = None
    return_type: str = "str"
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None
    prompt: str = """You are tasked to formulate arguments for the tool according to user task and conversation history.
Tool name: {tool_name}
Tool description: {tool_description}
Tool arguments schema: 
{schema}

Input from user: {last_message}  

Expected output is JSON that to be used as a KWARGS for the tool call like {{"key": "value"}} 
in case your key is "messages" value should be a list of messages with roles like {{"messages": [{{"role": "user", "content": "input"}}, {{"role": "assistant", "content": "output"}}]}}.
Tool won't have access to convesation so all keys and values need to be actual and independant. 
Anwer must be JSON only extractable by JSON.LOADS.
"""

    def _run(self, *args, **kwargs):
        params = convert_to_openai_tool(self.tool).get(
            'function',{'parameters': {}}).get(
                'parameters', {'properties': {}}).get('properties', {})
        parameters = ''
        for key in params.keys():
            parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
        # this is becasue messages is shared between all tools and we need to make sure that we are not modifying it
        input = []
        last_message = {}
        for var in self.input_variables:
            if 'messages' in self.input_variables:
                messages = kwargs.get('messages', [])[:]
                input = messages[:-1]
                last_message["user_input"] = messages[-1].content
            else:
                last_message[var] = kwargs[var]
                
        input += [
            HumanMessage(self.prompt.format(
                tool_name=self.tool.name, 
                tool_description=self.tool.description, 
                schema=parameters,
                last_message=dumps(last_message)))
        ]
        logger.info(f"ToolNode input: {input}")
        completion = self.client.completion_with_retry(input)
        result = _extract_json(completion[0].content.strip())
        try:
            tool_result = self.tool.run(result)
            logger.info(f"ToolNode response: {tool_result}")
            if not self.output_variables or 'messages' in self.output_variables:
                return {"messages": kwargs.get('messages', []) + process_response(tool_result, self.return_type)}
            else:
                return { self.output_variables[0]: tool_result }
        except ValidationError:
            return process_response(f"""Tool input to the {self.tool.name} with value {result} raised ValidationError. 
\n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
{input[-1].content}""", self.return_type)

