import logging
from json import dumps, loads
from langchain_core.tools import BaseTool
from typing import Any
from langchain_core.messages import HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from ..agents.utils import _old_extract_json
from pydantic.error_wrappers import ValidationError
logger = logging.getLogger(__name__)

def process_response(response, return_type, accumulated_response):
    if return_type == "str":
        accumulated_response += '{response}\n\n'
    else:
        if isinstance(response, str):
            accumulated_response['messages'][-1]["content"] += '{response}\n\n'
        elif isinstance(response, dict):
            if response.get('messages'):
                accumulated_response['messages'][-1]["content"] += "\n\n".join([message['content'] for message in response['messages']])
            else:
                accumulated_response['messages'][-1]['content'] += f"{dumps(response)}\n\n"
        else:
            accumulated_response['messages'][-1]['content'] += f"{str(response)}\n\n"
    return accumulated_response

class LoopNode(BaseTool):
    name: str = 'ToolNode'
    description: str = 'This is tool node for tools'
    client: Any = None
    tool: BaseTool = None
    task: str = ""
    return_type: str = "str"
    prompt: str = """You are tasked to formulate an LIST of ALL inputs for the tool according to user task. Use only chat_history and not this message."
Tool name: {tool_name}
Tool description: {tool_description}
Tool arguments schema: 
{schema}

Task from user: {task}

Expected output is COMLETE LIST OF JSON to be used as sequential kwargs for the tool call. 
You must provide all inputs wthin one LIST OF JSONS, avoid providing them one by one.

EXPETED OUTPUT FORMAT: [{{"messages": ["input1"]}}, {{"messages": ["input2"]}}, ...]
Anwer must be LIST OF JSON only extractable by JSON.LOADS.
"""
    def _run(self, messages, *args, **kwargs):
        params = convert_to_openai_tool(self.tool).get(
            'function',{'parameters': {}}).get(
                'parameters', {'properties': {}}).get('properties', {})
        parameters = ''
        for key in params.keys():
            parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
        # this is becasue messages is shared between all tools and we need to make sure that we are not modifying it
        input = messages[:] + [
            HumanMessage(self.prompt.format(
                tool_name=self.tool.name, 
                tool_description=self.tool.description, 
                schema=parameters,
                task=self.task))
        ]
        completion = self.client.completion_with_retry(input)
        print(f"Loop data: {completion[0].content.strip()}")
    
        loop_data = _old_extract_json(completion[0].content.strip())
        
        if self.return_type == "str":
            accumulated_response = ''
        else:
            accumulated_response = {"messages": [{"role": "assistant", "content": ""}]}
        if isinstance(loop_data, list):
            for each in loop_data:
                try:
                    accumulated_response = process_response(self.tool.run(each), self.return_type, accumulated_response)
                except ValidationError:
                    accumulated_response = process_response(f"""Tool input to the {self.tool.name} with value {loop_data} raised ValidationError.                                             
                                                            \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
                                                            {input[-1].content}""", self.return_type, accumulated_response)
        elif isinstance(loop_data, dict):
            try:
                accumulated_response = process_response(self.tool.run(loop_data), self.return_type, accumulated_response)
            except ValidationError:
                
                accumulated_response =  process_response(f"""Tool input to the {self.tool.name} with value {loop_data} raised ValidationError.                                             
                                                         \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
                                                         {input[-1].content}""", self.return_type, accumulated_response)
        else:
            accumulated_response = process_response(f"""Tool input to the {self.tool.name} with value {loop_data} is not a valid JSON. 
                                                    \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
                                                    {input[-1].content}""", self.return_type, accumulated_response)
        return accumulated_response

