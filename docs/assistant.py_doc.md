# assistant.py

**Path:** `src/alita_sdk/langchain/assistant.py`

## Data Flow

The data flow within the `assistant.py` file is centered around the initialization and configuration of an AI assistant, which is designed to interact with various tools and handle different types of chat applications. The data originates from the input parameters provided to the `Assistant` class, which include configurations for the language model, tools, and chat history. These parameters are used to set up the AI client and its associated tools.

The data undergoes several transformations, such as copying the client configuration, setting up the tools, and preparing the prompt for the chat agent. The final destination of the data is the execution of the agent, which can be in different forms such as a pipeline, OpenAI tools agent, or XML agent. Intermediate variables like `model_type`, `model_params`, and `messages` are used to store temporary data during these transformations.

Example:
```python
self.client = copy(client)
self.client.max_tokens = data['llm_settings']['max_tokens']
self.client.temperature = data['llm_settings']['temperature']
self.client.top_p = data['llm_settings']['top_p']
self.client.top_k = data['llm_settings']['top_k']
self.client.model_name = data['llm_settings']['model_name']
self.client.integration_uid = data['llm_settings']['integration_uid']
```
In this snippet, the client configuration is copied and various settings are applied based on the input data.

## Functions Descriptions

### `__init__`
The `__init__` function initializes the `Assistant` class. It takes parameters such as `alita`, `data`, `client`, `chat_history`, `app_type`, `tools`, and `memory`. It sets up the client configuration, initializes tools, and prepares the prompt based on the application type. The function also logs important information for debugging purposes.

### `runnable`
The `runnable` function determines the type of agent executor to be used based on the `app_type`. It returns the appropriate executor function, such as `pipeline`, `getOpenAIToolsAgentExecutor`, `getXMLAgentExecutor`, or `getAgentExecutor`.

### `_agent_executor`
The `_agent_executor` function creates an `AgentExecutor` from the given agent and tools. It configures the executor with parameters like verbosity, error handling, and execution time.

### `getAgentExecutor`
The `getAgentExecutor` function creates a JSON chat agent using the client, tools, and prompt. It then returns the agent executor created by `_agent_executor`.

### `getXMLAgentExecutor`
The `getXMLAgentExecutor` function creates an XML chat agent using the client, tools, and prompt. It then returns the agent executor created by `_agent_executor`.

### `getOpenAIToolsAgentExecutor`
The `getOpenAIToolsAgentExecutor` function creates an OpenAI tools agent using the client, tools, and prompt. It then returns the agent executor created by `_agent_executor`.

### `pipeline`
The `pipeline` function sets up a memory saver if no memory is provided. It creates a graph-based agent using the client, tools, and prompt, and returns the agent.

### `apredict`
The `apredict` function is used for asynchronous prediction. It yields results from the client's `ainvoke` method.

### `predict`
The `predict` function is used for synchronous prediction. It returns results from the client's `invoke` method.

## Dependencies Used and Their Descriptions

### `logging`
Used for logging debug and information messages throughout the code.

### `importlib`
Used for dynamic import of modules and classes based on string names.

### `copy`
Used to create a deep copy of the client configuration.

### `typing`
Provides type hints for better code readability and maintenance.

### `langchain.agents`
Provides various agent creation functions like `create_openai_tools_agent` and `create_json_chat_agent`.

### `langchain_core.messages`
Provides message classes like `BaseMessage`, `SystemMessage`, and `HumanMessage` used in chat interactions.

### `langchain_core.prompts`
Provides the `MessagesPlaceholder` class used in prompt templates.

### `constants`
Defines constants like `REACT_ADDON`, `REACT_VARS`, and `XML_ADDON` used in the prompt setup.

### `chat_message_template`
Provides the `Jinja2TemplatedChatMessagesTemplate` class used for creating chat message templates.

### `tools.echo`
Provides the `EchoTool` class used as a default tool in the agent.

### `toolkits.tools`
Provides the `get_tools` function used to initialize tools based on the input data.

## Functional Flow

1. **Initialization**: The `Assistant` class is initialized with the provided parameters, setting up the client, tools, and prompt.
2. **Runnable Determination**: The `runnable` function determines the type of agent executor to be used based on the `app_type`.
3. **Agent Execution**: The appropriate agent executor function is called, which creates the agent and returns the executor.
4. **Prediction**: The `predict` or `apredict` function is used to get predictions from the client.

Example:
```python
def runnable(self):
    if self.app_type == 'pipeline':
        return self.pipeline()
    elif self.app_type == 'openai':
        return self.getOpenAIToolsAgentExecutor()
    elif self.app_type == 'xml':
        return self.getXMLAgentExecutor()
    else:
        self.tools = [EchoTool()] + self.tools
        return self.getAgentExecutor()
```
In this snippet, the `runnable` function selects the appropriate agent executor based on the `app_type`.

## Endpoints Used/Created

The `assistant.py` file does not explicitly define or call any endpoints. The focus is on setting up and executing different types of chat agents using the provided client and tools.