import base64
import json
import logging
from copy import deepcopy
from json import dumps

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from typing import Any, Optional, Union
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from ..langchain.utils import propagate_the_input_mapping
from ..utils.serialization import safe_serialize

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
    alita_client: Optional[Any] = None

    def _prepare_pyodide_input(self, state: Union[str, dict, ToolCall]) -> str:
        """Prepare input for PyodideSandboxTool by injecting state into the code block.

        Uses base64 encoding to avoid string escaping issues when passing JSON
        through multiple layers of parsing (Python -> Deno -> Pyodide).
        """
        state_copy = replace_escaped_newlines(deepcopy(state))

        # remove messages to avoid issues with pickling without langchain-core
        if 'messages' in state_copy:
            del state_copy['messages']

        # Use safe_serialize to handle Pydantic models, datetime, and other non-JSON types
        state_json = safe_serialize(state_copy)

        # Use base64 encoding to avoid all string escaping issues
        # This is more robust than repr() when the code passes through multiple parsers
        state_json_b64 = base64.b64encode(state_json.encode('utf-8')).decode('ascii')

        # Generate code that decodes base64 and parses JSON inside Pyodide
        pyodide_predata = f'''#state dict
import json
import base64
_state_json_b64 = "{state_json_b64}"
_state_json = base64.b64decode(_state_json_b64).decode('utf-8')
alita_state = json.loads(_state_json)
'''
        return pyodide_predata

    def _handle_pyodide_output(self, tool_result: Any) -> dict:
        """Handle output processing for PyodideSandboxTool results."""
        tool_result_converted = {}

        if self.output_variables:
            for var in self.output_variables:
                if var == "messages":
                    tool_result_converted.update(
                        {"messages": [{"role": "assistant", "content": dumps(tool_result)}]})
                    continue
                if isinstance(tool_result, dict) and var in tool_result:
                    tool_result_converted[var] = tool_result[var]
                else:
                    # handler in case user points to a var that is not in the output of the tool
                    tool_result_converted[var] = tool_result.get('result',
                                                                 tool_result.get('error') if tool_result.get('error')
                                                                 else 'Execution result is missing')
        else:
            tool_result_converted.update({"messages": [{"role": "assistant", "content": dumps(tool_result)}]})

        if self.structured_output:
            # execute code tool and update state variables
            try:
                result_value = tool_result.get('result', {})
                if isinstance(result_value, dict):
                    tool_result_converted.update(result_value)
                elif isinstance(result_value, list):
                    # Handle list case - could wrap in a key or handle differently based on requirements
                    tool_result_converted.update({"result": result_value})
                else:
                    # Handle JSON string case
                    tool_result_converted.update(json.loads(result_value))
            except json.JSONDecodeError:
                logger.error(f"JSONDecodeError: {tool_result}")

        return tool_result_converted

    def _is_pyodide_tool(self) -> bool:
        """Check if the current tool is a PyodideSandboxTool."""
        return self.tool.name.lower() == 'pyodide_sandbox'

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

        # special handler for PyodideSandboxTool
        if self._is_pyodide_tool():
            code = func_args['code']
            func_args['code'] = (f"{self._prepare_pyodide_input(state)}\n{code}"
                                # handle new lines in the code properly
                                 .replace('\\n','\\\\n'))
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
            if self._is_pyodide_tool():
                return self._handle_pyodide_output(tool_result)

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
