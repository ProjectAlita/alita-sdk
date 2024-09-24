from typing import Sequence, Union, Any, Optional
from json import dumps, loads
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.prompts import BasePromptTemplate
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain.agents.output_parsers.openai_tools import ToolAgentAction
from langchain_core.runnables import RunnableSerializable
from langchain_core.tools.render import ToolsRenderer
from .mixedAgentRenderes import render_react_text_description_and_args
from .mixedAgentRenderes import convert_message_to_json
from .alita_agent import AlitaAssistantRunnable
        
from autogen import ConversableAgent

class AutoGenAssistantRunnable(AlitaAssistantRunnable):
    client: Optional[Any]
    assistant: Optional[Any]
    chat_history: list[BaseMessage] = []
    agent_type:str = "autogen"

    @classmethod
    def create_assistant(
        cls,
        client: Any,
        prompt: BasePromptTemplate,
        tools: Sequence[Union[BaseTool, dict]],
        tools_renderer: Optional[ToolsRenderer] = render_react_text_description_and_args,
    ) -> RunnableSerializable:
        functional_calls = {}
        for tool in tools:
            functional_calls[tool.name] = tool

        client['tools'] = [convert_to_openai_tool(tool) for tool in tools]
        assistant = ConversableAgent(
            'chatbot',
            llm_config=client,
            function_map=functional_calls,
            system_message=prompt.messages[0].content,
            chat_messages=convert_message_to_json(prompt.messages[1:])
        )
        return cls(client=client, assistant=assistant, agent_type='autogen', chat_history=[])
    
    def _create_thread_and_run(self, messages: list[BaseMessage], *args, **kwargs) -> Any:
        messages = convert_message_to_json(messages)
        return self.assistant.generate_reply(messages=messages)
    
    def _get_response(self, run: Union[str, dict]) -> Any:
        if isinstance(run, dict):
            tool_calls = run.get('tool_calls', [])
            if not tool_calls:
                return AgentFinish({"output": run['content']}, log=run)
            actions = []
            for tool_call in tool_calls:
                actions.append(AgentAction(
                    tool=tool_call['function']['name'], 
                    tool_input=loads(tool_call['function'].get('arguments', '{}')), 
                    log=dumps(tool_call),
                    tool_call_id=tool_call['id']))
            return actions
            
        else:
            return AgentFinish({"output": run}, log=run)