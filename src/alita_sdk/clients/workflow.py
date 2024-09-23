import yaml
from json import dumps
from langgraph.graph import StateGraph, MessagesState
from langchain_core.runnables import Runnable

from langchain_core.tools import BaseTool
from ..utils.utils import clean_string
from ..utils.evaluate import EvaluateTemplate
from ..agents.mixedAgentRenderes import convert_message_to_json

class ConditionalEdge(Runnable):
    def __init__(self, condition: str):
        self.condition = condition
    
    def invoke(self, *args, **kwargs):
        for arg in args:
            print(arg)
            print()
        messages = convert_message_to_json(args[0]['messages'])
        last_message = messages[-1]['content']
        template = EvaluateTemplate(
            self.condition, 
            chat_history=dumps(messages), 
            last_message=last_message)
        res = template.evaluate()
        if isinstance(res, str):
            res = clean_string(res)
        return res

class TransitionalEdge(Runnable):
    def __init__(self, next_step: str):
        self.next_step = next_step
    
    def invoke(self, *args, **kwargs):
        return self.next_step
    
def create_message_graph(yaml_schema: str, tools: list[BaseTool]):
    """ Create a message graph from a yaml schema """
    schema = yaml.safe_load(yaml_schema)
    lg_builder = StateGraph(MessagesState)
    for node in schema['nodes']:
        for tool in tools:
            node_id = clean_string(node['id'])
            if tool.name == node_id:
                lg_builder.add_node(node_id, tool)
                if node.get('next'):
                    next_step=clean_string(node['next'])
                    if node.get('next') != 'END':
                        lg_builder.add_conditional_edges(node_id, TransitionalEdge(next_step))
                elif node.get('condition'):
                    lg_builder.add_conditional_edges(node_id, ConditionalEdge(node['condition']))
                break

    lg_builder.set_entry_point(clean_string(schema['entry_point']))
    
    return lg_builder.compile()
 