import yaml
from uuid import uuid4
from typing import Sequence, Union, Any, Optional
from json import dumps
from traceback import format_exc
from langchain_core.load import dumpd
from langchain_core.agents import AgentAction, AgentFinish
from langgraph.graph import StateGraph, MessagesState
from langchain_core.prompts import BasePromptTemplate
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig, RunnableSerializable, ensure_config
from langchain_core.outputs import LLMResult, ChatGenerationChunk
from langchain_core.outputs.run_info import RunInfo
from langchain_core.outputs.generation import Generation
from langchain_core.callbacks import CallbackManager
from langchain.agents.openai_assistant.base import OutputType
from langchain_core.runnables import Runnable
from .mixedAgentRenderes import convert_message_to_json, conversation_to_messages, format_to_langmessages
from langchain_core.utils.function_calling import convert_to_openai_tool
from .alita_agent import AlitaAssistantRunnable
from ..utils.evaluate import EvaluateTemplate
from ..agents.utils import _extract_json
from ..utils.utils import clean_string

class ConditionalEdge(Runnable):
    def __init__(self, condition: str):
        self.condition = condition
    
    def invoke(self, messages, config: RunnableConfig, *args, **kwargs):
        print(config['callbacks'].handlers)
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

Expected output is JSON that to be used as a KWARGS for the tool call like {{"key": "value"}} 
Tool won't have access to convesation so all keys and values need to be actual and independant. 
Anwer must be JSON only extractable by JSON.LOADS.
"""
    def _run(self, messages, *args, **kwargs):
        print(args)
        params = convert_to_openai_tool(self.tool).get(
            'function',{'parameters': {}}).get(
                'parameters', {'properties': {}}).get('properties', {})
        # this is becasue messages is shared between all tools and we need to make sure that we are not modifying it
        input = messages + [
            HumanMessage(self.prompt.format(tool_name=self.tool.name, tool_description=self.tool.description, schema=dumps(params)))
        ]
        completion = self.client.completion_with_retry(input)
        result = _extract_json(completion[0].content.strip())
        return {"messages": [AIMessage(str(self.tool.run(result)))]}


class TransitionalEdge(Runnable):
    def __init__(self, next_step: str):
        self.next_step = next_step
    
    def invoke(self, messages, config: RunnableConfig, *args, **kwargs):
        print('Transitioning to:', self.next_step)
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
        return lg_builder.compile()

class LGAssistantRunnable(AlitaAssistantRunnable):
    client: Optional[Any]
    assistant: Optional[Any]
    chat_history: list[BaseMessage] = []
    agent_type:str = "langgraph"

    @classmethod
    def create_assistant(
        cls,
        client: Any,
        prompt: BasePromptTemplate,
        tools: Sequence[Union[BaseTool, dict]],
        chat_history: list[BaseMessage],
        *args, **kwargs
    ) -> RunnableSerializable:
        print(tools)
        assistant = create_message_graph(client, prompt, tools)
        return cls(client=client, assistant=assistant, agent_type='langgraph', chat_history=chat_history)
    
    def _create_thread_and_run(self, messages: list[BaseMessage], config, *args, **kwargs) -> Any:
        messages = convert_message_to_json(messages)
        return self.assistant.invoke({"messages": messages}, config=config)
    
    def _get_response(self, run: Union[str, dict]) -> Any:
        response = run.get("messages", [])
        if len(response) > 0:
            return AgentFinish({"output": response[-1].content}, log=response[-1].content)
        return AgentFinish({"output": "No reponse from chain"}, log=dumps(run))