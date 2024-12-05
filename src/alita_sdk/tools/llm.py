import logging
from json import dumps
from langchain_core.tools import BaseTool
from typing import Any, Optional
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from ..langchain.utils import _extract_json

logger = logging.getLogger(__name__)

def process_response(response, return_type):
    if return_type == "str":
        return response[0].content.strip()
    else:
        return [{"role": "assistant", "content": response[0].content.strip()}]

class LLMNode(BaseTool):
    name: str = 'LLMNode'
    prompt: str
    description: str = 'This is tool node for LLM'
    client: Any = None
    return_type: str = "str"
    output_variables: Optional[list] = None
    input_variables: Optional[list] = None
        
    def _run(self, *args, **kwargs):
        params = {}
        llm_input = []
        
        for var in self.input_variables:
            if var == 'messages':
                llm_input = kwargs.get("messages")
            else:
                params[var] = kwargs.get(var, "")
        if '{' in self.prompt and '}' in self.prompt:
            try:
                llm_input += [HumanMessage(self.prompt.format(**params))]
            except KeyError:
                llm_input += [HumanMessage(self.prompt + 'State: ' + dumps(params))]
        elif params:
            llm_input += [HumanMessage(self.prompt + 'State: ' + dumps(params))]
        else:
            llm_input += [HumanMessage(self.prompt)]
        try:
            logger.info(f"LLM Node input: {llm_input}")
            completion = self.client.completion_with_retry(llm_input)
            logger.info(f"LLM Node completion: {completion}")
            
            if not self.output_variables or 'messages' in self.output_variables:
                return {"messages": kwargs.get('messages', []) + process_response(completion, self.return_type)}
            else:
                try:
                    response = _extract_json(completion[0].content.strip())
                    resp = {}
                    for key in response.keys():
                        if key in self.output_variables:
                            resp[key] = response[key]
                    return resp
                except ValueError:
                    return { self.output_variables[0]: process_response(completion, 'str') }
        except Exception as e:
            return process_response([AIMessage(f"Error: {e}")], self.return_type)

