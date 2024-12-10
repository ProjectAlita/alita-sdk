import logging
from traceback import format_exc

from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from typing import Any, Optional
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from ..langchain.utils import _extract_json, create_pydantic_model

logger = logging.getLogger(__name__)

def create_llm_input(prompt: dict[str, str], params: dict, kwargs) -> list[HumanMessage]:
    if prompt.get('type') == 'fstring' and params:
        return [HumanMessage(content=PromptTemplate.from_template(prompt['value']).partial(**params).format(**params))]
    elif prompt.get('type') == 'string' and params:
        return [HumanMessage(
            content=f"Current User Input:\n{kwargs['input']}\nLast LLM Output:\n{params}\nPrompt:\n{prompt['value']}")]
    else:
        return [HumanMessage(content=prompt['value'])]


class LLMNode(BaseTool):
    name: str = 'LLMNode'
    prompt: dict[str, str]
    description: str = 'This is tool node for LLM'
    client: Any = None
    return_type: str = "str"
    response_key: str = "messages"
    output_variables: Optional[list] = None
    input_variables: Optional[list] = None
    structured_output: Optional[bool] = False
        
    def _run(self, *args, **kwargs):
        params = {}
        llm_input = []
        
        for var in self.input_variables:
            if var == 'messages':
                llm_input = kwargs.get("messages")[:]
            else:
                params[var] = kwargs.get(var, "")
        logger.info(f"LLM Node params: {params}")
        llm_input = create_llm_input(self.prompt, params, kwargs)
        try:
            if self.structured_output and len(self.output_variables) > 1:
                struct_params = {}
                for var in self.output_variables:
                    struct_params[var] = {"type": "str", "description": ""}
                stuct_model = create_pydantic_model(f"LLMOutput", struct_params)
                llm = self.client.with_structured_output(stuct_model)
                completion = llm.invoke(llm_input)
                result = completion.model_dump()
                return result
            else:
                completion = self.client.invoke(llm_input)
                result = completion.content.strip()
                if self.output_variables:
                    try:
                        resp = {}
                        response = _extract_json(result)
                        logger.info(f"LLM Node response: {response}")
                        for key in response.keys():
                            if key in self.output_variables:
                                resp[key] = response[key]
                        if not resp.get('messages'):
                            resp['messages'] = [{"role": "assistant", "content": resp.get(self.response_key) or result}]
                        return resp
                    except ValueError:
                        return { self.output_variables[0]: result, "messages": {"role": "assistant", "content": result}}
            if not self.output_variables:
                return {"messages": {"role": "assistant", "content": result}}        
        except Exception as e:
            logger.error(f"Error in LLM Node: {format_exc()}")
            return {"messages": [{"role": "assistant", "content": f"Error: {e}"}]}

