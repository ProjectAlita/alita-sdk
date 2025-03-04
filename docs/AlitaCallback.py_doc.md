# AlitaCallback.py

**Path:** `src/alita_sdk/utils/AlitaCallback.py`

## Data Flow

The data flow within `AlitaCallback.py` revolves around handling various callback events for an Alita agent. The data originates from different events such as chain start, tool start, LLM start, etc., and is processed through corresponding callback methods. Each method logs the event details if debugging is enabled and updates the callback state accordingly. The data is transformed into JSON payloads and written to the Streamlit status component for display. The final destination of the data is the Streamlit UI, where the status and outputs of different events are shown to the user.

Example:
```python
    def on_tool_start(self, *args, run_id: UUID, **kwargs):
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
```
In this example, the `on_tool_start` method processes the tool start event, logs the event details, creates a JSON payload, and updates the Streamlit status component.

## Functions Descriptions

1. **`__init__(self, st: Any, debug: bool = False)`**: Initializes the callback handler with Streamlit and debug mode. Sets up initial states and logging.

2. **`on_chain_start(self, *args, **kwargs)`**: Handles the chain start event. Logs the event details if debugging is enabled.

3. **`on_chain_end(self, *args, **kwargs)`**: Handles the chain end event. Logs the event details if debugging is enabled.

4. **`on_chain_error(self, *args, **kwargs)`**: Handles the chain error event. Logs the event details if debugging is enabled.

5. **`on_tool_start(self, *args, run_id: UUID, **kwargs)`**: Handles the tool start event. Logs the event details, creates a JSON payload, and updates the Streamlit status component.

6. **`on_tool_end(self, *args, run_id: UUID, **kwargs)`**: Handles the tool end event. Logs the event details, updates the Streamlit status component, and removes the callback state.

7. **`on_tool_error(self, *args, run_id: UUID, **kwargs)`**: Handles the tool error event. Logs the event details, updates the Streamlit status component, and removes the callback state.

8. **`on_agent_action(self, *args, **kwargs)`**: Handles the agent action event. Logs the event details if debugging is enabled.

9. **`on_agent_finish(self, *args, **kwargs)`**: Handles the agent finish event. Logs the event details if debugging is enabled.

10. **`_handle_llm_start(self, serialized: Dict[str, Any], messages: List[List[BaseMessage]] | List[List[str]], *, run_id: UUID, parent_run_id: Optional[UUID] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any)`**: Handles the LLM start event. Logs the event details, updates the current model name, and updates the Streamlit status component.

11. **`on_llm_start(self, *args, **kwargs)`**: Calls `_handle_llm_start` to handle the LLM start event.

12. **`on_chat_model_start(self, *args, **kwargs)`**: Calls `_handle_llm_start` to handle the chat model start event.

13. **`on_llm_new_token(self, *args, run_id: UUID, **kwargs)`**: Handles the LLM new token event. Logs the event details if debugging is enabled and writes the token content to the Streamlit status component.

14. **`on_llm_error(self, *args, run_id: UUID, **kwargs)`**: Handles the LLM error event. Logs the event details, updates the Streamlit status component, and removes the callback state.

15. **`on_text(self, *args, **kwargs)`**: Handles the text event. Logs the event details if debugging is enabled.

16. **`on_llm_end(self, response: LLMResult, run_id: UUID, **kwargs)`**: Handles the LLM end event. Logs the event details if debugging is enabled, updates the Streamlit status component, and removes the callback state.

## Dependencies Used and Their Descriptions

1. **`logging`**: Used for logging debug and info messages throughout the callback methods.

2. **`json`**: Used for creating JSON payloads from event data.

3. **`traceback`**: Used for formatting exception tracebacks in error events.

4. **`uuid`**: Used for generating and handling UUIDs for run IDs.

5. **`typing`**: Used for type hinting in method signatures.

6. **`collections.defaultdict`**: Used for maintaining callback state and pending LLM requests with default integer values.

7. **`langchain_core.callbacks.BaseCallbackHandler`**: Base class for creating callback handlers.

8. **`langchain_core.outputs.ChatGenerationChunk`**: Used for handling chat generation chunks in LLM new token events.

9. **`langchain_core.messages.BaseMessage`**: Used for handling base messages in LLM start events.

## Functional Flow

1. The `AlitaStreamlitCallback` class is initialized with Streamlit and debug mode.

2. Various callback methods handle different events such as chain start, tool start, LLM start, etc.

3. Each callback method logs the event details if debugging is enabled.

4. The callback methods update the Streamlit status component with event details and outputs.

5. The callback state is maintained and updated throughout the event handling process.

6. Error events log the exception details and update the Streamlit status component with error information.

## Endpoints Used/Created

No explicit endpoints are defined or called within `AlitaCallback.py`. The file primarily handles callback events and updates the Streamlit status component with event details and outputs.