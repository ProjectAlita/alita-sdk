# langraph_agent.py

**Path:** `src/alita_sdk/langchain/langraph_agent.py`

## Data Flow

The data flow within `langraph_agent.py` revolves around the creation and manipulation of state graphs for managing conversational agents. The data originates from YAML schemas and user inputs, which are then processed through various nodes and edges defined in the state graph. The data is transformed as it passes through different nodes, which can be functions, tools, loops, or decision points. The final output is generated based on the state of the graph and the transitions between nodes.

Example:
```python
schema = yaml.safe_load(yaml_schema)
state_class = create_state(schema.get('state', {}))
lg_builder = StateGraph(state_class)
```
In this example, the YAML schema is loaded, and a state class is created based on the schema. The state class is then used to initialize a `StateGraph` object, which will manage the flow of data through the graph.

## Functions Descriptions

### ConditionalEdge

The `ConditionalEdge` class represents a conditional transition between nodes in the state graph. It evaluates a condition based on the current state and determines the next node to transition to.

**Inputs:**
- `condition`: A string representing the condition to evaluate.
- `condition_inputs`: A list of state fields to use as inputs for the condition.
- `conditional_outputs`: A list of possible outputs based on the condition.
- `default_output`: The default output if the condition does not match any of the conditional outputs.

**Outputs:**
- The next node to transition to based on the evaluated condition.

Example:
```python
class ConditionalEdge(Runnable):
    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> str:
        input_data = {}
        for field in self.condition_inputs:
            input_data[field] = state.get(field, "")
        template = EvaluateTemplate(self.condition, input_data)
        result = template.evaluate()
        return result
```
In this example, the `invoke` method evaluates the condition using the specified inputs and returns the result, which determines the next node to transition to.

### DecisionEdge

The `DecisionEdge` class represents a decision point in the state graph. It uses a prompt to determine the next step based on the current state and additional information.

**Inputs:**
- `client`: The client to use for making decisions.
- `steps`: A list of possible steps to choose from.
- `description`: A description of the decision point.
- `decisional_inputs`: A list of state fields to use as inputs for the decision.
- `default_output`: The default output if no valid decision is made.

**Outputs:**
- The next node to transition to based on the decision made.

Example:
```python
class DecisionEdge(Runnable):
    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> str:
        decision_input = state.get('messages', [])[:]
        completion = self.client.invoke(decision_input)
        result = clean_string(completion.content.strip())
        return result
```
In this example, the `invoke` method uses the client to make a decision based on the current state and returns the result, which determines the next node to transition to.

### TransitionalEdge

The `TransitionalEdge` class represents a simple transition between nodes in the state graph.

**Inputs:**
- `next_step`: The next node to transition to.

**Outputs:**
- The next node to transition to.

Example:
```python
class TransitionalEdge(Runnable):
    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: RunnableConfig, *args, **kwargs):
        return self.next_step
```
In this example, the `invoke` method simply returns the next step, which determines the next node to transition to.

### prepare_output_schema

The `prepare_output_schema` function prepares the output schema for the state graph by attaching nodes and edges to the graph.

**Inputs:**
- `lg_builder`: The state graph builder.
- `memory`: The memory to use for the graph.
- `store`: The store to use for the graph.
- `debug`: A flag indicating whether to enable debug mode.
- `interrupt_before`: A list of nodes to interrupt before.
- `interrupt_after`: A list of nodes to interrupt after.

**Outputs:**
- The compiled state graph.

Example:
```python
def prepare_output_schema(lg_builder, memory, store, debug=False, interrupt_before=[], interrupt_after=[]):
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
    return compiled
```
In this example, the `prepare_output_schema` function initializes a `LangGraphAgentRunnable` object with the specified parameters and returns the compiled state graph.

### create_graph

The `create_graph` function creates a state graph from a YAML schema and a list of tools.

**Inputs:**
- `client`: The client to use for the graph.
- `yaml_schema`: The YAML schema defining the graph.
- `tools`: A list of tools to use in the graph.
- `memory`: The memory to use for the graph.
- `store`: The store to use for the graph.
- `debug`: A flag indicating whether to enable debug mode.

**Outputs:**
- The compiled state graph.

