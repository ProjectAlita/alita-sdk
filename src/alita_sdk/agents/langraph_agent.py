from typing import Sequence, Union, Any, Optional
from json import dumps
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.prompts import BasePromptTemplate
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableSerializable
from .mixedAgentRenderes import convert_message_to_json
from .alita_agent import AlitaAssistantRunnable
from ..clients.workflow import create_message_graph


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
        assistant = create_message_graph(prompt, tools)
        return cls(client=client, assistant=assistant, agent_type='langgraph', chat_history=chat_history)
    
    def _create_thread_and_run(self, messages: list[BaseMessage]) -> Any:
        print("create_thread")
        print(messages)
        messages = convert_message_to_json(messages)
        return self.assistant.invoke({"messages": messages})
    
    def _get_response(self, run: Union[str, dict]) -> Any:
        print(run)
        response = run.get("messages", [])
        if len(response) > 0:
            return AgentFinish({"output": response[-1].content}, 
                               log=dumps(convert_message_to_json(response)))
        return AgentFinish({"output": "No reponse from chain"}, log=dumps(run))