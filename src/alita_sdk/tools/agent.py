import logging
from json import dumps
from traceback import format_exc
from typing import Any, Optional, Union

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class AgentNode(BaseTool):
    name: str = 'AgentNode'
    description: str = 'This is agent node for tools'
    client: Any = None
    tool: BaseTool = None
    return_type: str = "str"
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None
    structured_output: Optional[bool] = False
    task: Optional[str] = None

    def invoke(
            self,
            state: Union[str, dict, ToolCall],
            config: Optional[RunnableConfig] = None,
            **kwargs: Any,
    ) -> Any:
        params = convert_to_openai_tool(self.tool).get(
            'function', {'parameters': {}}).get(
            'parameters', {'properties': {}}).get('properties', {})
        input_ = []
        last_message = {}
        logger.debug(f"AgentNode input: {self.input_variables}")
        logger.debug(f"Output variables: {self.output_variables}")
        for var in self.input_variables:
            if var != 'messages':
                last_message[var] = state[var]
        if self.task:
            task = self.task.format(**last_message, last_message=dumps(last_message))
        else:
            task = 'Input from user: {last_message}'.format(last_message=dumps(last_message))
        try:
            agent_input = {'task': task, 'chat_history': state.get('messages', [])[:] if 'messages' in self.input_variables else None}
            tool_result = self.tool.invoke(agent_input, config=config, kwargs=kwargs)
            dispatch_custom_event(
                "on_tool_node", {
                    "input_variables": self.input_variables,
                    "tool_result": tool_result,
                    "state": state,
                }, config=config
            )
            message_result = tool_result
            if isinstance(tool_result, dict) or isinstance(tool_result, list):
                message_result = dumps(tool_result)
            logger.info(f"AgentNode response: {tool_result}")
            if not self.output_variables:
                return {"messages": [{"role": "assistant", "content": message_result}]}
            else:
                return {self.output_variables[0]: tool_result,
                        "messages": [{"role": "assistant", "content": message_result}]}
        except ValidationError:
            logger.error(f"ValidationError: {format_exc()}")
            return {
                "messages": [{"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {agent_input} raised ValidationError. 
        \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
        {input_[-1].content}"""}]}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