Example:
```python
def create_graph(
        client: Any, 
        yaml_schema: str, 
        tools: list[BaseTool], 
        *args,
        memory: Optional[Any] = None,
        store: Optional[BaseStore] = None,
        debug: bool = False,
        **kwargs
    ):
    schema = yaml.safe_load(yaml_schema)
    state_class = create_state(schema.get('state', {}))
    lg_builder = StateGraph(state_class)
    compiled = prepare_output_schema(lg_builder, memory, store, debug)
    return compiled.validate()
```
In this example, the `create_graph` function loads the YAML schema, creates a state class, initializes a `StateGraph` object, prepares the output schema, and returns the compiled state graph.

### LangGraphAgentRunnable

The `LangGraphAgentRunnable` class represents a runnable state graph for managing conversational agents.

**Inputs:**
- `input`: The input data for the graph.
- `config`: The configuration for the graph.

**Outputs:**
- The output of the graph.

Example:
```python
class LangGraphAgentRunnable(CompiledStateGraph):
    def invoke(self, input: Union[dict[str, Any], Any], 
               config: Optional[RunnableConfig] = None, 
               *args, **kwargs):
        result = super().invoke(input, config=config, *args, **kwargs)
        output = result['messages'][-1].content
        return {
            "output": output,
            "thread_id": config['configurable']['thread_id']
        }
```
In this example, the `invoke` method processes the input data through the state graph and returns the output and thread ID.

## Dependencies Used and Their Descriptions

### yaml

The `yaml` library is used for parsing YAML schemas that define the state graph.

### logging

The `logging` library is used for logging debug and information messages throughout the code.

### uuid

The `uuid` library is used for generating unique thread IDs for each invocation of the state graph.

### typing

The `typing` library is used for type annotations in function signatures and class definitions.

### langchain_core.callbacks

The `langchain_core.callbacks` module is used for dispatching custom events during the execution of the state graph.

### langgraph.graph

The `langgraph.graph` module is used for creating and managing state graphs, including nodes, edges, and transitions.

### langgraph.channels.ephemeral_value

The `langgraph.channels.ephemeral_value` module is used for managing ephemeral values in the state graph.

### langgraph.managed.base

The `langgraph.managed.base` module is used for checking if a value is managed within the state graph.

### langgraph.prebuilt

The `langgraph.prebuilt` module is used for injecting prebuilt stores into the state graph.

### langgraph.store.base

The `langgraph.store.base` module is used for defining base store classes for managing state in the state graph.

### langgraph.graph.state

The `langgraph.graph.state` module is used for compiling state graphs into runnable objects.

### langchain_core.messages

The `langchain_core.messages` module is used for managing messages within the state graph.

### langchain_core.tools

The `langchain_core.tools` module is used for defining base tool classes for use in the state graph.

### langchain_core.runnables

The `langchain_core.runnables` module is used for defining runnable configurations and base runnable classes for the state graph.

### mixedAgentRenderes

The `mixedAgentRenderes` module is used for converting messages to JSON format.

### utils.evaluate

The `utils.evaluate` module is used for evaluating templates within the state graph.

### tools.llm

The `tools.llm` module is used for defining LLM nodes in the state graph.

### tools.tool

The `tools.tool` module is used for defining tool nodes in the state graph.

### tools.loop

The `tools.loop` module is used for defining loop nodes in the state graph.

### tools.loop_output

The `tools.loop_output` module is used for defining loop tool nodes in the state graph.

### tools.function

The `tools.function` module is used for defining function tool nodes in the state graph.

### utils.utils

The `utils.utils` module is used for utility functions such as cleaning strings.

### utils

The `utils` module is used for creating state objects within the state graph.

## Functional Flow

The functional flow of `langraph_agent.py` involves the following steps:
1. Load the YAML schema and create a state class based on the schema.
2. Initialize a `StateGraph` object with the state class.
3. Add nodes and edges to the state graph based on the schema and tools provided.
4. Set the entry point for the state graph.
5. Validate the state graph.
6. Prepare the output schema for the state graph.
7. Compile the state graph into a runnable object.
8. Invoke the state graph with input data and configuration.
9. Process the input data through the state graph and generate the output.

Example:
```python
schema = yaml.safe_load(yaml_schema)
state_class = create_state(schema.get('state', {}))
lg_builder = StateGraph(state_class)
compiled = prepare_output_schema(lg_builder, memory, store, debug)
result = compiled.invoke(input, config=config)
```
In this example, the YAML schema is loaded, a state class is created, a `StateGraph` object is initialized, the output schema is prepared, and the state graph is invoked with input data and configuration.

## Endpoints Used/Created

There are no explicit endpoints used or created within `langraph_agent.py`. The functionality is focused on creating and managing state graphs for conversational agents, and the interactions are primarily internal to the state graph and its nodes.