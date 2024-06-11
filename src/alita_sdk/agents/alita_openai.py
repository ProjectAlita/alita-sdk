import json 
from json import JSONDecodeError

from typing import Sequence, Union, Any, Dict, Optional
from traceback import format_exc

from langchain_core.messages import BaseMessage
from langchain_core.callbacks import CallbackManager
from langchain_core.load import dumpd
from langchain.agents.openai_assistant.base import OutputType
from langchain_core.runnables import RunnableConfig, RunnableSerializable, ensure_config

from .mixedAgentRenderes import conversation_to_messages, format_to_langmessages
from langchain_core.agents import AgentAction, AgentFinish
from .alita_agent import AlitaAssistantRunnable

class AlitaDialOpenAIAssistantRunnable(AlitaAssistantRunnable):
    agent_type:str = "openai"
    
    def _get_response(self, run: BaseMessage) -> Any:
        if run.additional_kwargs.get("function_call"):
            action = run.additional_kwargs["function_call"].get("name")
            tool_input = json.loads(run.additional_kwargs["function_call"].get("arguments"))
            return AgentAction(action, tool_input, run.content)
        else:
            return AgentFinish({"output": run.content}, run.content)
        
    
    def _create_thread_and_run(self, messages: list[BaseMessage]) -> Any:
        return self.assistant.predict(messages)
