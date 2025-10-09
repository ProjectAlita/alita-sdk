import json
import logging
from json import dumps

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from typing import Any, Optional, Union, Annotated
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError
from ..langchain.utils import propagate_the_input_mapping

logger = logging.getLogger(__name__)


class FunctionTool(BaseTool):
    name: str = 'FunctionalTool'
    description: str = 'This is direct call node for tools'
    tool: BaseTool = None
    return_type: str = "str"
    input_variables: Optional[list[str]] = None
    input_mapping: Optional[dict[str, dict]] = None
    output_variables: Optional[list[str]] = None
    structured_output: Optional[bool] = False

    def invoke(
            self,
            state: Union[str, dict, ToolCall],
            config: Optional[RunnableConfig] = None,
            **kwargs: Any,
    ) -> Any:
        params = convert_to_openai_tool(self.tool).get(
            'function', {'parameters': {}}).get(
            'parameters', {'properties': {}}).get('properties', {})
        func_args = propagate_the_input_mapping(input_mapping=self.input_mapping, input_variables=self.input_variables,
                                                state=state)
        try:
            tool_result = self.tool.invoke(func_args, config, **kwargs)
            dispatch_custom_event(
                "on_function_tool_node", {
                    "input_mapping": self.input_mapping,
                    "input_variables": self.input_variables,
                    "state": state,
                    "tool_result": tool_result,
                }, config=config
            )
            logger.info(f"ToolNode response: {tool_result}")
            # handler for PyodideSandboxTool
            if self.tool.name.lower() == 'pyodide_sandbox':
                tool_result_converted = {}
                if self.output_variables:
                    for var in self.output_variables:
                        if var in tool_result:
                            tool_result_converted[var] = tool_result[var]
                        else:
                            # handler in case user points to a var that is not in the output of the tool
                            tool_result_converted[var] = tool_result.get('result', 'Execution result is missing')
                else:
                    tool_result_converted.update({"messages": [{"role": "assistant", "content": dumps(tool_result)}]})

                if self.structured_output:
                    # execute code tool and update state variables
                    try:
                        result_value = tool_result.get('result', {})
                        tool_result_converted.update(result_value if isinstance(result_value, dict)
                                                     else json.loads(result_value))
                    except json.JSONDecodeError:
                        logger.error(f"JSONDecodeError: {tool_result}")
                return tool_result_converted

            if not self.output_variables:
                return {"messages": [{"role": "assistant", "content": dumps(tool_result)}]}
            else:
                if self.output_variables[0] == "messages":
                    return {
                        "messages": [{
                            "role": "assistant",
                            "content": dumps(tool_result) if not isinstance(tool_result, ToolException) else str(
                                tool_result)
                        }]
                    }
                else:
                    return { self.output_variables[0]: tool_result }
        except ValidationError:
            return {"messages": [
                {"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {func_args} raised ValidationError. 
        \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
        {func_args}"""}]}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
