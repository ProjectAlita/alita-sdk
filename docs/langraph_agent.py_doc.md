# langraph_agent.py

**Path:** `src/alita_sdk/langchain/langraph_agent.py`

## Data Flow

The data flow within `langraph_agent.py` is centered around the creation and manipulation of state graphs for managing conversational agents. The data originates from YAML schemas and user inputs, which are processed and transformed through various nodes and edges within the state graph. The data is stored in a `BaseStore` and manipulated using tools and functions defined in the schema. The flow of data is managed by classes such as `ConditionalEdge`, `DecisionEdge`, and `TransitionalEdge`, which handle different types of transitions based on conditions, decisions, and predefined steps. The data is ultimately used to generate responses and manage the state of the conversation.

Example:
```python
class ConditionalEdge(Runnable):
    name = "ConditionalEdge"
    def __init__(self, condition: str, condition_inputs: Optional[list[str]] = [], 
                 conditional_outputs: Optional[list[str]] = [], default_output: str = 'END'):
        self.condition = condition
        self.condition_inputs = condition_inputs
        self.conditional_outputs = conditional_outputs
        self.default_output = default_output
    
    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> str:
        logger.info(f"Current state in condition edge - {state}")
        input_data = {}
        for field in self.condition_inputs:
            if field == 'messages':
                input_data['messages'] = convert_message_to_json(state.get('messages', []))
            elif field == 'last_message' and state.get('messages'):
                input_data['last_message'] = state['messages'][-1].content
            else:
                input_data[field] = state.get(field, "")    
        template = EvaluateTemplate(self.condition, input_data)
        result = template.evaluate()
        if isinstance(result, str):
            result = clean_string(result)
            if len(self.conditional_outputs) > 0:
                if result in self.conditional_outputs:
                    return result
                else:
                    return self.default_output
        if result == 'END':
            result = END
        dispatch_custom_event(
            "on_conditional_edge", {"condition": self.condition, "state": state}, config=config
        )
        return result
```

## Functions Descriptions

### `ConditionalEdge`

The `ConditionalEdge` class is responsible for handling transitions based on conditions. It takes a condition string, a list of condition inputs, and a list of conditional outputs. The `invoke` method evaluates the condition using the current state and returns the appropriate output based on the evaluation result.

### `DecisionEdge`

The `DecisionEdge` class handles transitions based on decisions made from the chat history and additional information. It takes a client, a list of steps, a description, and a list of decisional inputs. The `invoke` method generates a prompt based on the inputs and uses the client to make a decision, returning the appropriate next step.

### `TransitionalEdge`

The `TransitionalEdge` class handles predefined transitions to the next step. It takes the next step as an input and returns it when invoked.

### `prepare_output_schema`

The `prepare_output_schema` function prepares the output schema for the state graph. It sets up the output and stream channels, compiles the state graph, and attaches nodes and edges based on the schema.

### `create_graph`

The `create_graph` function creates a state graph from a YAML schema. It initializes the state graph, adds nodes and edges based on the schema, and validates the graph.

### `LangGraphAgentRunnable`

The `LangGraphAgentRunnable` class extends `CompiledStateGraph` and handles the invocation of the state graph. It processes the input, updates the state, and returns the output and thread ID.

## Dependencies Used and Their Descriptions

- `yaml`: Used for loading and parsing YAML schemas.
- `logging`: Used for logging information and debugging messages.
- `uuid4`: Used for generating unique thread IDs.
- `typing`: Provides type hints for function signatures.
- `langchain_core.callbacks`: Used for dispatching custom events.
- `langgraph.graph.graph`: Provides constants for start and end states.
- `langgraph.graph`: Provides the `StateGraph` class for managing state graphs.
- `langgraph.channels.ephemeral_value`: Provides the `EphemeralValue` class for managing ephemeral values.
- `langgraph.managed.base`: Provides the `is_managed_value` function for checking managed values.
- `langgraph.prebuilt`: Provides the `InjectedStore` class for managing injected stores.
- `langgraph.store.base`: Provides the `BaseStore` class for managing base stores.
- `langgraph.graph.state`: Provides the `CompiledStateGraph` class for managing compiled state graphs.
- `langchain_core.messages`: Provides the `HumanMessage` class for managing human messages.
- `langchain_core.tools`: Provides the `BaseTool` class for managing base tools.
- `langchain_core.runnables`: Provides the `RunnableConfig` and `Runnable` classes for managing runnables.
- `mixedAgentRenderes`: Provides the `convert_message_to_json` function for converting messages to JSON.
- `utils.evaluate`: Provides the `EvaluateTemplate` class for evaluating templates.
- `tools.llm`: Provides the `LLMNode` class for managing LLM nodes.
- `tools.tool`: Provides the `ToolNode` class for managing tool nodes.
- `tools.loop`: Provides the `LoopNode` class for managing loop nodes.
- `tools.loop_output`: Provides the `LoopToolNode` class for managing loop tool nodes.
- `tools.function`: Provides the `FunctionTool` class for managing function tools.
- `utils.utils`: Provides the `clean_string` function for cleaning strings.
- `utils`: Provides the `create_state` function for creating states.

## Functional Flow

The functional flow of `langraph_agent.py` involves the following steps:

