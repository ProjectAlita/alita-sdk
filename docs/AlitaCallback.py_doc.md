# AlitaCallback.py

**Path:** `src/alita_sdk/utils/AlitaCallback.py`

## Data Flow

The data flow within `AlitaCallback.py` revolves around the handling of various callback events in the Alita agent. The data originates from different events such as chain start, tool start, LLM start, etc., and is processed through corresponding callback methods. These methods log the events, update the callback state, and manage the status messages displayed in the Streamlit interface. The data is primarily in the form of dictionaries and lists, which are transformed into JSON-compatible formats for logging and status updates. The final destination of the data is the Streamlit interface, where the status messages are displayed to the user.

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
In this example, the `on_tool_start` method processes the tool start event, logs the event details, and updates the Streamlit status with the tool inputs.

## Functions Descriptions

### `__init__(self, st: Any, debug: bool = False)`
Initializes the callback handler with the Streamlit instance and debug flag. Sets up initial state variables and logs the initialization.

### `on_chain_start(self, *args, **kwargs)`
Logs the chain start event if debug is enabled.

### `on_chain_end(self, *args, **kwargs)`
Logs the chain end event if debug is enabled.

### `on_chain_error(self, *args, **kwargs)`
Logs the chain error event if debug is enabled.

### `on_tool_start(self, *args, run_id: UUID, **kwargs)`
Logs the tool start event, updates the callback state with the tool inputs, and displays the status in Streamlit.

### `on_tool_end(self, *args, run_id: UUID, **kwargs)`
Logs the tool end event, updates the callback state with the tool output, and marks the status as complete in Streamlit.

### `on_tool_error(self, *args, run_id: UUID, **kwargs)`
Logs the tool error event, updates the callback state with the error message, and marks the status as error in Streamlit.

### `on_agent_action(self, *args, **kwargs)`
Logs the agent action event if debug is enabled.

### `on_agent_finish(self, *args, **kwargs)`
Logs the agent finish event if debug is enabled.

### `_handle_llm_start(self, serialized: Dict[str, Any], messages: List[List[BaseMessage]] | List[List[str]], *, run_id: UUID, parent_run_id: Optional[UUID] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any)`
Handles the LLM start event, logs the event details, updates the callback state with the LLM inputs, and displays the status in Streamlit.

### `on_llm_start(self, *args, **kwargs)`
Calls `_handle_llm_start` to process the LLM start event.

### `on_chat_model_start(self, *args, **kwargs)`
Calls `_handle_llm_start` to process the chat model start event.

### `on_llm_new_token(self, *args, run_id: UUID, **kwargs)`
Logs the new LLM token event and updates the callback state with the token content.

### `on_llm_error(self, *args, run_id: UUID, **kwargs)`
Logs the LLM error event, updates the callback state with the error message, and marks the status as error in Streamlit.

### `on_text(self, *args, **kwargs)`
Logs the text event if debug is enabled.

### `on_llm_end(self, response: LLMResult, run_id: UUID, **kwargs)`
Logs the LLM end event, updates the callback state with the LLM response, and marks the status as complete in Streamlit.

## Dependencies Used and Their Descriptions

### `logging`
Used for logging debug and error messages throughout the callback methods.

### `json`
Used for serializing and deserializing JSON data for logging and status updates.

### `traceback`
Used for formatting exception tracebacks in error handling methods.

### `uuid`
Used for generating and handling UUIDs for run identifiers.

### `typing`
Provides type hints for function parameters and return types.

### `collections.defaultdict`
Used for initializing default dictionary for callback state management.

### `langchain_core.callbacks.BaseCallbackHandler`
Base class for implementing callback handlers in the LangChain framework.

### `langchain_core.outputs.ChatGenerationChunk`
Represents a chunk of generated text from a chat model.

### `langchain_core.messages.BaseMessage`
Represents a base message in the LangChain framework.

## Functional Flow

1. **Initialization**: The `AlitaStreamlitCallback` class is initialized with a Streamlit instance and debug flag. Initial state variables are set up, and the initialization is logged.
2. **Chain Events**: Methods `on_chain_start`, `on_chain_end`, and `on_chain_error` handle the start, end, and error events of a chain, respectively. These methods log the events if debug is enabled.
3. **Tool Events**: Methods `on_tool_start`, `on_tool_end`, and `on_tool_error` handle the start, end, and error events of a tool, respectively. These methods log the events, update the callback state, and manage the status messages in Streamlit.
4. **Agent Events**: Methods `on_agent_action` and `on_agent_finish` handle the action and finish events of an agent, respectively. These methods log the events if debug is enabled.
5. **LLM Events**: Methods `_handle_llm_start`, `on_llm_start`, `on_chat_model_start`, `on_llm_new_token`, `on_llm_error`, and `on_llm_end` handle various events related to the LLM, such as start, new token, error, and end. These methods log the events, update the callback state, and manage the status messages in Streamlit.
6. **Miscellaneous Events**: Method `on_text` handles generic text events and logs them if debug is enabled.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The primary focus is on handling callback events and updating the Streamlit interface with status messages.