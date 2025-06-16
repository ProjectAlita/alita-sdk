import logging

from langchain_core.tools import BaseTool
from pydantic import field_validator
from typing import Any
from ..utils.utils import clean_string

logger = logging.getLogger(__name__)

def process_response(response, return_type):
    if return_type == "str":
        return response
    else:
        return {"messages": [{"role": "assistant", "content": response}]}


class Prompt(BaseTool):
    name: str
    description: str
    prompt: Any
    return_type: str = "str"
    
    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return clean_string(v)
    
    def _run(self, **kwargs):
        return process_response(self.prompt.predict(variables=kwargs), self.return_type)
    