1. **Initialization**: The state graph is initialized using the `StateGraph` class and the YAML schema is loaded.
2. **Node and Edge Addition**: Nodes and edges are added to the state graph based on the schema. Different types of nodes (function, tool, loop, LLM) and edges (conditional, decision, transitional) are handled by their respective classes.
3. **Validation**: The state graph is validated to ensure that all nodes and edges are correctly defined and connected.
4. **Invocation**: The state graph is invoked using the `LangGraphAgentRunnable` class, which processes the input, updates the state, and returns the output and thread ID.

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
        """ Create a message graph from a yaml schema """
        schema = yaml.safe_load(yaml_schema)
        logger.debug(f"Schema: {schema}")
        logger.debug(f"Tools: {tools}")
        state_class = create_state(schema.get('state', {}))
        lg_builder = StateGraph(state_class)
        interrupt_before = [clean_string(every) for every in schema.get('interrupt_before', [])]
        interrupt_after = [clean_string(every) for every in schema.get('interrupt_after', [])]
        try:
            for node in schema['nodes']:
                node_type = node.get('type', 'function')
                node_id = clean_string(node['id'])
                tool_name = clean_string(node.get('tool', node_id))
                logger.info(f"Node: {node_id} : {node_type} - {tool_name}")
                if node_type in ['function', 'tool', 'loop', 'loop_from_tool']:
                    for tool in tools:
                        if tool.name == tool_name:
                            if node_type == 'function':
                                lg_builder.add_node(node_id, FunctionTool(
                                    tool=tool, name=node['id'], return_type='dict',
                                    output_variables=node.get('output', []),
                                    input_mapping=node.get('input_mapping', {'messages': {'type': 'variable', 'value': 'messages'}}),
                                    input_variables=node.get('input', ['messages'])))
                            elif node_type == 'tool':
                                lg_builder.add_node(node_id, ToolNode(
                                    client=client, tool=tool,
                                    name=node['id'], return_type='dict',
                                    output_variables=node.get('output', []),
                                    input_variables=node.get('input', ['messages']),
                                    structured_output=node.get('structured_output', False)))
                            elif node_type == 'loop':
                                lg_builder.add_node(node_id, LoopNode(
                                    client=client, tool=tool, task=node.get('task', ""),
                                    name=node['id'], return_type='dict',
                                    output_variables=node.get('output', []),
                                    input_variables=node.get('input', ['messages'])))
                            elif node_type == 'loop_from_tool':
                                loop_tool = None
                                loop_tool_name = clean_string(node.get('loop_tool', 'None'))
                                for t in tools:
                                    logger.info(f"Tool: {t.name}")
                                    if t.name == loop_tool_name:
                                        loop_tool = t
                                if loop_tool:
                                    lg_builder.add_node(node_id, LoopToolNode(
                                        client=client, tool=tool,
                                        name=node['id'], return_type='dict',
                                        loop_tool=loop_tool,
                                        variables_mapping = node.get('variables_mapping', {}),
                                        output_variables=node.get('output', []),
                                        input_variables=node.get('input', ['messages']),
                                        structured_output=node.get('structured_output', False)))
                            break
                elif node_type == 'llm':
                    lg_builder.add_node(node_id, LLMNode(
                        client=client, prompt=node.get('prompt', {}),
                        name=node['id'], return_type='dict',
                        response_key=node.get('response_key', 'messages'),
                        output_variables=node.get('output', []),
                        input_variables=node.get('input', ['messages']),
                        structured_output=node.get('structured_output', False)))
                if node.get('transition'):
                    next_step=clean_string(node['transition'])
                    logger.info(f'Adding transition: {next_step}')
                    lg_builder.add_conditional_edges(node_id, TransitionalEdge(next_step))
                elif node.get('decision'):
                    logger.info(f'Adding decision: {node["decision"]["nodes"]}')
                    lg_builder.add_conditional_edges(node_id, DecisionEdge(
                        client, node['decision']['nodes'], 
                        node['decision'].get('description', ""),
                        decisional_inputs=node['decision'].get('decisional_inputs', ['messages']),
                        default_output=node['decision'].get('default_output', 'END')))
                elif node.get('condition'):
                    logger.info(f'Adding condition: {node["condition"]}')
                    condition_input = node['condition'].get('condition_input', ['messages'])
                    condition_definition = node['condition'].get('condition_definition', '')
                    lg_builder.add_conditional_edges(node_id, ConditionalEdge(
                        condition=condition_definition, condition_inputs=condition_input,
                        conditional_outputs=node['condition'].get('conditional_outputs', []),
                        default_output=node['condition'].get('default_output', 'END')))

            lg_builder.set_entry_point(clean_string(schema['entry_point']))
            
            # assign default values
            interrupt_before = interrupt_before or []
            interrupt_after = interrupt_after or []
            
            # validate the graph
            lg_builder.validate(
                interrupt=(
                    (interrupt_before if interrupt_before != "*" else []) + interrupt_after
                    if interrupt_after != "*"
                    else []
                )
            )
        except ValueError as e:
            raise ValueError(f"Validation of the schema failed. {e}\n\nDEBUG INFO:**Schema Nodes:**\n\n{lg_builder.nodes}\n\n**Schema Enges:**\n\n{lg_builder.edges}\n\n**Tools Available:**\n\n{tools}") 
        compiled = prepare_output_schema(lg_builder, memory, store, debug, 
                                         interrupt_before=interrupt_before, 
                                         interrupt_after=interrupt_after)
        return compiled.validate()
```

## Endpoints Used/Created

No explicit endpoints are defined or used within `langraph_agent.py`. The functionality is focused on managing state graphs and transitions within a conversational agent framework.