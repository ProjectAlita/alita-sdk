import logging
from json import dumps, loads

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from typing import Any, Optional, Union
from langchain_core.messages import HumanMessage, ToolCall
from langchain_core.utils.function_calling import convert_to_openai_tool
from ..langchain.utils import _old_extract_json
from pydantic import ValidationError
from openai import BadRequestError
logger = logging.getLogger(__name__)
from traceback import format_exc

def process_response(response, return_type, accumulated_response):
    if return_type == "str":
        accumulated_response += f'{response}\n\n'
    else:
        if isinstance(response, str):
            accumulated_response['messages'][-1]["content"] += f'{response}\n\n'
        elif isinstance(response, dict):
            if response.get('messages'):
                accumulated_response['messages'][-1]["content"] += "\n\n".join([message['content'] for message in response['messages']]) + "\n\n"
            else:
                accumulated_response['messages'][-1]['content'] += f"{dumps(response)}\n\n"
        else:
            accumulated_response['messages'][-1]['content'] += f"{str(response)}\n\n"
    return accumulated_response

class LoopNode(BaseTool):
    name: str = 'LoopNode'
    description: str = 'This is tool node for tools'
    client: Any = None
    tool: BaseTool = None
    task: str = ""
    output_variables: Optional[list] = None
    input_variables: Optional[list] = None
    return_type: str = "str"
    prompt: str = """You are tasked to formulate an LIST of ALL inputs for the tool according to instrcutions and derived solely from the conversation history. Do not include this message as part of the inputs."

Input data:
- Tool name: {tool_name}
- Tool description: {tool_description}
- Tool arguments schema: 
{schema}

{context}

Instructions to create the input for the tool: 
{task}

Expected output:
- COMLETE LIST OF JSON to be used as sequential kwargs for the tool call. 
- You must provide all inputs wthin one LIST OF JSONS, avoid providing them one by one.
- Anwer must be  LIST OF JSON only extractable by JSON.LOADS.

EXPETED OUTPUT FORMAT: 
- [{{"arg1": "input1", "arg2": "input2"}}, {{"arg1": "input3", "arg2": "input4"}}, ...]
"""

    def invoke(
        self,
        state: Union[str, dict, ToolCall],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> Any:
        params = convert_to_openai_tool(self.tool).get(
            'function', {'parameters': {}}).get(
            'parameters', {'properties': {}}).get('properties', {})
        parameters = ''
        for key in params.keys():
            parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"

        context = ''
        llm_input = []
        for var in self.input_variables:
            if var == 'messages':
                llm_input = state.get("messages")[:]
            else:
                if not context:
                    context += 'Context of the conversation:\n'
                context += f'{var}: {state.get(var, "")}\n'
        logger.info(f"LLM Node params: {params}")

        predict_input = llm_input[:] + [
            HumanMessage(self.prompt.format(
                tool_name=self.tool.name,
                tool_description=self.tool.description,
                context=context,
                schema=parameters,
                task=self.task))]
        logger.debug(f"LoopNode input: {predict_input}")
        completion = self.client.invoke(predict_input, config=config)
        logger.debug(f"LoopNode pure output: {completion}")
        loop_data = _old_extract_json(completion.content.strip())
        logger.debug(f"LoopNode output: {loop_data}")
        if self.return_type == "str":
            accumulated_response = ''
        else:
            accumulated_response = {"messages": [{"role": "assistant", "content": ""}]}
        if len(self.output_variables) > 0:
            output_varibles = {self.output_variables[0]: ""}
        if isinstance(loop_data, dict):
            loop_data = [loop_data]
        if isinstance(loop_data, list):
            for each in loop_data:
                logger.debug(f"LoopNode step input: {each}")
                try:
                    tool_run = self.tool.invoke(each, config=config)
                    if len(self.output_variables) > 0:
                        output_varibles[self.output_variables[0]] += f'{tool_run}\n\n'
                    accumulated_response = process_response(tool_run, self.return_type, accumulated_response)
                except ValidationError:
                    resp = f"""Tool input to the {self.tool.name} with value {loop_data} raised ValidationError.
                        \n\nTool schema is {dumps(params)} \n\nand the input to LLM was {predict_input[-1].content}\n\n"""
                    if len(self.output_variables) > 0:
                        output_varibles[self.output_variables[0]] += resp
                    accumulated_response = process_response(resp, self.return_type, accumulated_response)
                    logger.error(f"ValidationError: {format_exc()}")
                except Exception as e:
                    resp = f"""Tool input to the {self.tool.name} with value {loop_data} raised an exception: {e}.                                             
                        \n\nTool schema is {dumps(params)} \n\nand the input to LLM was {predict_input[-1].content}\n\n"""
                    if len(self.output_variables) > 0:
                        output_varibles[self.output_variables[0]] += resp
                    accumulated_response = process_response(resp, self.return_type, accumulated_response)
                    logger.error(f"Exception: {format_exc()}")
                logger.info(f"LoopNode response: {accumulated_response}")
        else:
            resp = f"""Tool input to the {self.tool.name} with value {loop_data} is not a valid JSON. 
                \n\nTool schema is {dumps(params)} \n\nand the input to LLM was  {predict_input[-1].content}\n\n"""
            if len(self.output_variables) > 0:
                output_varibles[self.output_variables[0]] += resp
            accumulated_response = process_response(f"""Tool input to the {self.tool.name} with value {loop_data} is not a valid JSON. 
                                                    \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
                                                    {predict_input[-1].content}""", self.return_type,
                                                    accumulated_response)
        if len(self.output_variables) > 0:
            accumulated_response[self.output_variables[0]] = output_varibles[self.output_variables[0]]
        dispatch_custom_event(
            "on_loop_node", {
                "input_variables": self.input_variables,
                "accumulated_response": accumulated_response,
                "state": state,
            }, config=config
        )
        return accumulated_response

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)

