from langchain_core.tools import BaseTool
from pydantic import validator
from typing import Any
from ..utils.utils import clean_string

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
    
    @validator('name', pre=True, allow_reuse=True)
    def remove_spaces(cls, v):
        return clean_string(v)
    
    def _run(self, **kwargs):
        return process_response(self.prompt.predict(variables=kwargs), self.return_type)
    
