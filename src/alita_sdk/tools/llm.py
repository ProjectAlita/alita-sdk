import logging
from traceback import format_exc
from typing import Any, Optional, Dict, List

from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.tools import BaseTool

from ..langchain.utils import _extract_json, create_pydantic_model, create_params

logger = logging.getLogger(__name__)


def create_llm_input(prompt: Dict[str, str], params: Dict[str, Any], kwargs: Dict[str, Any]) -> list[BaseMessage]:
    logger.info(f"Creating LLM input with prompt: {prompt}, params: {params}, kwargs: {kwargs}")
    if prompt.get('type') == 'fstring' and params:
        return [HumanMessage(content=prompt['value'].format(**params))]
    else:
        return kwargs.get("messages") + [HumanMessage(prompt['value'])]


class LLMNode(BaseTool):
    name: str = 'LLMNode'
    prompt: Dict[str, str]
    description: str = 'This is tool node for LLM'
    client: Any = None
    return_type: str = "str"
    response_key: str = "messages"
    structured_output_dict: Optional[dict[str, str]] = None
    output_variables: Optional[List[str]] = None
    input_variables: Optional[List[str]] = None
    structured_output: Optional[bool] = False

    def _run(self, *args, **kwargs):
        params = create_params(self.input_variables, kwargs)
        logger.info(f"LLM Node params: {params}")
        llm_input = create_llm_input(self.prompt, params, kwargs)
        try:
            if self.structured_output and len(self.output_variables) > 0:
                struct_params = {
                    key: {
                        "type": 'list[str]' if 'list' in value else value,
                        "description": ""
                    }
                    for key, value in (self.structured_output_dict or {}).items()
                }
                stuct_model = create_pydantic_model(f"LLMOutput", struct_params)
                llm = self.client.with_structured_output(stuct_model)
                completion = llm.invoke(llm_input)
                result = completion.model_dump()
                if result.get('messages') and isinstance(result['messages'], list):
                    result['messages'] = [{'role': 'assistant', 'content': '\n'.join(result['messages'])}]
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
