import base64
import json
import logging
from copy import deepcopy

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from typing import Any, Optional, Union
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from ..langchain.utils import propagate_the_input_mapping

logger = logging.getLogger(__name__)


def safe_serialize(obj: Any) -> str:
    """
    Safely serialize any object to a JSON string.
    Falls back to str() conversion if json.dumps fails.

    Args:
        obj: Any object to serialize

    Returns:
        JSON string representation of the object
    """
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        # If json.dumps fails, convert to string
        logger.debug(f"JSON serialization failed for {type(obj).__name__}: {e}. Falling back to str() conversion.")
        try:
            return json.dumps(str(obj), ensure_ascii=False)
        except Exception:
            # Ultimate fallback - just return string representation
            return str(obj)


def replace_escaped_newlines(data):
    """
        Replace \\n with \n in all string values recursively.
        Required for sanitization of state variables in code node
    """
    if isinstance(data, dict):
        return {key: replace_escaped_newlines(value) for key, value in data.items()}
    elif isinstance(data, str):
        return data.replace('\\n', '\n')
    else:
        return data

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

    def _prepare_pyodide_input(self, state: Union[str, dict, ToolCall], input_variables: Optional[list[str]] = None) -> str:
        """Prepare input for PyodideSandboxTool by injecting state into the code block.

        Logic for state variable injection:
        - If input_variables is None, empty, or only contains 'messages': inject ALL state variables
        - If input_variables contains specific variable names: inject ONLY those variables (excluding 'messages')

        Uses base64 encoding to avoid string escaping issues when passing JSON
        through multiple layers of parsing (Python -> Deno -> Pyodide) and compression to minimize args list
        """
        import base64
        import zlib

        state_copy = replace_escaped_newlines(deepcopy(state))

        # Always remove 'messages' from state injection
        if 'messages' in state_copy:
            del state_copy['messages']

        # Filter state variables based on input_variables
        # If no input_variables specified or only 'messages', include all state vars
        # Otherwise, include only specified variables (excluding 'messages')
        if input_variables is None or len(input_variables) == 0 or (len(input_variables) == 1 and input_variables[0] == 'messages'):
            # Include all state variables (messages already removed above)
            filtered_state = state_copy
            logger.debug("Code node: injecting ALL state variables into alita_state")
        else:
            # Include only specified variables, excluding 'messages'
            filtered_state = {}
            for var in input_variables:
                if var != 'messages' and var in state_copy:
                    filtered_state[var] = state_copy[var]
            logger.debug(f"Code node: injecting ONLY specified variables into alita_state: {list(filtered_state.keys())}")

        # Use safe_serialize to handle Pydantic models, datetime, and other non-JSON types
        state_json = safe_serialize(filtered_state)

        # Use base64 encoding to avoid all string escaping issues
        # This is more robust than repr() when the code passes through multiple parsers
        # use compression to avoid issue with `{"error": "Error executing code: [Errno 7] Argument list too long: 'deno'"}`
        compressed = zlib.compress(state_json.encode('utf-8'))
        encoded = base64.b64encode(compressed).decode('ascii')

        pyodide_predata = f'''#state dict
import json
import base64
import zlib

compressed_state = base64.b64decode('{encoded}')
state_json = zlib.decompress(compressed_state).decode('utf-8')
alita_state = json.loads(state_json)
'''
        return pyodide_predata

    def _handle_pyodide_output(self, tool_result: Any) -> dict:
        """Handle output processing for PyodideSandboxTool results."""
        tool_result_converted = {}

        if self.output_variables:
            for var in self.output_variables:
                if var == "messages":
                    tool_result_converted.update(
                        {"messages": [{"role": "assistant", "content": safe_serialize(tool_result)}]})
                    continue
                if isinstance(tool_result, dict) and var in tool_result:
                    tool_result_converted[var] = tool_result[var]
                else:
                    # handler in case user points to a var that is not in the output of the tool
                    tool_result_converted[var] = tool_result.get('result',
                                                                 tool_result.get('error') if tool_result.get('error')
                                                                 else 'Execution result is missing')
        else:
            tool_result_converted.update({"messages": [{"role": "assistant", "content": safe_serialize(tool_result)}]})

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
            # replace new lines in strings in code block
            code = func_args['code'].replace('\\n', '\\\\n')
            func_args['code'] = f"{self._prepare_pyodide_input(state, self.input_variables)}\n{code}"
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
                return {"messages": [{"role": "assistant", "content": safe_serialize(tool_result)}]}
            else:
                if "messages" in self.output_variables:
                    if isinstance(tool_result, dict) and 'messages' in tool_result:
                        # case when the sub-graph has been executed
                        messages_dict = {"messages": tool_result['messages']}
                    else:
                        messages_dict = {
                            "messages": [{
                                "role": "assistant",
                                "content": safe_serialize(tool_result)
                                if not isinstance(tool_result, ToolException) and not isinstance(tool_result, str)
                                else str(tool_result)
                            }]
                        }
                    for var in self.output_variables:
                        if var != "messages":
                            if isinstance(tool_result, dict) and var in tool_result:
                                messages_dict[var] = tool_result[var]
                            else:
                                messages_dict[var] = tool_result
                    return messages_dict
                else:
                    return { self.output_variables[0]: tool_result }
        except ValidationError:
            return {"messages": [
                {"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {func_args} raised ValidationError. 
        \n\nTool schema is {safe_serialize(params)} \n\nand the input to LLM was 
        {func_args}"""}]}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
