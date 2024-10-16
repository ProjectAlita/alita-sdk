import yaml
from uuid import uuid4
from typing import Union, Any, Optional
from json import dumps
from langgraph.graph.graph import END, START
from langgraph.graph import StateGraph, MessagesState
from langgraph.store.base import BaseStore
from langgraph.channels.ephemeral_value import EphemeralValue
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables import Runnable
from .mixedAgentRenderes import convert_message_to_json
from langchain_core.utils.function_calling import convert_to_openai_tool
from ..utils.evaluate import EvaluateTemplate
from ..agents.utils import _extract_json
from ..utils.utils import clean_string
from pydantic.error_wrappers import ValidationError
from langgraph.managed.base import is_managed_value
from langgraph.errors import NodeInterrupt


class ConditionalEdge(Runnable):
    def __init__(self, condition: str):
        self.condition = condition
    
    def invoke(self, messages, config: RunnableConfig, *args, **kwargs):
        messages = messages['messages']
        messages = convert_message_to_json(messages)
        last_message = messages[-1]['content']
        
        # llm_manager, checkpoint_id = get_llm_manager(dumpd(self), config, last_message)
        template = EvaluateTemplate(
            self.condition, 
            chat_history=dumps(messages), 
            last_message=last_message)
        result = template.evaluate()
        if isinstance(result, str):
            result = clean_string(result)
        # wrap_message(llm_manager, result, checkpoint_id)
        
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
        messages = messages['messages']
        messages.append(HumanMessage(self.prompt.format(steps=self.steps, description=self.description)))
        completion = self.client.completion_with_retry(messages)
        result = completion[0].content.strip()
        return result 
        

class ToolNode(BaseTool):
    name: str = 'ToolNode'
    description: str = 'This is tool node for tools'
    client: Any = None
    tool: BaseTool = None
    prompt: str = """Based on last message in chat history formulate arguments for the tool.
Tool name: {tool_name}
Tool description: {tool_description}
Tool arguments schema: {schema}

What user want to achieve: {last_message}

Expected output is JSON that to be used as a KWARGS for the tool call like {{"key": "value"}} 
Tool won't have access to convesation so all keys and values need to be actual and independant. 
Anwer must be JSON only extractable by JSON.LOADS.
"""
    def _run(self, messages, *args, **kwargs):
        params = convert_to_openai_tool(self.tool).get(
            'function',{'parameters': {}}).get(
                'parameters', {'properties': {}}).get('properties', {})
        # this is becasue messages is shared between all tools and we need to make sure that we are not modifying it
        prompt = self.prompt.format(
                tool_name=self.tool.name, 
                tool_description=self.tool.description, 
                schema=dumps(params),
                last_message=messages[-1].content)
        input = messages[:-1] + [HumanMessage(prompt)]
        completion = self.client.completion_with_retry(input)
        result = _extract_json(completion[0].content.strip())
        try:
            return {"messages": [AIMessage(str(self.tool.run(result)))]}
        except ValidationError:
            raise NodeInterrupt(f"Tool input to the {self.tool.name} with value {result} raised ValidationError. \n\nTool schema is {dumps(params)} \n\nand the input to LLM was {prompt}")


class LLMNode(BaseTool):
    name: str = 'LLMNode'
    prompt: str
    description: str = 'This is tool node for LLM'
    client: Any = None
    
    def __init__(self, client, prompt: str):
        self.client = client
        self.prompt = prompt
        
    def _run(self, messages, *args, **kwargs):
        input = messages + [HumanMessage(self.prompt)]
        
        completion = self.client.completion_with_retry(input)
        return {"messages": [AIMessage(completion[0].content.strip())]}

class TransitionalEdge(Runnable):
    def __init__(self, next_step: str):
        self.next_step = next_step
    
    def invoke(self, messages, config: RunnableConfig, *args, **kwargs):
        print('Transitioning to:', self.next_step)
        return self.next_step

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

        for node in schema['nodes']:
            node_type = node.get('type', 'function')
            node_id = clean_string(node['id'])
            if node_type in ['function', 'tool']:
                for tool in tools:
                    if tool.name == node_id:
                        if node_type == 'function':
                            lg_builder.add_node(node_id, tool)
                        elif node_type == 'tool':
                            lg_builder.add_node(node_id, ToolNode(client=client, tool=tool, name=node['id']))
                        elif node_type == 'llm':
                            lg_builder.add_node(node_id, LLMNode(client=client, prompt=node.get('prompt', ""), name=node['id']))
            if node.get('transition'):
                next_step=clean_string(node['transition'])
                if node.get('transition') != 'END':
                    print('Adding transition:', next_step)
                    lg_builder.add_conditional_edges(node_id, TransitionalEdge(next_step))
            elif node.get('decision'):
                lg_builder.add_conditional_edges(node_id, DecisionEdge(
                    client, node['decision']['nodes'], 
                    node['decision'].get('description', "")))
            elif node.get('condition'):
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