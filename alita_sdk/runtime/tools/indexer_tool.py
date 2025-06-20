import logging
from json import dumps
from traceback import format_exc

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from typing import Any, Optional, Union
from langchain_core.messages import ToolCall
from langchain_core.utils.function_calling import convert_to_openai_tool
from ..langchain.utils import _extract_json, propagate_the_input_mapping
from pydantic import ValidationError
from time import time

logger = logging.getLogger(__name__)

class IndexerNode(BaseTool):
    name: str = 'IndexToolNode'
    description: str = 'This is an index tool node for tools'
    tool: BaseTool = None
    client: Any = None
    index_tool: BaseTool = None
    chunking_tool: str = None
    return_type: str = "str"
    input_mapping: Optional[dict[str, dict]] = None
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None
    chunking_config: Optional[dict] = None
    

    def invoke(
        self,
        state: Union[str, dict, ToolCall],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> Any:
        # TODO: Not cool, but will work for now
        from alita_sdk.tools.chunkers import __all__ as chunkers
        start_time = time()
        params = convert_to_openai_tool(self.tool).get(
            'function', {'parameters': {}}).get(
            'parameters', {'properties': {}}).get('properties', {})
        func_args = propagate_the_input_mapping(input_mapping=self.input_mapping, input_variables=self.input_variables, state=state)
        try:
            result = self.tool.invoke(func_args, config=config, kwargs=kwargs)
            dispatch_custom_event(
                "on_index_tool_node", {
                    "input_variables": self.input_variables,
                    "tool_result": "Document generator provided",
                    "state": state,
                }, config=config
            )
            chunks = None
            if self.chunking_tool:
                try:
                # TODO: Magic parameters need to be explained in the documentation
                    if self.chunking_config.get('embedding_model') and self.chunking_config.get('embedding_model_params'):
                        from ..langchain.interfaces.llm_processor import get_embeddings
                        embedding = get_embeddings(self.chunking_config.get('embedding_model'), 
                                                self.chunking_config.get('embedding_model_params'))
                        self.chunking_config['embedding'] = embedding
                    self.chunking_config['llm'] = self.client
                    chunks = chunkers.get(self.chunking_tool, None)(result, self.chunking_config)
                    dispatch_custom_event(
                        "on_index_tool_node", {
                            "input_variables": self.input_variables,
                            "tool_result": "Chunks generator provided",
                            "state": state,
                        }, config=config
                    )
                except Exception as e:
                    logger.error(f"Chunking error: {format_exc()}")
                    return {"messages": [{"role": "assistant", "content": f"""Chunking tool {self.chunking_tool} raised an error.\n\nError: {format_exc()}"""}]}
            index_results = self.index_tool.invoke({"documents": chunks if chunks else result}, config=config, kwargs=kwargs)
            if isinstance(index_results, ToolException):
                raise index_results
            logger.info(f"IndexNode response: {index_results}")
            total_time = round((time() - start_time), 2)
            index_results['total_time'] = total_time
            return {
                "messages": [{"role": "assistant", "content": dumps(index_results)}]
            }

        except Exception as e:
            logger.error(f"ValidationError: {format_exc()}")
            return {
                "messages": [{"role": "assistant", "content": f"""Tool input to the {self.tool.name} with value {result} raised ValidationError. 
        \n\nTool schema is {dumps(params)} \n\nand the input to LLM was 
        {func_args}\n{e}"""}]}

    def _run(self, *args, **kwargs):
        return self.invoke(**kwargs)
