from ..clients.client import AlitaPrompt
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import AnyStr


class Prompt(BaseTool):
    name: str
    description: str
    prompt: AlitaPrompt
    
    def _run(self, input, **kwargs):
        if not kwargs:
            return self.prompt.predict(input=input)
        return self.prompt.predict(input=input, variables=kwargs)
    
