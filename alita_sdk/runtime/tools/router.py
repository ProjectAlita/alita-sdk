import logging
import re
from typing import Any, Optional, Union, List
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from ..utils.evaluate import EvaluateTemplate
from ..utils.utils import clean_string

logger = logging.getLogger(__name__)

def clean_node_str(s: str)-> str:
        cleaned_string = re.sub(r'[^\w\s]', '', s)
        return cleaned_string

class RouterNode(BaseTool):
    name: str = 'RouterNode'
    description: str = 'A router node that evaluates a condition and routes accordingly.'
    condition: str = ''
    routes: List[str] = []  # List of possible output node keys
    default_output: str = 'END'
    input_variables: Optional[list[str]] = None

    def invoke(self, state: Union[str, dict], config: Optional[RunnableConfig] = None, **kwargs: Any) -> dict:
        input_data = {}
        for field in self.input_variables or []:
            input_data[field] = state.get(field, "")
        template = EvaluateTemplate(self.condition, input_data)
        result = template.evaluate()
        logger.info(f"RouterNode evaluated condition '{self.condition}' with input {input_data} => {result}")
        result = clean_node_str(str(result))
        if result in self.routes:
            # If the result is one of the routes, return it
            return {"router_output": result}
        elif result == self.default_output:
            # If the result is the default output, return it
            return {"router_output": clean_string(self.default_output)}
        return {"router_output": 'END'}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
