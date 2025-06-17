import logging
import json
import traceback
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Any, Dict, List, Optional
from collections import defaultdict
from langchain_core.callbacks import BaseCallbackHandler  # pylint: disable=E0401
from langchain_core.outputs import ChatGenerationChunk, LLMResult
from langchain_core.messages import BaseMessage  # pylint: disable=E0401

log = logging.getLogger(__name__)

class AlitaStreamlitCallback(BaseCallbackHandler):
    """ Alita agent callback handler """

    def __init__(self, st: Any, debug: bool = False):
        log.info(f'AlitaCallback init {st=} {debug=}')
        self.debug = debug
        self.st = st
        self.callback_state = defaultdict(int)
        self.tokens_in = 0
        self.tokens_out = 0
        self.pending_llm_requests = defaultdict(int)
        self.current_model_name = 'gpt-4'
        #
        super().__init__()

    #
    # Chain
    #

    def on_chain_start(self, *args, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_chain_start(%s, %s)", args, kwargs)

    def on_chain_end(self, *args, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_chain_end(%s, %s)", args, kwargs)

    def on_chain_error(self, *args, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_chain_error(%s, %s)", args, kwargs)
        #
        # exception = args[0]
        # FIXME: should we emit an error here too?

    #
    # Tool
    #

    def on_custom_event(
        self,
        name: str,
        data: Any,
        *,
        run_id: UUID,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Callback containing a group of custom events"""

        payload = {
            "name": name,
            "run_id": str(run_id),
            "tool_run_id": str(run_id),  # compatibility
            "metadata": metadata,
            "datetime": str(datetime.now(tz=timezone.utc)),
            **data,
        }
        payload = json.loads(
            json.dumps(payload, ensure_ascii=False, default=lambda o: str(o))
        )

        self.callback_state[str(run_id)] = self.st.status(
            f"Running {payload.get('tool_name')}...", expanded=True
        )
        self.callback_state[str(run_id)].write(f"Tool inputs: {payload}")

    def on_tool_start(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_tool_start(%s, %s)", args, kwargs)

        tool_name = args[0].get("name")
        tool_run_id = str(run_id)
        payload = {
            "tool_name": tool_name,
            "tool_run_id": tool_run_id,
            "tool_meta": args[0],
            "tool_inputs": kwargs.get('inputs')
        }
        payload = json.loads(json.dumps(payload, ensure_ascii=False, default=lambda o: str(o)))
        self.callback_state[tool_run_id] = self.st.status(f"Running {tool_name}...", expanded=True)
        self.callback_state[tool_run_id].write(f"Tool inputs: {kwargs.get('inputs')}")

    def on_tool_end(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_tool_end(%s, %s)", args, kwargs)
        tool_run_id = str(run_id)
        tool_output = args[0]
        if self.callback_state[tool_run_id]:
            self.callback_state[tool_run_id].write(f"Tool output: {tool_output}")
            self.callback_state[tool_run_id].update(label=f"Completed {kwargs.get('name')}", state="complete", expanded=False)
            self.callback_state.pop(tool_run_id, None)
            del self.callback_state[run_id]

    def on_tool_error(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_tool_error(%s, %s)", args, kwargs)
        tool_run_id = str(run_id)
        tool_exception = args[0]
        self.callback_state[tool_run_id].write(f"{traceback.format_exception(tool_exception)}")
        self.callback_state[tool_run_id].update(label=f"Error {kwargs.get('name')}", state="error", expanded=False)
        self.callback_state.pop(tool_run_id, None)

    #
    # Agent
    #

    def on_agent_action(self, *args, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_agent_action(%s, %s)", args, kwargs)

    def on_agent_finish(self, *args, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_agent_finish(%s, %s)", args, kwargs)

    #
    # LLM
    #

    def _handle_llm_start(self,
                          serialized: Dict[str, Any],
                          messages: List[List[BaseMessage]] | List[List[str]],
                          *,
                          run_id: UUID,
                          parent_run_id: Optional[UUID] = None,
                          tags: Optional[List[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None,
                          **kwargs: Any, ):
        if self.debug:
            log.info(f'on_llm_start {run_id=}')
            log.info(f'on_llm_start {serialized=}')
            log.info(f'on_llm_start {messages=}')
            log.info(f'on_llm_start {metadata=}')

        self.current_model_name = metadata.get('ls_model_name', self.current_model_name)
        llm_run_id = str(run_id)

        self.callback_state[llm_run_id] = self.st.status(f"Running LLM ...", expanded=True)
        self.callback_state[llm_run_id].write(f"LLM inputs: {messages}")

    def on_llm_start(self, *args, **kwargs):
        """ Callback """
        self._handle_llm_start(*args, **kwargs)

    def on_chat_model_start(self, *args, **kwargs):
        """ Callback """
        self._handle_llm_start(*args, **kwargs)

    def on_llm_new_token(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_llm_new_token(%s, %s)", args, kwargs)
        #
        # TODO: streaming support
        # log.info(f"on_llm_new_token\n{args=}\n{kwargs=}")
        chunk: ChatGenerationChunk = kwargs.get('chunk')
        content = None
        if chunk:
            content = chunk.text
        self.callback_state[str(run_id)].write(content)

    def on_llm_error(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.error("on_llm_error(%s, %s)", args, kwargs)
        llm_run_id = str(run_id)
        self.callback_state[llm_run_id].write(f"on_llm_error({args}, {kwargs})")
        self.callback_state[llm_run_id].update(label=f"Error {kwargs.get('name')}", state="error", expanded=False)
        self.callback_state.pop(llm_run_id, None)
        #
        # exception = args[0]
        # FIXME: should we emit an error here too?

    #
    # Misc
    #

    def on_text(self, *args, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_text(%s, %s)", args, kwargs)

    def on_llm_end(self, response: LLMResult, run_id: UUID, **kwargs) -> None:
        if self.debug:
            log.debug("on_llm_end(%s, %s)", response, kwargs)
        llm_run_id = str(run_id)
        self.callback_state[llm_run_id].update(label=f"Completed LLM call", state="complete", expanded=False)
        self.callback_state.pop(llm_run_id, None)
