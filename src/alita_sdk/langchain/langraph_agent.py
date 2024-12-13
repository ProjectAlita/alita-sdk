import yaml
import logging
from uuid import uuid4
from typing import Union, Any, Optional, Annotated
from langgraph.graph.graph import END, START
from langgraph.graph import StateGraph
from langgraph.channels.ephemeral_value import EphemeralValue
from langgraph.managed.base import is_managed_value
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables import Runnable
from .mixedAgentRenderes import convert_message_to_json
from ..utils.evaluate import EvaluateTemplate
from ..tools.llm import LLMNode
from ..tools.tool import ToolNode
from ..tools.loop import LoopNode
from ..tools.function import FunctionTool
from ..utils.utils import clean_string

from .utils import create_state

logger = logging.getLogger(__name__)

class ConditionalEdge(Runnable):
    name = "ConditionalEdge"
    def __init__(self, condition: str, condition_inputs: Optional[list[str]] = [], 
                 conditional_outputs: Optional[list[str]] = [], default_output: str = 'END'):
        self.condition = condition
        self.condition_inputs = condition_inputs
        self.conditional_outputs = conditional_outputs
        self.default_output = default_output
    
    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> str:
        logger.info(f"Current state in condition edge - {state}")
        input_data = {}
        for field in self.condition_inputs:
            if field == 'messages':
                input_data['messages'] = convert_message_to_json(state.get('messages', []))
            else:
                input_data[field] = state.get(field, "")    
        template = EvaluateTemplate(self.condition, input_data)
        result = template.evaluate()
        if isinstance(result, str):
            result = clean_string(result)
            if len(self.conditional_outputs) > 0:
                if result in self.conditional_outputs:
                    return result
                else:
                    return self.default_output
        if result == 'END':
            result = END
        return result

class DecisionEdge(Runnable):
    name = "DecisionEdge"
    prompt: str = """Based on chat history and additional_info make a decision what step need to be next.
Steps available: {steps}
Explanation: {description}

{additional_info}

### Expected output:
Answer only with step name, no need to add descrip in case none of the steps are applibcable answer with 'END'
"""
    def __init__(self, client, steps: str, description: str = "", decisional_inputs: Optional[list[str]] = [],
                 default_output: str = 'END'):
        self.client = client
        self.steps = ",".join([clean_string(step) for step in steps])
        self.description = description
        self.decisional_inputs = decisional_inputs
        self.default_output = default_output if default_output != 'END' else END
        
    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> str:
        additional_info = ""
        decision_input = []
        for field in self.decisional_inputs:
            if field == 'messages':
                decision_input = state.get('messages', [])[:]
            else:
                if len(additional_info) == 0:
                    additional_info = """### Additoinal info: """
                additional_info += "{field}: {value}\n".format(field=field, value=state.get(field, ""))
        decision_input.append(HumanMessage(self.prompt.format(steps=self.steps, description=self.description, additional_info=additional_info)))
        completion = self.client.invoke(decision_input)
        result = clean_string(completion.content.strip())
        logger.info(f"Plan to transition to: {result}")
        if result not in self.steps or result == 'END':
            result = self.default_output
        return result

class TransitionalEdge(Runnable):
    name = "TransitionalEdge"
    def __init__(self, next_step: str):
        self.next_step = next_step
    
    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: RunnableConfig, *args, **kwargs):
        logger.info(f'Transitioning to: {self.next_step}')
        return self.next_step if self.next_step != 'END' else END
     
def prepare_output_schema(lg_builder, memory, store, debug=False, interrupt_before=[], interrupt_after=[]):
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
        
        compiled = LangGraphAgentRunnable(
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
        return compiled

def create_graph(
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
        state_class = create_state(schema.get('state', {}))
        lg_builder = StateGraph(state_class)
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
                                lg_builder.add_node(node_id, FunctionTool(
                                    tool=tool, name=node['id'], return_type='dict',
                                    output_variables=node.get('output', []),
                                    input_mapping=node.get('input_mapping', {'messages': {'type': 'variable', 'value': 'messages'}}),
                                    input_variables=node.get('input', ['messages'])))
                            elif node_type == 'tool':
                                lg_builder.add_node(node_id, ToolNode(
                                    client=client, tool=tool,
                                    name=node['id'], return_type='dict',
                                    output_variables=node.get('output', []),
                                    input_variables=node.get('input', ['messages']),
                                    structured_output=node.get('structured_output', False)))
                            elif node_type == 'loop':
                                lg_builder.add_node(node_id, LoopNode(
                                    client=client, tool=tool, task=node.get('task', ""),
                                    name=node['id'], return_type='dict',
                                    output_variables=node.get('output', []),
                                    input_variables=node.get('input', ['messages'])))
                            break
                elif node_type == 'llm':
                    lg_builder.add_node(node_id, LLMNode(
                        client=client, prompt=node.get('prompt', {}),
                        name=node['id'], return_type='dict',
                        response_key=node.get('response_key', 'messages'),
                        output_variables=node.get('output', []),
                        input_variables=node.get('input', ['messages']),
                        structured_output=node.get('structured_output', False)))
                if node.get('transition'):
                    next_step=clean_string(node['transition'])
                    logger.info(f'Adding transition: {next_step}')
                    lg_builder.add_conditional_edges(node_id, TransitionalEdge(next_step))
                elif node.get('decision'):
                    logger.info(f'Adding decision: {node["decision"]["nodes"]}')
                    lg_builder.add_conditional_edges(node_id, DecisionEdge(
                        client, node['decision']['nodes'], 
                        node['decision'].get('description', ""),
                        decisional_inputs=node['decision'].get('decisional_inputs', ['messages']),
                        default_output=node['decision'].get('default_output', 'END')))
                elif node.get('condition'):
                    logger.info(f'Adding condition: {node["condition"]}')
                    condition_input = node['condition'].get('condition_input', ['messages'])
                    condition_definition = node['condition'].get('condition_definition', '')
                    lg_builder.add_conditional_edges(node_id, ConditionalEdge(
                        condition=condition_definition, condition_inputs=condition_input,
                        conditional_outputs=node['condition'].get('conditional_outputs', []),
                        default_output=node['condition'].get('default_output', 'END')))

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
        compiled = prepare_output_schema(lg_builder, memory, store, debug, 
                                         interrupt_before=interrupt_before, 
                                         interrupt_after=interrupt_after)
        return compiled.validate()


class LangGraphAgentRunnable(CompiledStateGraph):
    builder: CompiledStateGraph
    
    def invoke(self, input: Union[dict[str, Any], Any], 
               config: Optional[RunnableConfig] = None, 
               *args, **kwargs):
        
        if not config.get("configurable", {}).get("thread_id"):
            config["configurable"] = {"thread_id": str(uuid4())}
        thread_id = config.get("configurable", {}).get("thread_id")
        if input.get('chat_history') and not input.get('messages'):
            input['messages'] = input.pop('chat_history')
        if input.get('input'):
            if input.get('messages'):
                input['messages'].append({"role": "user", "content": input.get('input')})
            else:
                input['messages'] = [{"role": "user", "content": input.get('input')}]
        
        logging.info(f"Input: {thread_id} - {input}")
        
        if self.checkpointer and self.checkpointer.get_tuple(config):
            self.update_state(config, input)
            input = None
        result = super().invoke(input, config=config, *args, **kwargs)
        try:
            output = result['messages'][-1].content
        except:
            output =list(result.values())[-1]
        thread_id = None
        if self.get_state(config).next:
            thread_id = config['configurable']['thread_id']
        return {
            "output": output,
            "thread_id": thread_id
        }