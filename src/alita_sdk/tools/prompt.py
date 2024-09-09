from langchain_core.tools import BaseTool
from pydantic import validator
from typing import Any
from ..utils.utils import clean_string

class Prompt(BaseTool):
    name: str
    description: str
    prompt: Any
    
    @validator('name', pre=True, allow_reuse=True)
    def remove_spaces(cls, v):
        return clean_string(v)
    
    def _run(self, **kwargs):
        return self.prompt.predict(variables=kwargs)
    
