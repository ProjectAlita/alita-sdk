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
        self._event_queue = []  # Queue for events when context is unavailable
        #
        super().__init__()

    def _has_streamlit_context(self) -> bool:
        """Check if Streamlit context is available in the current thread."""
        try:
            # Try to import streamlit runtime context checker
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            ctx = get_script_run_ctx()
            return ctx is not None
        except (ImportError, Exception) as e:
            if self.debug:
                log.debug(f"Streamlit context check failed: {e}")
            return False

    def _safe_streamlit_call(self, func, *args, **kwargs):
        """Safely execute a Streamlit UI operation, handling missing context gracefully."""
        if not self._has_streamlit_context():
            func_name = getattr(func, '__name__', str(func))
            if self.debug:
                log.warning(f"Streamlit context not available for {func_name}, queueing event")
            # Store the event for potential replay when context is available
            self._event_queue.append({
                'func': func_name,
                'args': args,
                'kwargs': kwargs,
                'timestamp': datetime.now(tz=timezone.utc)
            })
            return None

        try:
            return func(*args, **kwargs)
        except Exception as e:
            func_name = getattr(func, '__name__', str(func))
            # Handle any Streamlit-specific exceptions gracefully
            log.warning(f"Streamlit operation {func_name} failed: {e}")
            return None

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

        status_widget = self._safe_streamlit_call(
            self.st.status,
            f"Running {payload.get('tool_name')}...",
            expanded=True
        )
        if status_widget:
            self.callback_state[str(run_id)] = status_widget
            self._safe_streamlit_call(status_widget.write, f"Tool inputs: {payload}")

    def on_tool_start(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_tool_start(%s, %s)", args, kwargs)

        tool_name = args[0].get("name")
        tool_run_id = str(run_id)
        
        # Extract metadata from tool if available (from BaseAction.metadata)
        # Try multiple sources for metadata with toolkit_name
        tool_meta = args[0].copy()
        
        # Source 1: kwargs['serialized']['metadata'] - LangChain's full tool serialization
        if 'serialized' in kwargs and 'metadata' in kwargs['serialized']:
            tool_meta['metadata'] = kwargs['serialized']['metadata']
            log.info(f"[METADATA] Extracted from serialized: {kwargs['serialized']['metadata']}")
        # Source 2: Check if metadata is directly in args[0] (some LangChain versions)
        elif 'metadata' in args[0]:
            tool_meta['metadata'] = args[0]['metadata']
            log.info(f"[METADATA] Extracted from args[0]: {args[0]['metadata']}")
        else:
            log.info(f"[METADATA] No metadata found. args[0] keys: {list(args[0].keys())}, kwargs keys: {list(kwargs.keys())}")
            # Fallback: Try to extract toolkit_name from description
            description = args[0].get('description', '')
            if description:
                import re
                # Try pattern 1: [Toolkit: name]
                match = re.search(r'\[Toolkit:\s*([^\]]+)\]', description)
                if not match:
                    # Try pattern 2: Toolkit: name at start or end
                    match = re.search(r'(?:^|\n)Toolkit:\s*([^\n]+)', description)
                if match:
                    toolkit_name = match.group(1).strip()
                    tool_meta['metadata'] = {'toolkit_name': toolkit_name}
                    log.info(f"[METADATA] Extracted toolkit_name from description: {toolkit_name}")
        
        payload = {
            "tool_name": tool_name,
            "tool_run_id": tool_run_id,
            "tool_meta": tool_meta,
            "tool_inputs": kwargs.get('inputs')
        }
        payload = json.loads(json.dumps(payload, ensure_ascii=False, default=lambda o: str(o)))

        status_widget = self._safe_streamlit_call(
            self.st.status,
            f"Running {tool_name}...",
            expanded=True
        )
        if status_widget:
            self.callback_state[tool_run_id] = status_widget
            self._safe_streamlit_call(status_widget.write, f"Tool inputs: {kwargs.get('inputs')}")

    def on_tool_end(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_tool_end(%s, %s)", args, kwargs)
        tool_run_id = str(run_id)
        tool_output = args[0]
        if self.callback_state.get(tool_run_id):
            status_widget = self.callback_state[tool_run_id]
            self._safe_streamlit_call(status_widget.write, f"Tool output: {tool_output}")
            self._safe_streamlit_call(
                status_widget.update,
                label=f"Completed {kwargs.get('name')}",
                state="complete",
                expanded=False
            )
            self.callback_state.pop(tool_run_id, None)

    def on_tool_error(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.info("on_tool_error(%s, %s)", args, kwargs)
        tool_run_id = str(run_id)
        tool_exception = args[0]
        if self.callback_state.get(tool_run_id):
            status_widget = self.callback_state[tool_run_id]
            self._safe_streamlit_call(
                status_widget.write,
                f"{traceback.format_exception(tool_exception)}"
            )
            self._safe_streamlit_call(
                status_widget.update,
                label=f"Error {kwargs.get('name')}",
                state="error",
                expanded=False
            )
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

        status_widget = self._safe_streamlit_call(
            self.st.status,
            f"Running LLM ...",
            expanded=True
        )
        if status_widget:
            self.callback_state[llm_run_id] = status_widget
            self._safe_streamlit_call(status_widget.write, f"LLM inputs: {messages}")

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

        llm_run_id = str(run_id)
        if self.callback_state.get(llm_run_id):
            status_widget = self.callback_state[llm_run_id]
            self._safe_streamlit_call(status_widget.write, content)

    def on_llm_error(self, *args, run_id: UUID, **kwargs):
        """ Callback """
        if self.debug:
            log.error("on_llm_error(%s, %s)", args, kwargs)
        llm_run_id = str(run_id)
        if self.callback_state.get(llm_run_id):
            status_widget = self.callback_state[llm_run_id]
            self._safe_streamlit_call(status_widget.write, f"on_llm_error({args}, {kwargs})")
            self._safe_streamlit_call(
                status_widget.update,
                label=f"Error {kwargs.get('name')}",
                state="error",
                expanded=False
            )
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
        # Check if callback_state exists and is not None before accessing
        if self.callback_state is not None and self.callback_state.get(llm_run_id):
            status_widget = self.callback_state[llm_run_id]
            self._safe_streamlit_call(
                status_widget.update,
                label=f"Completed LLM call",
                state="complete",
                expanded=False
            )
            self.callback_state.pop(llm_run_id, None)
