from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import Any


class Prompt(BaseTool):
    name: str
    description: str
    prompt: Any
    
    def _run(self, **kwargs):
        return self.prompt.predict(variables=kwargs)
    
