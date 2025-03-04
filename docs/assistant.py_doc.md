# assistant.py

**Path:** `src/alita_sdk/langchain/assistant.py`

## Data Flow

The data flow within the `assistant.py` file is centered around the initialization and utilization of an AI assistant. The data originates from the parameters passed to the `Assistant` class constructor, which includes `alita`, `data`, `client`, `chat_history`, `app_type`, `tools`, and `memory`. These parameters are used to configure the AI client and set up the tools and prompts required for the assistant's operation.

The `data` dictionary contains settings for the language model, such as `max_tokens`, `temperature`, `top_p`, `top_k`, `model_name`, and `integration_uid`. These settings are applied to the `client` object. The `data` dictionary also includes instructions and variables that are used to create the prompt for the assistant.

The assistant's tools are initialized using the `get_tools` function, which takes the tools specified in the `data` dictionary and configures them with the `alita` client and the language model client. The tools are then combined with any additional tools passed to the constructor.

The prompt for the assistant is created based on the `app_type`. For example, if the `app_type` is `react`, the prompt includes a `HumanMessage` with the `REACT_ADDON`. The prompt is further customized with variables and input variables from the `data` dictionary.

The `runnable` method determines the type of agent executor to use based on the `app_type`. It returns the appropriate executor, such as `getOpenAIToolsAgentExecutor` for `openai` or `getXMLAgentExecutor` for `xml`.

Here is an example of data transformation within the `Assistant` class:

```python
self.client = copy(client)
self.client.max_tokens = data['llm_settings']['max_tokens']
self.client.temperature = data['llm_settings']['temperature']
self.client.top_p = data['llm_settings']['top_p']
self.client.top_k = data['llm_settings']['top_k']
self.client.model_name = data['llm_settings']['model_name']
self.client.integration_uid = data['llm_settings']['integration_uid']
```

In this snippet, the `client` object is copied and its settings are updated based on the values in the `data` dictionary.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `Assistant` class. It takes several parameters, including `alita`, `data`, `client`, `chat_history`, `app_type`, `tools`, and `memory`. The method configures the `client` object with settings from the `data` dictionary and sets up the tools and prompt for the assistant.

### `runnable`

The `runnable` method determines the type of agent executor to use based on the `app_type`. It returns the appropriate executor, such as `getOpenAIToolsAgentExecutor` for `openai` or `getXMLAgentExecutor` for `xml`.

### `_agent_executor`

The `_agent_executor` method creates an `AgentExecutor` from the given agent and tools. It sets various parameters for the executor, such as `verbose`, `handle_parsing_errors`, `max_execution_time`, and `return_intermediate_steps`.

### `getAgentExecutor`

The `getAgentExecutor` method creates a JSON chat agent using the `create_json_chat_agent` function. It then returns an `AgentExecutor` for the agent.

### `getXMLAgentExecutor`

The `getXMLAgentExecutor` method creates an XML chat agent using the `create_xml_chat_agent` function. It then returns an `AgentExecutor` for the agent.

### `getOpenAIToolsAgentExecutor`

The `getOpenAIToolsAgentExecutor` method creates an OpenAI tools agent using the `create_openai_tools_agent` function. It then returns an `AgentExecutor` for the agent.

### `pipeline`

The `pipeline` method creates a graph-based agent using the `create_graph` function. It sets up the agent with the client, tools, and prompt, and returns the agent.

### `apredict`

The `apredict` method is used for asynchronous prediction. It takes a list of messages and yields results from the client's `ainvoke` method.

### `predict`

The `predict` method is used for synchronous prediction. It takes a list of messages and returns results from the client's `invoke` method.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging debug and information messages throughout the `Assistant` class.

### `importlib`

The `importlib` module is used to dynamically import the language model class based on the `model_type` specified in the `data` dictionary.

### `copy`

The `copy` function from the `copy` module is used to create a deep copy of the `client` object.

### `typing`

The `typing` module is used for type hints, such as `Any`, `Optional`, and `list`.

### `langchain.agents`

The `langchain.agents` module is used to create different types of agents, such as JSON chat agents and OpenAI tools agents.

### `langchain_core.messages`

The `langchain_core.messages` module is used for message types, such as `BaseMessage`, `SystemMessage`, and `HumanMessage`.

### `langchain_core.prompts`

The `langchain_core.prompts` module is used for the `MessagesPlaceholder` class.

### `constants`

The `constants` module is used for constants like `REACT_ADDON`, `REACT_VARS`, and `XML_ADDON`.

### `chat_message_template`

The `chat_message_template` module is used for the `Jinja2TemplatedChatMessagesTemplate` class.

### `tools.echo`

The `tools.echo` module is used for the `EchoTool` class.

### `toolkits.tools`

The `toolkits.tools` module is used for the `get_tools` function.

## Functional Flow

The functional flow of the `assistant.py` file begins with the initialization of the `Assistant` class. The `__init__` method configures the client, tools, and prompt based on the parameters passed to it. The `runnable` method determines the type of agent executor to use based on the `app_type` and returns the appropriate executor.

The `_agent_executor` method creates an `AgentExecutor` from the given agent and tools. The `getAgentExecutor`, `getXMLAgentExecutor`, and `getOpenAIToolsAgentExecutor` methods create different types of agents and return their respective executors.

The `pipeline` method creates a graph-based agent and returns it. The `apredict` and `predict` methods are used for asynchronous and synchronous predictions, respectively.

Here is an example of the functional flow within the `Assistant` class:

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

In this snippet, the `runnable` method determines the type of agent executor to use based on the `app_type` and returns the appropriate executor.

## Endpoints Used/Created

The `assistant.py` file does not explicitly define or call any endpoints. The functionality is focused on creating and managing different types of agents and their executors based on the provided configuration and parameters.