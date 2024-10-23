import yaml
import logging
from uuid import uuid4
from typing import Union, Any, Optional
from json import dumps
from langgraph.graph.graph import END, START
from langgraph.graph import StateGraph, MessagesState
from langgraph.store.base import BaseStore
from langgraph.channels.ephemeral_value import EphemeralValue
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables import Runnable
from .mixedAgentRenderes import convert_message_to_json
from ..utils.evaluate import EvaluateTemplate
from ..tools.llm import LLMNode
from ..tools.tool import ToolNode
from ..tools.loop import LoopNode
from ..utils.utils import clean_string
from langgraph.managed.base import is_managed_value

logger = logging.getLogger(__name__)

class ConditionalEdge(Runnable):
    def __init__(self, condition: str):
        self.condition = condition
    
    def invoke(self, messages, config: RunnableConfig, *args, **kwargs):
        input = convert_message_to_json(messages['messages'][:-1])
        last_message = messages['messages'][-1].content
        template = EvaluateTemplate(
            self.condition, 
            chat_history=dumps(input), 
            last_message=last_message)
        result = template.evaluate()
        if isinstance(result, str):
            result = clean_string(result)
        if result == 'END':
            result = END
        return result 

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
        
    def invoke(self, messages, config: RunnableConfig, *args, **kwargs):
        input = messages['messages'][:]
        # Message are shared between all tools so we need to make sure that we are not modifying it
        input.append(HumanMessage(self.prompt.format(steps=self.steps, description=self.description)))
        print(input)
        completion = self.client.completion_with_retry(input)
        result = clean_string(completion[0].content.strip())
        logger.info(f"Plan to transition to: {result}")
        if result not in self.steps or result == 'END':
            result = END
        return result

class TransitionalEdge(Runnable):
    def __init__(self, next_step: str):
        self.next_step = next_step
    
    def invoke(self, messages, config: RunnableConfig, *args, **kwargs):
        logger.info(f'Transitioning to: {self.next_step}')
        return self.next_step if self.next_step != 'END' else END

# def create_message_graph(client: Any, yaml_schema: str, tools: list[BaseTool], memory: Optional[Any] = None):
     
from langgraph.graph.state import CompiledStateGraph
       
class LangGraphAgentRunnable(CompiledStateGraph):
    builder: CompiledStateGraph
    
    @classmethod
    def create_graph(
        cls,
        client: Any, 
        yaml_schema: str, 
        tools: list[BaseTool], 
        *args,
        memory: Optional[Any] = None,
        store: Optional[BaseStore] = None,
        debug: bool = False,
        **kwargs
    ):
        """ Create a message graph from a yaml schema """
        schema = yaml.safe_load(yaml_schema)
        lg_builder = StateGraph(MessagesState)
        interrupt_before = [clean_string(every) for every in schema.get('interrupt_before', [])]
        interrupt_after = [clean_string(every) for every in schema.get('interrupt_after', [])]
        try:
            for node in schema['nodes']:
                node_type = node.get('type', 'function')
                node_id = clean_string(node['id'])
                tool_name = clean_string(node.get('tool', node_id))
                logger.info(f"Node: {node_id} : {node_type} - {tool_name}")
                if node_type in ['function', 'tool', 'loop']:
                    for tool in tools:
                        if tool.name == tool_name:
                            if node_type == 'function':
                                lg_builder.add_node(node_id, tool)
                            elif node_type == 'tool':
                                lg_builder.add_node(node_id, 
                                                    ToolNode(client=client, tool=tool, 
                                                             name=node['id'], return_type='dict'))
                            elif node_type == 'loop':
                                lg_builder.add_node(node_id, 
                                                    LoopNode(client=client, tool=tool, task=node.get('task', ""),
                                                             name=node['id'], return_type='dict'))
                            break
                elif node_type == 'llm':
                    lg_builder.add_node(node_id, 
                                        LLMNode(client=client, prompt=node.get('prompt', ""), name=node['id'], return_type='dict'))
                if node.get('transition'):
                    next_step=clean_string(node['transition'])
                    logger.info(f'Adding transition: {next_step}')
                    lg_builder.add_conditional_edges(node_id, TransitionalEdge(next_step))
                elif node.get('decision'):
                    logger.info(f'Adding decision: {node["decision"]["nodes"]}')
                    lg_builder.add_conditional_edges(node_id, DecisionEdge(
                        client, node['decision']['nodes'], 
                        node['decision'].get('description', "")))
                elif node.get('condition'):
                    logger.info(f'Adding condition: {node["condition"]}')
                    lg_builder.add_conditional_edges(node_id, ConditionalEdge(node['condition']))

            lg_builder.set_entry_point(clean_string(schema['entry_point']))
            
            # assign default values
            interrupt_before = interrupt_before or []
            interrupt_after = interrupt_after or []

            # validate the graph
            lg_builder.validate(
                interrupt=(
                    (interrupt_before if interrupt_before != "*" else []) + interrupt_after
                    if interrupt_after != "*"
                    else []
                )
            )
        except ValueError as e:
            # todo: raise a better error for the user
            raise e

        # prepare output channels
        output_channels = (
            "__root__"
            if len(lg_builder.schemas[lg_builder.output]) == 1
            and "__root__" in lg_builder.schemas[lg_builder.output]
            else [
                key
                for key, val in lg_builder.schemas[lg_builder.output].items()
                if not is_managed_value(val)
            ]
        )
        stream_channels = (
            "__root__"
            if len(lg_builder.channels) == 1 and "__root__" in lg_builder.channels
            else [
                key for key, val in lg_builder.channels.items() if not is_managed_value(val)
            ]
        )
        
        compiled = cls(
            builder=lg_builder,
            config_type=lg_builder.config_schema,
            nodes={},
            channels={
                **lg_builder.channels,
                **lg_builder.managed,
                START: EphemeralValue(lg_builder.input),
            },
            input_channels=START,
            stream_mode="updates",
            output_channels=output_channels,
            stream_channels=stream_channels,
            checkpointer=memory,
            interrupt_before_nodes=interrupt_before,
            interrupt_after_nodes=interrupt_after,
            auto_validate=False,
            debug=debug,
            store=store,
        )

        compiled.attach_node(START, None)
        for key, node in lg_builder.nodes.items():
            compiled.attach_node(key, node)

        for start, end in lg_builder.edges:
            compiled.attach_edge(start, end)

        for starts, end in lg_builder.waiting_edges:
            compiled.attach_edge(starts, end)

        for start, branches in lg_builder.branches.items():
            for name, branch in branches.items():
                compiled.attach_branch(start, name, branch)
                
        logger.info(compiled.get_graph().draw_mermaid())
        return compiled.validate()
        
    
    def invoke(self, input: Union[dict[str, Any], Any], 
               config: Optional[RunnableConfig] = None, 
               *args, **kwargs):
        
        if not config.get("configurable", {}).get("thread_id"):
            config["configurable"] = {"thread_id": str(uuid4())}
        thread_id = config.get("configurable", {}).get("thread_id")       
        if self.checkpointer.get_tuple(config):
            self.update_state(config, {'messages': input['input']})
            output = super().invoke(None, config=config, *args, **kwargs)['messages'][-1].content
        else:
            input = {
                "messages": input.get('chat_history', []) + [{"role": "user", "content": input.get('input')}]
            }
            output = super().invoke(input, config=config, *args, **kwargs)['messages'][-1].content
        thread_id = None
        if self.get_state(config).next:
            thread_id = config['configurable']['thread_id']
        return {
            "output": output,
            "thread_id": thread_id
        }