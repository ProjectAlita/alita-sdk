from langchain_core.tools import BaseTool
from pydantic import field_validator
from typing import Any, Optional
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
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None
    current_state: Optional[dict] = None

    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return clean_string(v)
    
    def _run(self, *args, **kwargs):
        if kwargs.get('messages'):
            return process_response(self.prompt.predict(variables=kwargs), self.return_type)
        else:
            if self.input_variables:
                prompt_input = {var: self.current_state[var] for var in self.input_variables}
                prompt_response = self.prompt.predict(variables=prompt_input)
                return prompt_response
            else:
                prompt_response = self.prompt.predict(variables=self.current_state)
                return prompt_response


    
