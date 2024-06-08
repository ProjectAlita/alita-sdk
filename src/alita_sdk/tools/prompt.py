from langchain.tools import BaseTool
from pydantic import validator
from typing import Any

class Prompt(BaseTool):
    name: str
    description: str
    prompt: Any
    
    @validator('name', pre=True, allow_reuse=True)
    def remove_spaces(cls, v):
        return v.replace(' ', '')
    
    def _run(self, **kwargs):
        return self.prompt.predict(variables=kwargs)
    
