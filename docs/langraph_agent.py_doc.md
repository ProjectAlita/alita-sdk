# langraph_agent.py

**Path:** `src/alita_sdk/langchain/langraph_agent.py`

## Data Flow

The data flow within `langraph_agent.py` revolves around the creation and manipulation of state graphs for managing conversational agents. The data originates from YAML schemas and user inputs, which are then processed through various nodes and edges within the state graph. The data is transformed as it moves through different nodes, each performing specific tasks such as invoking tools, making decisions, or transitioning states. The final output is generated based on the processed data and is returned to the user.

Example:
```python
schema = yaml.safe_load(yaml_schema)
state_class = create_state(schema.get('state', {}))
lg_builder = StateGraph(state_class)
```
In this example, the YAML schema is loaded, and a state class is created based on the schema. The state class is then used to initialize a `StateGraph` object, which will manage the flow of data through various nodes and edges.

## Functions Descriptions

### `ConditionalEdge`

The `ConditionalEdge` class is responsible for evaluating conditions and determining the next step based on the evaluation result. It takes a condition string, condition inputs, conditional outputs, and a default output as parameters. The `invoke` method evaluates the condition using the provided inputs and returns the appropriate output.

Example:
```python
def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> str:
    input_data = {}
    for field in self.condition_inputs:
        input_data[field] = state.get(field, "")
    template = EvaluateTemplate(self.condition, input_data)
    result = template.evaluate()
    return result
```
In this example, the `invoke` method collects input data from the state, evaluates the condition using the `EvaluateTemplate` class, and returns the result.

### `DecisionEdge`

The `DecisionEdge` class is responsible for making decisions based on chat history and additional information. It takes a client, steps, description, decisional inputs, and a default output as parameters. The `invoke` method generates a prompt, sends it to the client for completion, and returns the appropriate step based on the completion result.

Example:
```python
def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> str:
    decision_input.append(HumanMessage(self.prompt.format(steps=self.steps, description=self.description, additional_info=additional_info)))
    completion = self.client.invoke(decision_input)
    result = clean_string(completion.content.strip())
    return result
```
In this example, the `invoke` method generates a prompt, sends it to the client for completion, and returns the cleaned result.

### `TransitionalEdge`

The `TransitionalEdge` class is responsible for transitioning to the next step. It takes the next step as a parameter. The `invoke` method logs the transition and returns the next step.

Example:
```python
def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: RunnableConfig, *args, **kwargs):
    logger.info(f'Transitioning to: {self.next_step}')
    return self.next_step if self.next_step != 'END' else END
```
In this example, the `invoke` method logs the transition and returns the next step.

### `prepare_output_schema`

The `prepare_output_schema` function prepares the output schema for the state graph. It takes various parameters such as `lg_builder`, `memory`, `store`, `debug`, `interrupt_before`, and `interrupt_after`. The function initializes the output and stream channels, compiles the state graph, attaches nodes and edges, and returns the compiled state graph.

Example:
```python
compiled = LangGraphAgentRunnable(
    builder=lg_builder,
    config_type=lg_builder.config_schema,
    nodes={},
    channels={
        **lg_builder.channels,
        **lg_builder.managed,
        START: EphemeralValue(lg_builder.input),
    },
    input_channels=START,
    stream_mode="updates",
    output_channels=output_channels,
    stream_channels=stream_channels,
    checkpointer=memory,
    interrupt_before_nodes=interrupt_before,
    interrupt_after_nodes=interrupt_after,
    auto_validate=False,
    debug=debug,
    store=store,
)
```
In this example, the `LangGraphAgentRunnable` object is initialized with various parameters, including the state graph builder, channels, and memory.

### `create_graph`

The `create_graph` function creates a message graph from a YAML schema. It takes various parameters such as `client`, `yaml_schema`, `tools`, `memory`, `store`, `debug`, and additional arguments. The function loads the schema, initializes the state graph, adds nodes and edges, validates the graph, and returns the compiled state graph.

Example:
```python
schema = yaml.safe_load(yaml_schema)
state_class = create_state(schema.get('state', {}))
lg_builder = StateGraph(state_class)
```
In this example, the YAML schema is loaded, and a state class is created based on the schema. The state class is then used to initialize a `StateGraph` object.

### `LangGraphAgentRunnable`

The `LangGraphAgentRunnable` class extends `CompiledStateGraph` and is responsible for invoking the state graph. It takes input data, configuration, and additional arguments. The `invoke` method updates the state, invokes the state graph, and returns the output and thread ID.

Example:
```python
def invoke(self, input: Union[dict[str, Any], Any], config: Optional[RunnableConfig] = None, *args, **kwargs):
    if not config.get("configurable", {}).get("thread_id"):
        config["configurable"] = {"thread_id": str(uuid4())}
    thread_id = config.get("configurable", {}).get("thread_id")
    result = super().invoke(input, config=config, *args, **kwargs)
    return {
        "output": result['messages'][-1].content,
        "thread_id": thread_id
    }
```
In this example, the `invoke` method updates the state, invokes the state graph, and returns the output and thread ID.

## Dependencies Used and Their Descriptions

### `yaml`

The `yaml` library is used for parsing YAML schemas. It provides functions to load and parse YAML data, which is essential for creating the state graph from a YAML schema.

### `logging`

The `logging` library is used for logging information, warnings, and errors. It helps in tracking the flow of data and debugging issues within the code.

### `uuid`

The `uuid` library is used for generating unique identifiers. It is used in the `LangGraphAgentRunnable` class to generate unique thread IDs for each invocation.

### `typing`

The `typing` library is used for type hinting. It provides various type hints such as `Union`, `Any`, `Optional`, and `Annotated`, which help in defining the expected types of function parameters and return values.

### `langchain_core`

The `langchain_core` library provides various core functionalities such as callbacks, messages, tools, and runnables. It is used extensively throughout the code for managing state, invoking tools, and handling messages.

### `langgraph`

The `langgraph` library provides functionalities for creating and managing state graphs. It includes classes and functions for defining nodes, edges, and state transitions, which are essential for building the conversational agent's state graph.

## Functional Flow

The functional flow of `langraph_agent.py` involves the following steps:

1. **Loading the YAML Schema:** The YAML schema is loaded and parsed to extract the state, nodes, and edges.
2. **Creating the State Graph:** A `StateGraph` object is created using the parsed schema. Nodes and edges are added to the state graph based on the schema.
3. **Preparing the Output Schema:** The output schema is prepared by initializing channels, compiling the state graph, and attaching nodes and edges.
4. **Creating the Graph:** The message graph is created by loading the schema, initializing the state graph, adding nodes and edges, validating the graph, and returning the compiled state graph.
5. **Invoking the State Graph:** The state graph is invoked with input data and configuration. The state is updated, the state graph is invoked, and the output and thread ID are returned.

Example:
```python
schema = yaml.safe_load(yaml_schema)
state_class = create_state(schema.get('state', {}))
lg_builder = StateGraph(state_class)
compiled = prepare_output_schema(lg_builder, memory, store, debug, interrupt_before=interrupt_before, interrupt_after=interrupt_after)
return compiled.validate()
```
In this example, the YAML schema is loaded, the state class is created, the state graph is initialized, the output schema is prepared, and the compiled state graph is validated and returned.

## Endpoints Used/Created

The `langraph_agent.py` file does not explicitly define or call any endpoints. However, it interacts with various tools and clients that may involve API calls or other forms of communication. The specific endpoints and interactions would depend on the tools and clients used within the state graph.