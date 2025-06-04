import logging
from json import dumps
from traceback import format_exc
from typing import Any, Optional, Union, List

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import HumanMessage, ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from .loop import process_response
from ..langchain.utils import _extract_json, create_pydantic_model, propagate_the_input_mapping

logger = logging.getLogger(__name__)


class LoopToolNode(BaseTool):
    name: str = 'LoopToolNode'
    description: str = 'This is loop tool node for tools'
    client: Any = None
    tool: BaseTool = None
    loop_tool: BaseTool = None
    return_type: str = "str"
    variables_mapping: Optional[dict] = None
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
        parameters = ''
        struct_params = {}
        for key in params.keys():
            parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
            struct_params[key] = {"type": params[key].get('type', 'str'),
                                  "description": params[key].get('description', '')}
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
                schema=parameters,
                task=task))
        ]
        if self.return_type == "str":
            accumulated_response = ''
        else:
            accumulated_response = {"messages": [{"role": "assistant", "content": ""}]}
        if self.structured_output:
            struct_model = create_pydantic_model(f"{self.tool.name}Output", struct_params)
            llm = self.client.with_structured_output(struct_model)
            completion = llm.invoke(input_, config=config)
            result = completion.model_dump()
        else:
            input_[-1].content += self.unstructured_output
            completion = self.client.invoke(input_, config=config)
            result = _extract_json(completion.content.strip())
        try:
            tool_result: dict | List[dict] = self.tool.invoke(result, config=config, kwargs=kwargs)
            dispatch_custom_event(
                "on_loop_tool_node", {
                    "input_variables": self.input_variables,
                    "tool_result": tool_result,
                    "state": state,
                }, config=config
            )

            tool_inputs = []
            if not isinstance(tool_result, list):
                tool_result = [tool_result]
            if isinstance(tool_result, list):
                for i in tool_result:
                    if not isinstance(i, dict):
                        logger.error(f'Tool result expected to be dict, but got {type(i)} {i=}')
                        raise TypeError(f'Tool result expected to be dict, but got {type(i)} {i=}')
                    v_mapping = propagate_the_input_mapping(
                        input_mapping=self.variables_mapping,
                        input_variables=self.input_variables,
                        state=state,
                        tool=i
                    )
                    tool_inputs.append(v_mapping)
            else:
                logger.error(f'Tool results expected to be List[dict], but got {type(tool_result)} {tool_result=}')
                raise TypeError(f'Tool results expected to be List[dict], but got {type(tool_result)} {tool_result=}')
            #     tool_inputs.append({list(self.variables_mapping.keys())[0]: tool_result})
            logger.info(f"Loop tool inputs: {tool_inputs}")
            output_variables = dict()
            if len(self.output_variables) > 0:
                output_variables = {self.output_variables[0]: ""}
            for tool_input in tool_inputs:
                logger.info(f"LoopToolNode step input: {tool_input}")
                try:
                    tool_run = self.loop_tool.invoke(tool_input, config=config, kwargs=kwargs)
                    if len(self.output_variables) > 0:
                        output_variables[self.output_variables[0]] += f'{tool_run}\n\n'
                    accumulated_response = process_response(tool_run, self.return_type, accumulated_response)
                except ValidationError:
                    resp = f"""Tool input to the {self.tool.name} with value {tool_input} raised ValidationError.
                                \n\nTool schema is {dumps(params)}"""
                    if len(self.output_variables) > 0:
                        output_variables[self.output_variables[0]] += resp
                    accumulated_response = process_response(resp, self.return_type, accumulated_response)
                    logger.error(f"ValidationError: {format_exc()}")
                except Exception as e:
                    resp = f"""Tool input to the {self.tool.name} with value {tool_input} raised an exception: {e}.                                             
                                \n\nTool schema is {dumps(params)}"""
                    if len(self.output_variables) > 0:
                        output_variables[self.output_variables[0]] += resp
                    accumulated_response = process_response(resp, self.return_type, accumulated_response)
                    logger.error(f"Exception: {format_exc()}")
                logger.info(f"LoopNode response: {accumulated_response}")

        except ValidationError:
            logger.error(f"ValidationError: {format_exc()}")
            return {
                "messages": [{"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {result} raised ValidationError. 
        \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
        {input_[-1].content}"""}]}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
