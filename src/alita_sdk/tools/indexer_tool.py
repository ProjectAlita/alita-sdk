import logging
from json import dumps
from traceback import format_exc

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from typing import Any, Optional, Union
from langchain_core.messages import ToolCall
from langchain_core.utils.function_calling import convert_to_openai_tool
from ..langchain.utils import _extract_json, propagate_the_input_mapping
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class IndexerNode(BaseTool):
    name: str = 'IndexToolNode'
    description: str = 'This is an index tool node for tools'
    tool: BaseTool = None
    index_tool: BaseTool = None
    return_type: str = "str"
    input_mapping: Optional[dict[str, dict]] = None
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None

    def invoke(
        self,
        state: Union[str, dict, ToolCall],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> Any:
        params = convert_to_openai_tool(self.tool).get(
            'function', {'parameters': {}}).get(
            'parameters', {'properties': {}}).get('properties', {})
        func_args = propagate_the_input_mapping(input_mapping=self.input_mapping, input_variables=self.input_variables, state=state)
        
        try:
            result = self.tool.invoke(func_args, config=config, kwargs=kwargs)
            dispatch_custom_event(
                "on_index_tool_node", {
                    "input_variables": self.input_variables,
                    "tool_result": "Completed and generator provided",
                    "state": state,
                }, config=config
            )
            index_results = self.index_tool.invoke({"documents": result}, config=config, kwargs=kwargs)
            logger.info(f"IndexNode response: {index_results}")
            return {
                "messages": [{"role": "assistant", "content": dumps(index_results)}]
            }

        except ValidationError:
            logger.error(f"ValidationError: {format_exc()}")
            return {
                "messages": [{"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {result} raised ValidationError. 
        \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
        {func_args}"""}]}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
