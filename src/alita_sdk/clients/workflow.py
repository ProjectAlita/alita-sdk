import yaml
from json import dumps
from typing import Any
from langgraph.graph import StateGraph, MessagesState
from langchain_core.runnables import Runnable
from langchain_core.messages import HumanMessage

from langchain_core.tools import BaseTool
from ..utils.utils import clean_string
from ..utils.evaluate import EvaluateTemplate
from ..agents.mixedAgentRenderes import convert_message_to_json
from ..agents.utils import _extract_json

class ConditionalEdge(Runnable):
    def __init__(self, condition: str):
        self.condition = condition
    
    def invoke(self, *args, **kwargs):
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
    

class DecisionEdge(Runnable):
    prompt: str = """Based on chat history make a decision what step need to be next.
Steps available: {steps}
Explanation: {description}
Answer only with step name, no need to add descrip in case none of the steps are applibcable answer with 'END'
"""
    def __init__(self, client, steps: str, description: str = ""):
        self.client = client
        self.steps = ",".join([clean_string(step) for step in steps])
        self.description = description
        
    def invoke(self, *args, **kwargs):
        messages = args[0]['messages']
        messages.append(HumanMessage(self.prompt.format(steps=self.steps, description=self.description)))
        print(messages)
        completion = self.client.completion_with_retry(messages)
        print(completion)
        return completion[0].content.strip()
        

class ToolNode(Runnable):
    prompt: str = """Based on last message in chat history formulate arguments for the tool.
Tool name: {tool_name}
Expected arguments schema: {schema}

Expected output is JSON that could be put as KWARGS to the tool {'key': 'value', 'key2': 'value2'}
Anwer with JSON only to be able to put in in JSON.LOADS
"""
    def __init__(self, client: Any, tool: BaseTool):
        self.client = client
        self.tool = tool
    
    def invoke(self, *args, **kwargs):
        messages = [args[0]['messages'][-1]]
        messages.append(
            HumanMessage(self.prompt.format(tool_name=self.tool.name, schema=dumps(self.tool.args_schema.json())))
        )
        completion = self.client.completion_with_retry(messages)
        print(completion)
        return self.tool.run(_extract_json(completion[0].content.strip()))


class TransitionalEdge(Runnable):
    def __init__(self, next_step: str):
        self.next_step = next_step
    
    def invoke(self, *args, **kwargs):
        return self.next_step
    
def create_message_graph(client: Any, yaml_schema: str, tools: list[BaseTool]):
    """ Create a message graph from a yaml schema """
    schema = yaml.safe_load(yaml_schema)
    lg_builder = StateGraph(MessagesState)
    for node in schema['nodes']:
        node_type = node.get('type', 'function')
        node_id = clean_string(node['id'])
        if node_type in ['function', 'tool']:
            for tool in tools:
                if tool.name == node_id:
                    if node_type == 'function':
                        lg_builder.add_node(node_id, tool)
                    else:
                        lg_builder.add_node(node_id, ToolNode(client=client, tool=tool))
        if node.get('next'):
            next_step=clean_string(node['next'])
            if node.get('next') != 'END':
                lg_builder.add_conditional_edges(node_id, TransitionalEdge(next_step))
        elif node.get('decision'):
            lg_builder.add_conditional_edges(node_id, DecisionEdge(client, node['decision']['nodes'], node['decision'].get('description', "")))
        elif node.get('condition'):
            lg_builder.add_conditional_edges(node_id, ConditionalEdge(node['condition']))

    lg_builder.set_entry_point(clean_string(schema['entry_point']))
    
    return lg_builder.compile()
 