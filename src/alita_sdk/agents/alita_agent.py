from typing import Sequence, Union, Any, Optional
from traceback import format_exc

from langchain_core.prompts import BasePromptTemplate
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain.agents.openai_assistant.base import OutputType
from langchain_core.runnables import RunnableSerializable, ensure_config
from .mixedAgentParser import MixedAgentOutputParser
from langchain_core.tools.render import ToolsRenderer
from langchain_core.load import dumpd
from .mixedAgentRenderes import render_react_text_description_and_args
from .mixedAgentRenderes import conversation_to_messages, format_to_langmessages
from langchain_core.callbacks import CallbackManager
from langchain_core.runnables import RunnableConfig, RunnableSerializable, ensure_config
from uuid import uuid4
from langchain_core.outputs import LLMResult, ChatGenerationChunk
from langchain_core.outputs.run_info import RunInfo
from langchain_core.outputs.generation import Generation
from ..clients.constants import ALITA_OUTPUT_FORMAT

class AlitaAssistantRunnable(RunnableSerializable):
    client: Optional[Any]
    assistant: Optional[Any]
    chat_history: list[BaseMessage] = []
    agent_type:str = "alita"

    @classmethod
    def create_assistant(
        cls,
        client: Any,
        prompt: BasePromptTemplate,
        tools: Sequence[Union[BaseTool, dict]],
        tools_renderer: Optional[ToolsRenderer] = render_react_text_description_and_args,
    ) -> RunnableSerializable:
        prompt = prompt.partial(
            tools=tools_renderer(list(tools)),
            tool_names=", ".join([t.name for t in tools]),
        )
        return cls(client=client, assistant=client, agent_type='alita', chat_history=prompt.format_messages())
    
    def invoke(self, input: dict, config: RunnableConfig | None = None) -> OutputType:
        run_id = uuid4()
        config = ensure_config(config)
        callback_manager = CallbackManager.configure(
            inheritable_callbacks=config.get("callbacks"),
            inheritable_tags=config.get("tags"),
            inheritable_metadata=config.get("metadata"),
        )
        run_manager = callback_manager.on_chain_start(
            dumpd(self), input, name=config.get("run_name"), run_id=run_id
        )
        messages = []
        if input.get("intermediate_steps"):
            messages = format_to_langmessages(input["intermediate_steps"])
        
        try:
            user_messages = [] 
            if self.agent_type == "alita":
                messages.append(SystemMessage(content=ALITA_OUTPUT_FORMAT))
            if input.get('input', input.get('content')):
                user_messages.append(HumanMessage(content=input.get('input', input.get('content'))))
            msgs = self.chat_history + \
                conversation_to_messages(input["chat_history"]) + \
                     user_messages + \
                        messages
            llm_manager = callback_manager.on_llm_start(dumpd(self), [msgs[-1].content], run_id=run_id)
            run = self._create_thread_and_run(msgs, config=config)
            response = self._get_response(run)
            try:
                log = response.log
            except AttributeError:
                log = response
            llm_manager[0].on_llm_new_token(
                token=str(log), chunk=ChatGenerationChunk(
                    text=str(log), message=AIMessage(content=str(log))
                ))
            llm_manager[0].on_llm_end(LLMResult(generations=[[Generation(text=str(log))]], 
                                                run=[RunInfo(run_id=run_id)]))
        except BaseException as e:
            run_manager.on_chain_error(e, metadata=format_exc())
            raise e
        else:
            run_manager.on_chain_end(response)
            return response
        
    
    def _create_thread_and_run(self, messages: list[BaseMessage], *args, **kwargs) -> Any:
        return self.client.completion_with_retry(messages)
    
    def _get_response(self, run: BaseMessage) -> Any:
        output_parser = MixedAgentOutputParser()
        return output_parser.parse(run[0].content)