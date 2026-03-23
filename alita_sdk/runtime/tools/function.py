import base64
import json
import logging
from copy import deepcopy

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from langgraph.errors import GraphBubbleUp
from typing import Any, Optional, Union
from langchain_core.utils.function_calling import convert_to_openai_tool

from ..langchain.utils import propagate_the_input_mapping, safe_serialize, object_to_dict

logger = logging.getLogger(__name__)

# State key used to signal that a FunctionTool node was blocked
PIPELINE_BLOCKED_KEY = '_pipeline_blocked'

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
        filtered_state_dict = object_to_dict(filtered_state)
        state_json = safe_serialize(filtered_state_dict)

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

    @staticmethod
    def _is_sensitive_tool_blocked(tool_result: Any) -> bool:
        """Check if the tool result is a sensitive-tool blocked payload."""
        if not isinstance(tool_result, str):
            return False
        try:
            parsed = json.loads(tool_result)
            return isinstance(parsed, dict) and parsed.get('type') == 'sensitive_tool_blocked'
        except (json.JSONDecodeError, TypeError, ValueError):
            return False

    def _build_blocked_termination(self, tool_result: str) -> dict:
        """Build a clean termination result when a FunctionTool's tool is blocked.

        Writes None/empty to all declared output variables so downstream nodes
        don't receive corrupt blocked-result JSON. Adds a clear assistant
        message and sets the ``_pipeline_blocked`` flag so the graph routes
        to END.
        """
        try:
            blocked = json.loads(tool_result)
        except (json.JSONDecodeError, TypeError):
            blocked = {}

        blocked_tool = blocked.get('blocked_tool_name', self.tool.name)
        toolkit_type = blocked.get('blocked_toolkit_type', '')
        node_name = self.name or ''

        # Build a clean, user-friendly markdown message
        parts = [f"**Pipeline stopped** — the action **{blocked_tool}**"]
        details = []
        if toolkit_type:
            details.append(f"toolkit type: *{toolkit_type}*")
        if node_name:
            details.append(f"node: *{node_name}*")
        if details:
            parts[0] += f" ({', '.join(details)})"
        parts[0] += " was **blocked** by user."

        parts.append(
            f"Downstream nodes that depend on `{blocked_tool}` output "
            f"were skipped to prevent invalid data."
        )
        parts.append(
            "> **Tip:** Regenerate this message to re-trigger the approval "
            "request and try again."
        )
        message = "\n\n".join(parts)

        result: dict[str, Any] = {
            "messages": [{"role": "assistant", "content": message}],
            PIPELINE_BLOCKED_KEY: message,
        }

        # Null-out all declared output variables
        if self.output_variables:
            for var in self.output_variables:
                if var != "messages":
                    result[var] = None

        logger.warning(
            "[PIPELINE] FunctionTool '%s' blocked — clean termination. Tool: %s",
            self.name, blocked_tool,
        )
        return result

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

        # For subgraph nodes, also pass through state variables that match child's expected inputs
        # This ensures shared state variables are available in the child
        if hasattr(self.tool, 'is_subgraph') and self.tool.is_subgraph:
            # Merge state variables that aren't already in func_args
            for key, value in state.items():
                if key not in func_args and key not in ['messages', 'input']:
                    func_args[key] = value

        # special handler for PyodideSandboxTool
        if self._is_pyodide_tool():
            func_args['code'] = f"{self._prepare_pyodide_input(state, self.input_variables)}\n{func_args['code']}"

        try:
            tool_result = self.tool.invoke(func_args, config, **kwargs)

            # If the tool was blocked by the sensitive-tool guard (user
            # rejected), return a clean termination instead of propagating
            # the blocked-result JSON as a real tool output.
            if self._is_sensitive_tool_blocked(tool_result):
                return self._build_blocked_termination(tool_result)

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
                    return { self.output_variables[0]: object_to_dict(tool_result) }
        except GraphBubbleUp:
            raise
        except ValueError as value_error:
            # re-raise the error as ToolException since it is related to toolkit configuration:
            # example: incorrect input mappings etc.
            raise ToolException(str(value_error))
        # save the whole error message to the tool's output
        except Exception as e:
            return {"messages": [
                {"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {func_args} raised Exception. 
                        \n\nTool schema is {safe_serialize(params)}. \n\n Details: {e}"""}]}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
