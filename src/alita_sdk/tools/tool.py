import logging
from json import dumps
from traceback import format_exc
from typing import Any, Optional, Union

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import HumanMessage, ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError, BaseModel, create_model

from .application import Application
from ..langchain.utils import _extract_json

logger = logging.getLogger(__name__)


class ToolNode(BaseTool):
    name: str = 'ToolNode'
    description: str = 'This is tool node for tools'
    client: Any = None
    tool: BaseTool = None
    return_type: str = "str"
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None
    structured_output: Optional[bool] = False
    task: Optional[str] = None
    prompt: str = """You are tasked to formulate arguments for the tool according to user task and conversation history.
Tool name: {tool_name}
Tool description: {tool_description}
Tool arguments schema: 
{schema}

{task}  

"""
    unstructured_output: str = """Expected output is JSON that to be used as a KWARGS for the tool call like {{"key": "value"}} 
in case your key is "chat_history" value should be a list of messages with roles like {{"chat_history": [{{"role": "user", "content": "input"}}, {{"role": "assistant", "content": "output"}}]}}.
Tool won't have access to conversation so all keys and values need to be actual and independent.
Answer must be JSON only extractable by JSON.LOADS."""

    def invoke(
            self,
            state: Union[str, dict, ToolCall],
            config: Optional[RunnableConfig] = None,
            **kwargs: Any,
    ) -> Any:
        params = convert_to_openai_tool(self.tool).get(
            'function', {'parameters': {}}).get(
            'parameters', {'properties': {}}).get('properties', {})
        # this is becasue messages is shared between all tools and we need to make sure that we are not modifying it
        input_ = []
        last_message = {}
        logger.debug(f"ToolNode input: {self.input_variables}")
        logger.debug(f"Output variables: {self.output_variables}")
        for var in self.input_variables:
            if 'messages' in self.input_variables:
                messages = state.get('messages', [])[:]
                input_ = messages[:-1]
                last_message["user_input"] = messages[-1].content
            else:
                last_message[var] = state[var]
        logger.debug(f"ToolNode input: {input_}")
        if self.task:
            task = self.task.format(**last_message, last_message=dumps(last_message))
        else:
            task = 'Input from user: {last_message}'.format(last_message=dumps(last_message))
        input_ += [
            HumanMessage(self.prompt.format(
                tool_name=self.tool.name,
                tool_description=self.tool.description,
                schema=params,
                task=task
            ))
        ]
        if self.structured_output:
            # cut defaults from schema and remove chat_history for application as a tool
            fields = {name: (field.annotation, ...) for name, field
                      in self.tool.args_schema.model_fields.items() if name != 'chat_history'}
            input_schema = create_model('NewModel', **fields)

            llm = self.client.with_structured_output(input_schema)
            completion = llm.invoke(input_, config=config)
            result = completion.model_dump()
        else:
            input_[-1].content += self.unstructured_output
            completion = self.client.invoke(input_, config=config)
            result = _extract_json(completion.content.strip())
            logger.info(f"ToolNode tool params: {result}")
        try:
            # handler for application added as a tool
            if isinstance(self.tool, Application):
                # set empty chat history
                result['chat_history'] = None
            tool_result = self.tool.invoke(result, config=config, kwargs=kwargs)
            dispatch_custom_event(
                "on_tool_node", {
                    "input_variables": self.input_variables,
                    "tool_result": tool_result,
                    "state": state,
                }, config=config
            )
            message_result = tool_result
            if isinstance(tool_result, dict) or isinstance(tool_result, list):
                try:
                    message_result = dumps(tool_result)
                except TypeError:
                    logger.error(f"ToolNode tool result is not JSON serializable: {tool_result}")
                    message_result = str(tool_result)
            logger.info(f"ToolNode response: {tool_result}")
            if not self.output_variables:
                return {"messages": [{"role": "assistant", "content": message_result}]}
            else:
                return {self.output_variables[0]: tool_result,
                        "messages": [{"role": "assistant", "content": message_result}]}
        except ValidationError:
            logger.error(f"ValidationError: {format_exc()}")
            return {
                "messages": [{"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {result} raised ValidationError. 
        \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
        {input_[-1].content}"""}]}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
