import json
import logging
from traceback import format_exc
from typing import Any, Optional, Dict, List

from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool

from ..langchain.utils import _extract_json, create_pydantic_model

logger = logging.getLogger(__name__)


def create_llm_input(prompt: Dict[str, str], params: Dict[str, Any], kwargs: Dict[str, Any]) -> list[HumanMessage]:
    logger.info(f"Creating LLM input with prompt: {prompt}, params: {params}, kwargs: {kwargs}")
    if prompt.get('type') == 'fstring' and params:
        return [HumanMessage(content=PromptTemplate.from_template(prompt['value']).partial(**params).format(**params))]
    elif prompt.get('type') == 'string' and params:
        return [HumanMessage(
            content=f"Current User Input:\n{kwargs['input']}\nPrompt:\n{prompt['value']}")]
    else:
        return kwargs.get("messages") + [HumanMessage(prompt['value'])]


class LLMNode(BaseTool):
    name: str = 'LLMNode'
    prompt: Dict[str, str]
    description: str = 'This is tool node for LLM'
    client: Any = None
    return_type: str = "str"
    response_key: str = "messages"
    output_variables: Optional[List[str]] = None
    input_variables: Optional[List[str]] = None
    structured_output: Optional[bool] = False

    def _run(self, *args, **kwargs):
        params = {var: kwargs.get(var, "") for var in self.input_variables if var != 'messages'}
        logger.info(f"LLM Node params: {params}")
        llm_input = create_llm_input(self.prompt, params, kwargs)
        try:
            if self.structured_output and len(self.output_variables) > 0:
                struct_params = {var: {"type": "str", "description": ""} for var in self.output_variables}
                stuct_model = create_pydantic_model(f"LLMOutput", struct_params)
                llm = self.client.with_structured_output(stuct_model)
                completion = llm.invoke(llm_input)
                result = completion.model_dump()
                return result
            else:
                completion = self.client.invoke(llm_input)
                result = completion.content.strip()
                response = _extract_json(result) or {}
                response_data = {key: response[key] for key in response if key in self.output_variables}
                if not response_data.get('messages'):
                    response_data['messages'] = [
                        {"role": "assistant", "content": response_data.get(self.response_key) or result}]
                return response_data
        except ValueError:
            if self.output_variables:
                return {self.output_variables[0]: result, "messages": [{"role": "assistant", "content": result}]}
            else:
                return {"messages": [{"role": "assistant", "content": result}]}
        except Exception as e:
            logger.error(f"Error in LLM Node: {format_exc()}")
            return {"messages": [{"role": "assistant", "content": f"Error: {e}"}]}
