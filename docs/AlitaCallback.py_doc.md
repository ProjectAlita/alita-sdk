# AlitaCallback.py

**Path:** `src/alita_sdk/utils/AlitaCallback.py`

## Data Flow

The data flow within `AlitaCallback.py` revolves around handling various callback events for an Alita agent. The data originates from different events such as chain start, tool start, LLM start, etc., and is processed through corresponding callback methods. These methods log the events, update the callback state, and manage the status of ongoing operations. The data is primarily in the form of dictionaries and lists, which are transformed into JSON payloads for logging and status updates. The final destination of the data is the Streamlit status updates and logs.

Example:
```python
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
This snippet shows the creation of a payload for a tool start event and updating the callback state with the tool's status.

## Functions Descriptions

1. `__init__(self, st: Any, debug: bool = False)`: Initializes the callback handler with Streamlit instance and debug flag. Sets up initial states and logging.
2. `on_chain_start(self, *args, **kwargs)`: Logs the start of a chain if debug is enabled.
3. `on_chain_end(self, *args, **kwargs)`: Logs the end of a chain if debug is enabled.
4. `on_chain_error(self, *args, **kwargs)`: Logs a chain error if debug is enabled.
5. `on_tool_start(self, *args, run_id: UUID, **kwargs)`: Logs the start of a tool, creates a payload, and updates the callback state with the tool's status.
6. `on_tool_end(self, *args, run_id: UUID, **kwargs)`: Logs the end of a tool, updates the callback state with the tool's output, and removes the tool's status.
7. `on_tool_error(self, *args, run_id: UUID, **kwargs)`: Logs a tool error, updates the callback state with the error, and removes the tool's status.
8. `on_agent_action(self, *args, **kwargs)`: Logs an agent action if debug is enabled.
9. `on_agent_finish(self, *args, **kwargs)`: Logs the completion of an agent if debug is enabled.
10. `_handle_llm_start(self, serialized: Dict[str, Any], messages: List[List[BaseMessage]] | List[List[str]], *, run_id: UUID, parent_run_id: Optional[UUID] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any)`: Handles the start of an LLM, logs the event, and updates the callback state with the LLM's status.
11. `on_llm_start(self, *args, **kwargs)`: Calls `_handle_llm_start` to handle the start of an LLM.
12. `on_chat_model_start(self, *args, **kwargs)`: Calls `_handle_llm_start` to handle the start of a chat model.
13. `on_llm_new_token(self, *args, run_id: UUID, **kwargs)`: Logs a new LLM token and updates the callback state with the token's content.
14. `on_llm_error(self, *args, run_id: UUID, **kwargs)`: Logs an LLM error, updates the callback state with the error, and removes the LLM's status.
15. `on_text(self, *args, **kwargs)`: Logs a text event if debug is enabled.
16. `on_llm_end(self, response: LLMResult, run_id: UUID, **kwargs)`: Logs the end of an LLM call, updates the callback state with the completion status, and removes the LLM's status.

## Dependencies Used and Their Descriptions

1. `logging`: Used for logging debug and error messages.
2. `json`: Used for serializing and deserializing JSON payloads.
3. `traceback`: Used for formatting exception tracebacks.
4. `uuid`: Used for generating and handling UUIDs for run IDs.
5. `typing`: Used for type hinting.
6. `collections.defaultdict`: Used for initializing default dictionary for callback states.
7. `langchain_core.callbacks.BaseCallbackHandler`: Base class for callback handlers.
8. `langchain_core.outputs.ChatGenerationChunk`: Used for handling chat generation chunks.
9. `langchain_core.messages.BaseMessage`: Used for handling base messages.

## Functional Flow

1. The `AlitaStreamlitCallback` class is initialized with a Streamlit instance and a debug flag.
2. Various callback methods are defined to handle different events such as chain start, tool start, LLM start, etc.
3. Each callback method logs the event if debug is enabled and updates the callback state with the event's status.
4. The callback state is managed using a default dictionary, where each event's status is stored and updated.
5. The callback methods handle errors by logging the error and updating the callback state with the error status.
6. The callback methods also handle the completion of events by updating the callback state with the completion status and removing the event's status from the callback state.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file.