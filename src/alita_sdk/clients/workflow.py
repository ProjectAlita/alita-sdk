import yaml
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import HumanMessage
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph, MessagesState, MessageGraph
from langgraph.prebuilt import ToolNode
# from ..utils.sandbox import exec_code

from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel
from pydantic.fields import FieldInfo
from multiprocessing import Pool

# class CodeRun(BaseTool):
#     name: str
#     description: str 
#     code: str
    
#     def _run(self, state: MessagesState):
#         pool = Pool(processes = 1)
#         print(state)
#         print(self.code)
#         p = pool.map(exec_code, [self.code])
#         return p[0]


def create_message_graph(yaml_schema: str, tools: list[BaseTool]):
    """ Create a message graph from a yaml schema """
    schema = yaml.safe_load(yaml_schema)
    lg_builder = StateGraph(MessagesState)
    previous_node = None
    for node in schema['nodes']:
        if node.get('type', 'function') == 'function':
            for tool in tools:
                if tool.name == node['id']:
                    lg_builder.add_node(node['id'], tool)
                    if previous_node:
                        lg_builder.add_edge(previous_node, node['id'])
                    previous_node = node['id']
                    break
    lg_builder.set_entry_point(schema['entry_point'])
    return lg_builder.compile()