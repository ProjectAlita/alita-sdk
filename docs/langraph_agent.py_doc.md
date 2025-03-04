# langraph_agent.py

**Path:** `src/alita_sdk/langchain/langraph_agent.py`

## Data Flow

The data flow within `langraph_agent.py` revolves around the creation and manipulation of state graphs for managing conversational agents. The data originates from YAML schemas and user inputs, which are then processed through various nodes and edges defined in the state graph. The data is transformed as it moves through different nodes, each performing specific tasks such as invoking tools, making decisions, or transitioning states. The final output is generated based on the processed data and is returned to the user.

Example:
```python
schema = yaml.safe_load(yaml_schema)
state_class = create_state(schema.get('state', {}))
lg_builder = StateGraph(state_class)
```
In this example, the YAML schema is loaded, and a state class is created based on the schema. The state graph builder (`lg_builder`) is then initialized with the state class.

## Functions Descriptions

### `ConditionalEdge`

This class represents a conditional edge in the state graph. It evaluates a condition based on the current state and determines the next step in the graph. The `invoke` method processes the state and returns the result of the condition evaluation.

### `DecisionEdge`

This class represents a decision edge in the state graph. It uses a client to make decisions based on the chat history and additional information. The `invoke` method processes the state and returns the result of the decision.

### `TransitionalEdge`

This class represents a transitional edge in the state graph. It simply transitions to the next step specified during initialization. The `invoke` method processes the state and returns the next step.

### `prepare_output_schema`

This function prepares the output schema for the state graph. It sets up the output and stream channels, attaches nodes and edges, and returns the compiled state graph.

### `create_graph`

This function creates a state graph from a YAML schema and a list of tools. It initializes the state graph builder, adds nodes and edges based on the schema, and validates the graph. The compiled graph is then returned.

### `LangGraphAgentRunnable`

This class represents a runnable state graph. It extends `CompiledStateGraph` and overrides the `invoke` method to process input and return the output.

## Dependencies Used and Their Descriptions

- `yaml`: Used for loading and parsing YAML schemas.
- `logging`: Used for logging information and debugging messages.
- `uuid4`: Used for generating unique thread IDs.
- `langchain_core.callbacks`: Used for dispatching custom events.
- `langgraph.graph`: Used for managing state graphs and their components.
- `langgraph.channels.ephemeral_value`: Used for handling ephemeral values in the state graph.
- `langgraph.managed.base`: Used for checking if a value is managed.
- `langgraph.prebuilt`: Used for injecting stores into the state graph.
- `langgraph.store.base`: Used for defining base store classes.
- `langgraph.graph.state`: Used for compiling state graphs.
- `langchain_core.messages`: Used for handling messages in the state graph.
- `langchain_core.tools`: Used for defining base tools.
- `langchain_core.runnables`: Used for defining runnable configurations and classes.
- `mixedAgentRenderes`: Used for converting messages to JSON format.
- `utils.evaluate`: Used for evaluating templates.
- `tools.llm`: Used for defining LLM nodes.
- `tools.tool`: Used for defining tool nodes.
- `tools.loop`: Used for defining loop nodes.
- `tools.loop_output`: Used for defining loop tool nodes.
- `tools.function`: Used for defining function tools.
- `tools.indexer_tool`: Used for defining indexer nodes.
- `utils.utils`: Used for cleaning strings.
- `utils`: Used for creating state.

## Functional Flow

The functional flow of `langraph_agent.py` involves the following steps:
1. Load the YAML schema and create the state class.
2. Initialize the state graph builder with the state class.
3. Add nodes and edges to the state graph based on the schema.
4. Validate the state graph.
5. Prepare the output schema and compile the state graph.
6. Invoke the compiled state graph with the input and return the output.

Example:
```python
schema = yaml.safe_load(yaml_schema)
state_class = create_state(schema.get('state', {}))
lg_builder = StateGraph(state_class)
compiled = prepare_output_schema(lg_builder, memory, store, debug, 
                                 interrupt_before=interrupt_before, 
                                 interrupt_after=interrupt_after)
return compiled.validate()
```
In this example, the YAML schema is loaded, the state class is created, the state graph builder is initialized, the output schema is prepared, and the compiled state graph is validated.

## Endpoints Used/Created

There are no explicit endpoints defined or used within `langraph_agent.py`. The functionality revolves around creating and managing state graphs for conversational agents based on YAML schemas and user inputs.