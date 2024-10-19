import logging
from langchain_core.tools import BaseTool
from typing import Any
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage


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
        
    def _run(self, messages, *args, **kwargs):
        if isinstance(messages, list):
            input = messages + [HumanMessage(self.prompt)]
        else:
            input = messages.get("messages") + [HumanMessage(self.prompt)]
        try:
            logger.info(f"LLM Node input: {input}")
            completion = self.client.completion_with_retry(input)
            logger.info(f"LLM Node completion: {completion}")
            return process_response(completion, self.return_type)
        except Exception as e:
            return process_response([AIMessage(f"Error: {e}")], self.return_type)

