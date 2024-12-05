import logging
from json import dumps
from langchain_core.tools import BaseTool
from typing import Any, Optional
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError
from .tool import process_response

logger = logging.getLogger(__name__)

class FunctionTool(BaseTool):
    name: str = 'FunctionalTool'
    description: str = 'This is direct call node for tools'
    tool: BaseTool = None
    return_type: str = "str"
    input_variables: Optional[list[str]] = None
    input_mapping: Optional[dict[str, str]] = None
    output_variables: Optional[list[str]] = None

    def _run(self, *args, **kwargs):
        params = convert_to_openai_tool(self.tool).get(
            'function',{'parameters': {}}).get(
                'parameters', {'properties': {}}).get('properties', {})
        
        func_args = {}
        for var in self.input_variables:
            func_args[self.input_mapping[var]] = kwargs.get(var, "")
        try:
            tool_result = self.tool.run(func_args)
            logger.info(f"ToolNode response: {tool_result}")
            if not self.output_variables or 'messages' in self.output_variables:
                return {"messages": kwargs.get('messages', []) + process_response(tool_result, self.return_type)}
            else:
                return { self.output_variables[0]: tool_result }
        except ValidationError:
            return process_response(f"""Tool input to the {self.tool.name} with value {func_args} raised ValidationError. 
\n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
{input[-1].content}""", self.return_type)

