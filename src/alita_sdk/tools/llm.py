import json
import logging
from langchain_core.tools import BaseTool
from typing import Any, Union, Dict, Optional
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from ..langchain.utils import _extract_json

logger = logging.getLogger(__name__)

def process_response(response, return_type):
    if return_type == "str":
        return response[0].content.strip()
    else:
        return {
            "messages": [
                {"role": "assistant", "content": response[0].content.strip()}
            ]
        }

class LLMNode(BaseTool):
    name: str = 'LLMNode'
    prompt: str
    description: str = 'This is tool node for LLM'
    client: Any = None
    return_type: str = "str"
    out_variables: Optional[list] = None
    input_variables: Optional[list] = None
        
    def _run(self, *args, **kwargs):
        logger.info(f'Kwargs in LLM node - {kwargs}')
        if isinstance(kwargs, dict):
            if kwargs.get('messages'):
                llm_input = kwargs.get("messages") + [HumanMessage(self.prompt)]
            else:
                if '{' in self.prompt and '}' in self.prompt and self.input_variables or '{state}' in self.prompt:
                    if self.input_variables:
                        variables = {var: kwargs[var] for var in self.input_variables}
                        llm_input = [HumanMessage(self.prompt.format(**variables))]
                    else:
                        llm_input = [HumanMessage(self.prompt.format(**{'state': json.dumps(kwargs)}))]
                else:
                    llm_input = [HumanMessage(f"Current User Input:\n{kwargs['input']}\nLast LLM Output:\n{kwargs}\nPrompt:\n{self.prompt}")]
        try:
            logger.info(f"LLM Node input: {llm_input}")
            completion = self.client.completion_with_retry(llm_input)
            logger.info(f"LLM Node completion: {completion}")
            if 'json' in completion[0].content.strip():
                result = _extract_json(completion[0].content.strip())
                result['input'] = kwargs['input']
                return result
            elif kwargs.get('messages'):
                return process_response(completion, self.return_type)
            else:
                if self.out_variables:
                    res_response = {'input': kwargs['input'] }
                    for var in self.out_variables:
                        res_response[var] = completion[0].content.strip()
                    return res_response
        except Exception as e:
            return process_response([AIMessage(f"Error: {e}")], self.return_type)

