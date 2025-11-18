import logging
import re
from typing import Union, Any, Optional, Annotated, get_type_hints
from uuid import uuid4
from typing import Dict

import yaml
import ast
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from langgraph.channels.ephemeral_value import EphemeralValue
from langgraph.graph import StateGraph
from langgraph.graph.graph import END, START
from langgraph.graph.state import CompiledStateGraph
from langgraph.managed.base import is_managed_value
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore

from .constants import PRINTER_NODE_RS
from .mixedAgentRenderes import convert_message_to_json
from .utils import create_state, propagate_the_input_mapping, safe_format
from ..tools.function import FunctionTool
from ..tools.indexer_tool import IndexerNode
from ..tools.llm import LLMNode
from ..tools.loop import LoopNode
from ..tools.loop_output import LoopToolNode
from ..tools.tool import ToolNode
from ..utils.evaluate import EvaluateTemplate
from ..utils.utils import clean_string, TOOLKIT_SPLITTER
from ..tools.router import RouterNode

logger = logging.getLogger(__name__)

# Global registry for subgraph definitions
# Structure: {'subgraph_name': {'yaml': 'yaml_def', 'tools': [tools], 'flattened': False}}
SUBGRAPH_REGISTRY: Dict[str, Dict[str, Any]] = {}


# Wrapper for injecting a compiled subgraph into a parent StateGraph
class SubgraphRunnable(CompiledStateGraph):
    def __init__(
        self,
        inner: CompiledStateGraph,
        *,
        name: str,
        input_mapping: Dict[str, Any],
        output_mapping: Dict[str, Any]
    ):
        # copy child graph internals
        super().__init__(
            builder=inner.builder,
            config_type=inner.config_type,
            nodes=inner.nodes,
            channels=inner.channels,
            input_channels=inner.input_channels,
            stream_mode=inner.stream_mode,
            output_channels=inner.output_channels,
            stream_channels=inner.stream_channels,
            checkpointer=inner.checkpointer,
            interrupt_before_nodes=inner.interrupt_before_nodes,
            interrupt_after_nodes=inner.interrupt_after_nodes,
            auto_validate=False,
            debug=inner.debug,
            store=inner.store,
        )
        self.inner = inner
        self.name = name
        self.input_mapping = input_mapping or {}
        self.output_mapping = output_mapping or {}

    def invoke(
        self,
        state: Union[dict[str, Any], Any],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> Union[dict[str, Any], Any]:
        # Detailed logging for debugging
        logger.debug(f"SubgraphRunnable '{self.name}' invoke called with state: {state}")
        logger.debug(f"SubgraphRunnable '{self.name}' config: {config}")

        # 1) parent -> child mapping
        if not self.input_mapping:
            child_input = state.copy()
        else:
            child_input = propagate_the_input_mapping(
                self.input_mapping, list(self.input_mapping.keys()), state
            )
        # debug trace of messages flowing into child
        logger.debug(f"SubgraphRunnable '{self.name}' child_input.messages: {child_input.get('messages')}")
        logger.debug(f"SubgraphRunnable '{self.name}' child_input.input: {child_input.get('input')}")

        # 2) Invoke the child graph.
        # Pass None as the first argument for input if the child is expected to resume
        # using its (now updated) checkpoint. The CompiledStateGraph.invoke method, when
        # input is None but a checkpoint exists, loads from the checkpoint.
        # Any resume commands (if applicable for internal child interrupts) are in 'config'.
        # logger.debug(f"SubgraphRunnable '{self.name}': Invoking child graph super().invoke(None, config).")
        subgraph_output = super().invoke(child_input, config=config, **kwargs)

        # 3) child complete: apply output_mapping or passthrough
        logger.debug(f"SubgraphRunnable '{self.name}' child complete, applying mappings")
        result: Dict[str, Any] = {}
        if self.output_mapping:
            for child_key, parent_key in self.output_mapping.items():
                if child_key in subgraph_output:
                    state[parent_key] = subgraph_output[child_key]
                    result[parent_key] = subgraph_output[child_key]
                    logger.debug(f"SubgraphRunnable '{self.name}' mapped {child_key} -> {parent_key}")
        else:
            for k, v in subgraph_output.items():
                state[k] = v
                result[k] = v

        # include full messages history on completion
        if 'messages' not in result:
            result['messages'] = subgraph_output.get('messages', [])
        logger.debug(f"SubgraphRunnable '{self.name}' returning result: {result}")
        return result


class ConditionalEdge(Runnable):
    name = "ConditionalEdge"

    def __init__(self, condition: str, condition_inputs: Optional[list[str]] = [],
                 conditional_outputs: Optional[list[str]] = [], default_output: str = END):
        self.condition = condition
        self.condition_inputs = condition_inputs
        self.conditional_outputs = {clean_string(cond if not 'END' == cond else '__end__') for cond in conditional_outputs}
        self.default_output = clean_string(default_output)

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


class DecisionEdge(Runnable):
    name = "DecisionEdge"
    prompt: str = """Based on chat history and additional_info make a decision what step need to be next.
Steps available: {steps}
Explanation: {description}

{additional_info}

### Expected output:
Answer only with step name, no need to add descrip in case none of the steps are applibcable answer with 'END'
"""

    def __init__(self, client, steps: str, description: str = "", decisional_inputs: Optional[list[str]] = [],
                 default_output: str = 'END'):
        self.client = client
        self.steps = ",".join([clean_string(step) for step in steps])
        self.description = description
        self.decisional_inputs = decisional_inputs
        self.default_output = default_output if default_output != 'END' else END

    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> str:
        additional_info = ""
        decision_input = []
        for field in self.decisional_inputs:
            if field == 'messages':
                decision_input = state.get('messages', [])[:]
            else:
                if len(additional_info) == 0:
                    additional_info = """### Additoinal info: """
                additional_info += "{field}: {value}\n".format(field=field, value=state.get(field, ""))
        decision_input.append(HumanMessage(
            self.prompt.format(steps=self.steps, description=self.description, additional_info=additional_info)))
        completion = self.client.invoke(decision_input)
        result = clean_string(completion.content.strip())
        logger.info(f"Plan to transition to: {result}")
        if result not in self.steps or result == 'END':
            result = self.default_output
        dispatch_custom_event(
            "on_decision_edge", {"decisional_inputs": self.decisional_inputs, "state": state}, config=config
        )
        return result


class TransitionalEdge(Runnable):
    name = "TransitionalEdge"

    def __init__(self, next_step: str):
        self.next_step = next_step

    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: RunnableConfig, *args, **kwargs):
        logger.info(f'Transitioning to: {self.next_step}')
        dispatch_custom_event(
            "on_transitional_edge", {"next_step": self.next_step, "state": state}, config=config
        )
        return self.next_step if self.next_step != 'END' else END

class StateDefaultNode(Runnable):
    name = "StateDefaultNode"

    def __init__(self, default_vars: dict = {}):
        self.default_vars = default_vars

    def invoke(self, state: BaseStore, config: Optional[RunnableConfig] = None) -> dict:
        logger.info("Setting default state variables")
        result = {}
        for key, value in self.default_vars.items():
            if isinstance(value, dict) and 'value' in value:
                temp_value = value['value']
                try:
                    result[key] = ast.literal_eval(temp_value)
                except:
                    logger.debug("Unable to evaluate value, using as is")
                    result[key] = temp_value
        return result

class PrinterNode(Runnable):
    name = "PrinterNode"

    def __init__(self, text_pattern: str, formatting_enabled: bool = True):
        self.text = text_pattern
        self.formatting_enabled = formatting_enabled

    def invoke(self, state: BaseStore, config: Optional[RunnableConfig] = None) -> dict:
        logger.info(f"Printer Node - Current state variables: {state}")
        result = {}
        logger.debug(f"Initial text pattern: {self.text}")
        formatted_output = safe_format(self.text, state)
        logger.debug(f"Formatted output: {formatted_output}")
        result[PRINTER_NODE_RS] = formatted_output
        return result


class StateModifierNode(Runnable):
    name = "StateModifierNode"

    def __init__(self, template: str, variables_to_clean: Optional[list[str]] = None, 
                 input_variables: Optional[list[str]] = None, 
                 output_variables: Optional[list[str]] = None):
        self.template = template
        self.variables_to_clean = variables_to_clean or []
        self.input_variables = input_variables or ["messages"]
        self.output_variables = output_variables or []

    def invoke(self, state: Annotated[BaseStore, InjectedStore()], config: Optional[RunnableConfig] = None) -> dict:
        logger.info(f"Modifying state with template: {self.template}")

        # Collect input variables from state
        input_data = {}
        
        for var in self.input_variables:
            if var in state:
                input_data[var] = state.get(var)
        type_of_output = type(state.get(self.output_variables[0])) if self.output_variables else None
        # Render the template using Jinja
        import json
        import base64
        from jinja2 import Environment

        def from_json(value):
            """Convert JSON string to Python object"""
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse JSON value: {e}")
                return value
        
        def base64_to_string(value):
            """Convert base64 encoded string to regular string"""
            try:
                return base64.b64decode(value).decode('utf-8')
            except Exception as e:
                logger.warning(f"Failed to decode base64 value: {e}")
                return value
        
        def split_by_words(value, chunk_size=100):
            words = value.split()
            return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        
        def split_by_regex(value, pattern):
            """Splits the provided string using the specified regex pattern."""
            return re.split(pattern, value)

        env = Environment()
        env.filters['from_json'] = from_json
        env.filters['base64_to_string'] = base64_to_string
        env.filters['split_by_words'] = split_by_words
        env.filters['split_by_regex'] = split_by_regex

        template = env.from_string(self.template)
        rendered_message = template.render(**input_data)
        result = {}
        # Store the rendered message in the state or messages
        if len(self.output_variables) > 0:
            # Use the first output variable to store the rendered content
            output_var = self.output_variables[0]
            
            # Convert rendered_message to the appropriate type
            if type_of_output is not None:
                try:
                    if type_of_output == dict:
                        result[output_var] = json.loads(rendered_message) if isinstance(rendered_message, str) else dict(rendered_message)
                    elif type_of_output == list:
                        result[output_var] = json.loads(rendered_message) if isinstance(rendered_message, str) else list(rendered_message)
                    elif type_of_output == int:
                        result[output_var] = int(rendered_message)
                    elif type_of_output == float:
                        result[output_var] = float(rendered_message)
                    elif type_of_output == str:
                        result[output_var] = str(rendered_message)
                    elif type_of_output == bool:
                        if isinstance(rendered_message, str):
                            result[output_var] = rendered_message.lower() in ('true', '1', 'yes', 'on')
                        else:
                            result[output_var] = bool(rendered_message)
                    elif type_of_output == type(None):
                        result[output_var] = None
                    else:
                        # Fallback to string if type is not recognized
                        result[output_var] = str(rendered_message)
                except (ValueError, TypeError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to convert rendered_message to {type_of_output.__name__}: {e}. Using string fallback.")
                    result[output_var] = str(rendered_message)
            else:
                result[output_var] = rendered_message

        # Clean up specified variables (make them empty, not delete)
        
        for var in self.variables_to_clean:
            if var in state:
                # Empty the variable based on its type
                if isinstance(state[var], list):
                    result[var] = []
                elif isinstance(state[var], dict):
                    result[var] = {}
                elif isinstance(state[var], str):
                    result[var] = ""
                elif isinstance(state[var], (int, float)):
                    result[var] = 0
                elif state[var] is None:
                    pass
                else:
                    # For other types, set to None
                    result[var] = None
        logger.info(f"State modifier result: {result}")
        return result


def prepare_output_schema(lg_builder, memory, store, debug=False, interrupt_before=None, interrupt_after=None,
                          state_class=None, output_variables=None):
    # prepare output channels
    if interrupt_after is None:
        interrupt_after = []
    if interrupt_before is None:
        interrupt_before = []
    output_channels = (
        "__root__"
        if len(lg_builder.schemas[lg_builder.output]) == 1
           and "__root__" in lg_builder.schemas[lg_builder.output]
        else [
            key
            for key, val in lg_builder.schemas[lg_builder.output].items()
            if not is_managed_value(val)
        ]
    )
    stream_channels = (
        "__root__"
        if len(lg_builder.channels) == 1 and "__root__" in lg_builder.channels
        else [
            key for key, val in lg_builder.channels.items() if not is_managed_value(val)
        ]
    )

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
        schema_to_mapper=state_class,
        output_variables=output_variables
    )

    compiled.attach_node(START, None)
    for key, node in lg_builder.nodes.items():
        compiled.attach_node(key, node)

    for start, end in lg_builder.edges:
        compiled.attach_edge(start, end)

    for starts, end in lg_builder.waiting_edges:
        compiled.attach_edge(starts, end)

    for start, branches in lg_builder.branches.items():
        for name, branch in branches.items():
            compiled.attach_branch(start, name, branch)

    logger.info(compiled.get_graph().draw_mermaid())
    return compiled


def create_graph(
        client: Any,
        yaml_schema: str,
        tools: list[Union[BaseTool, CompiledStateGraph]],
        *args,
        memory: Optional[Any] = None,
        store: Optional[BaseStore] = None,
        debug: bool = False,
        for_subgraph: bool = False,
        **kwargs
):
    """ Create a message graph from a yaml schema """

    # For top-level graphs (not subgraphs), detect and flatten any subgraphs
    if not for_subgraph:
        flattened_yaml, additional_tools = detect_and_flatten_subgraphs(yaml_schema)
        # Add collected tools from subgraphs to the tools list
        tools = list(tools) + additional_tools
        # Use the flattened YAML for building the graph
        yaml_schema = flattened_yaml

    schema = yaml.safe_load(yaml_schema)
    logger.debug(f"Schema: {schema}")
    logger.debug(f"Tools: {tools}")
    logger.info(f"Tools: {[tool.name for tool in tools]}")
    state = schema.get('state', {})
    state_class = create_state(state)
    lg_builder = StateGraph(state_class)
    interrupt_before = [clean_string(every) for every in schema.get('interrupt_before', [])]
    interrupt_after = [clean_string(every) for every in schema.get('interrupt_after', [])]
    try:
        for node in schema['nodes']:
            node_type = node.get('type', 'function')
            node_id = clean_string(node['id'])
            toolkit_name = node.get('toolkit_name')
            tool_name = clean_string(node.get('tool', node_id))
            if toolkit_name:
                tool_name = f"{clean_string(toolkit_name)}{TOOLKIT_SPLITTER}{tool_name}"
            logger.info(f"Node: {node_id} : {node_type} - {tool_name}")
            if node_type in ['function', 'tool', 'loop', 'loop_from_tool', 'indexer', 'subgraph', 'pipeline', 'agent']:
                for tool in tools:
                    if tool.name == tool_name:
                        if node_type == 'function':
                            lg_builder.add_node(node_id, FunctionTool(
                                tool=tool, name=node_id, return_type='dict',
                                output_variables=node.get('output', []),
                                input_mapping=node.get('input_mapping',
                                                       {'messages': {'type': 'variable', 'value': 'messages'}}),
                                input_variables=node.get('input', ['messages'])))
                        elif node_type == 'agent':
                            input_params = node.get('input', ['messages'])
                            input_mapping = node.get('input_mapping',
                                                     {'messages': {'type': 'variable', 'value': 'messages'}})
                            output_vars = node.get('output', [])
                            lg_builder.add_node(node_id, FunctionTool(
                                client=client, tool=tool,
                                name=node_id, return_type='str',
                                output_variables=output_vars + ['messages'] if 'messages' not in output_vars else output_vars,
                                input_variables=input_params,
                                input_mapping= input_mapping
                            ))
                        elif node_type == 'subgraph' or node_type == 'pipeline':
                            # assign parent memory/store
                            # tool.checkpointer = memory
                            # tool.store = store
                            # wrap with mappings
                            pipeline_name = node.get('tool', None)
                            if not pipeline_name:
                                raise ValueError(
                                    "Subgraph must have a 'tool' node: add required tool to the subgraph node")
                            node_fn = SubgraphRunnable(
                                inner=tool.graph,
                                name=pipeline_name,
                                input_mapping=node.get('input_mapping', {}),
                                output_mapping=node.get('output_mapping', {}),
                            )
                            lg_builder.add_node(node_id, node_fn)
                            break  # skip legacy handling
                        elif node_type == 'tool':
                            lg_builder.add_node(node_id, ToolNode(
                                client=client, tool=tool,
                                name=node_id, return_type='dict',
                                output_variables=node.get('output', []),
                                input_variables=node.get('input', ['messages']),
                                structured_output=node.get('structured_output', False),
                                task=node.get('task')
                            ))
                        elif node_type == 'loop':
                            lg_builder.add_node(node_id, LoopNode(
                                client=client, tool=tool,
                                name=node_id, return_type='dict',
                                output_variables=node.get('output', []),
                                input_variables=node.get('input', ['messages']),
                                task=node.get('task', '')
                            ))
                        elif node_type == 'loop_from_tool':
                            loop_toolkit_name = node.get('loop_toolkit_name')
                            loop_tool_name = node.get('loop_tool')
                            if (loop_toolkit_name and loop_tool_name) or loop_tool_name:
                                loop_tool_name = f"{clean_string(loop_toolkit_name)}{TOOLKIT_SPLITTER}{loop_tool_name}" if loop_toolkit_name else clean_string(
                                    loop_tool_name)
                                for t in tools:
                                    if t.name == loop_tool_name:
                                        logger.debug(f"Loop tool discovered: {t}")
                                        lg_builder.add_node(node_id, LoopToolNode(
                                            client=client,
                                            name=node_id, return_type='dict',
                                            tool=tool, loop_tool=t,
                                            variables_mapping=node.get('variables_mapping', {}),
                                            output_variables=node.get('output', []),
                                            input_variables=node.get('input', ['messages']),
                                            structured_output=node.get('structured_output', False),
                                            task=node.get('task')
                                        ))
                                        break
                        elif node_type == 'indexer':
                            indexer_tool = None
                            indexer_tool_name = clean_string(node.get('indexer_tool', None))
                            for t in tools:
                                if t.name == indexer_tool_name:
                                    indexer_tool = t
                            logger.info(f"Indexer tool: {indexer_tool}")
                            lg_builder.add_node(node_id, IndexerNode(
                                client=client, tool=tool,
                                index_tool=indexer_tool,
                                input_mapping=node.get('input_mapping', {}),
                                name=node_id, return_type='dict',
                                chunking_tool=node.get('chunking_tool', None),
                                chunking_config=node.get('chunking_config', {}),
                                output_variables=node.get('output', []),
                                input_variables=node.get('input', ['messages']),
                                structured_output=node.get('structured_output', False)))
                        break
            elif node_type == 'code':
                from ..tools.sandbox import create_sandbox_tool
                sandbox_tool = create_sandbox_tool(stateful=False, allow_net=True,
                                                   alita_client=kwargs.get('alita_client', None))
                code_data = node.get('code', {'type': 'fixed', 'value': "return 'Code block is empty'"})
                lg_builder.add_node(node_id, FunctionTool(
                    tool=sandbox_tool, name=node['id'], return_type='dict',
                    output_variables=node.get('output', []),
                    input_mapping={'code': code_data},
                    input_variables=node.get('input', ['messages']),
                    structured_output=node.get('structured_output', False),
                    alita_client=kwargs.get('alita_client', None)
                ))
            elif node_type == 'llm':
                output_vars = node.get('output', [])
                output_vars_dict = {
                    var: get_type_hints(state_class).get(var, str).__name__
                    for var in output_vars
                }
                
                # Check if tools should be bound to this LLM node
                connected_tools = node.get('tool_names', {})
                tool_names = []
                if isinstance(connected_tools, dict):
                    for toolkit, selected_tools in connected_tools.items():
                        for tool in selected_tools:
                            tool_names.append(f"{toolkit}{TOOLKIT_SPLITTER}{tool}")
                elif isinstance(connected_tools, list):
                    # for cases when tools are provided as a list of names with already bound toolkit_name
                    tool_names = connected_tools
                
                if tool_names:
                    # Filter tools by name
                    tool_dict = {tool.name: tool for tool in tools if isinstance(tool, BaseTool)}
                    available_tools = [tool_dict[name] for name in tool_names if name in tool_dict]
                    if len(available_tools) != len(tool_names):
                        missing_tools = [name for name in tool_names if name not in tool_dict]
                        logger.warning(f"Some tools not found for LLM node {node_id}: {missing_tools}")
                else:
                    # Use all available tools
                    available_tools = [tool for tool in tools if isinstance(tool, BaseTool)]

                lg_builder.add_node(node_id, LLMNode(
                    client=client,
                    input_mapping=node.get('input_mapping', {'messages': {'type': 'variable', 'value': 'messages'}}),
                    name=node_id,
                    return_type='dict',
                    structured_output_dict=output_vars_dict,
                    output_variables=output_vars,
                    input_variables=node.get('input', ['messages']),
                    structured_output=node.get('structured_output', False),
                    available_tools=available_tools,
                    tool_names=tool_names,
                    steps_limit=kwargs.get('steps_limit', 25)
                ))
            elif node_type == 'router':
                # Add a RouterNode as an independent node
                lg_builder.add_node(node_id, RouterNode(
                    name=node_id,
                    condition=node.get('condition', ''),
                    routes=node.get('routes', []),
                    default_output=node.get('default_output', 'END'),
                    input_variables=node.get('input', ['messages'])
                ))
                # Add a single conditional edge for all routes
                lg_builder.add_conditional_edges(
                    node_id,
                    ConditionalEdge(
                        condition="{{router_output}}",  # router node returns the route key in 'router_output'
                        condition_inputs=["router_output"],
                        conditional_outputs=node.get('routes', []),
                        default_output=node.get('default_output', 'END')
                    )
                )
            elif node_type == 'state_modifier':
                lg_builder.add_node(node_id, StateModifierNode(
                    template=node.get('template', ''),
                    variables_to_clean=node.get('variables_to_clean', []),
                    input_variables=node.get('input', ['messages']),
                    output_variables=node.get('output', [])
                ))
            elif node_type == 'printer':
                lg_builder.add_node(node_id, PrinterNode(
                    text_pattern=node.get('printer', ''),
                    formatting_enabled=node.get('formatting_enabled', True)
                ))

                # add interrupts after printer node if specified
                interrupt_after.append(clean_string(node_id))

                # reset printer output variable to avoid carrying over
                reset_node_id = f"{node_id}_reset"
                lg_builder.add_node(reset_node_id, PrinterNode(
                    text_pattern=''
                ))
                lg_builder.add_edge(node_id, reset_node_id)
                lg_builder.add_conditional_edges(reset_node_id, TransitionalEdge(clean_string(node['transition'])))
                continue
            if node.get('transition'):
                next_step = clean_string(node['transition'])
                logger.info(f'Adding transition: {next_step}')
                lg_builder.add_conditional_edges(node_id, TransitionalEdge(next_step))
            elif node.get('decision'):
                logger.info(f'Adding decision: {node["decision"]["nodes"]}')
                lg_builder.add_conditional_edges(node_id, DecisionEdge(
                    client, node['decision']['nodes'],
                    node['decision'].get('description', ""),
                    decisional_inputs=node['decision'].get('decisional_inputs', ['messages']),
                    default_output=node['decision'].get('default_output', 'END')))
            elif node.get('condition') and node_type != 'router':
                logger.info(f'Adding condition: {node["condition"]}')
                condition_input = node['condition'].get('condition_input', ['messages'])
                condition_definition = node['condition'].get('condition_definition', '')
                lg_builder.add_conditional_edges(node_id, ConditionalEdge(
                    condition=condition_definition, condition_inputs=condition_input,
                    conditional_outputs=node['condition'].get('conditional_outputs', []),
                    default_output=node['condition'].get('default_output', 'END')))

        # set default value for state variable at START
        try:
            entry_point = clean_string(schema['entry_point'])
        except KeyError:
            raise ToolException("Entry point is not defined in the schema. Please define 'entry_point' in the schema.")
        if state.items():
            state_default_node = StateDefaultNode(default_vars=set_defaults(state))
            lg_builder.add_node(state_default_node.name, state_default_node)
            lg_builder.set_entry_point(state_default_node.name)
            lg_builder.add_conditional_edges(state_default_node.name, TransitionalEdge(entry_point))
        else:
            # if no state variables are defined, set the entry point directly
            lg_builder.set_entry_point(entry_point)

        interrupt_before = interrupt_before or []
        interrupt_after = interrupt_after or []

        if not for_subgraph:
            # validate the graph for LangGraphAgentRunnable before the actual construction
            lg_builder.validate(
                interrupt=(
                    (interrupt_before if interrupt_before != "*" else []) + interrupt_after
                    if interrupt_after != "*"
                    else []
                )
            )

        # Compile into a CompiledStateGraph  for the subgraph
        graph = lg_builder.compile(
            checkpointer=True,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
            store=store,
            debug=debug,
        )
    except ValueError as e:
        raise ValueError(
            f"Validation of the schema failed. {e}\n\nDEBUG INFO:**Schema Nodes:**\n\n{lg_builder.nodes}\n\n**Schema Enges:**\n\n{lg_builder.edges}\n\n**Tools Available:**\n\n{tools}")
    # If building a nested subgraph, return the raw CompiledStateGraph
    if for_subgraph:
        return graph
    # Otherwise prepare top-level runnable wrapper and validate
    compiled = prepare_output_schema(
        lg_builder, memory, store, debug,
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after,
        state_class={state_class: None},
        output_variables=node.get('output', [])
    )
    return compiled.validate()

def set_defaults(d):
    """Set default values for dictionary entries based on their type."""
    type_defaults = {
        'str': '',
        'list': [],
        'dict': {},
        'int': 0,
        'float': 0.0,
        'bool': False,
        # add more types as needed
    }
    # Build state_types mapping with STRING type names (not actual type objects)
    state_types = {}

    for k, v in d.items():
        # Skip 'input' key as it is not a state initial variable
        if k == 'input':
            continue
        # set value or default if type is defined
        if 'value' not in v:
            v['value'] = type_defaults.get(v['type'], None)

        # Also build the state_types mapping with STRING type names
        var_type = v['type'] if isinstance(v, dict) else v
        if var_type in ['str', 'int', 'float', 'bool', 'list', 'dict', 'number']:
            # Store the string type name, not the actual type object
            state_types[k] = var_type if var_type != 'number' else 'int'

    # Add state_types as a default value that will be set at initialization
    # Use string type names to avoid serialization issues
    d['state_types'] = {'type': 'dict', 'value': state_types}
    return d

def convert_dict_to_message(msg_dict):
    """Convert a dictionary message to a LangChain message object."""
    if isinstance(msg_dict, BaseMessage):
        return msg_dict  # Already a LangChain message
    
    if isinstance(msg_dict, dict):
        role = msg_dict.get('role', 'user')
        content = msg_dict.get('content', '')
        
        if role == 'user':
            return HumanMessage(content=content)
        elif role == 'assistant':
            return AIMessage(content=content)
        elif role == 'system':
            return SystemMessage(content=content)
        else:
            # Default to HumanMessage for unknown roles
            return HumanMessage(content=content)
    
    # If it's neither dict nor BaseMessage, convert to string and make HumanMessage
    return HumanMessage(content=str(msg_dict))


class LangGraphAgentRunnable(CompiledStateGraph):
    def __init__(self, *args, output_variables=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_variables = output_variables

    def invoke(self, input: Union[dict[str, Any], Any],
               config: Optional[RunnableConfig] = None,
               *args, **kwargs):
        logger.info(f"Incoming Input: {input}")
        if config is None:
            config = RunnableConfig()
        if not config.get("configurable", {}).get("thread_id", ""):
            config["configurable"] = {"thread_id": str(uuid4())}
        thread_id = config.get("configurable", {}).get("thread_id")
        # Handle chat history and current input properly
        if input.get('chat_history') and not input.get('messages'):
            # Convert chat history dict messages to LangChain message objects
            chat_history = input.pop('chat_history')
            input['messages'] = [convert_dict_to_message(msg) for msg in chat_history]

        # handler for LLM node: if no input (Chat perspective), then take last human message
        if not input.get('input'):
            if input.get('messages'):
                input['input'] = [next((msg for msg in reversed(input['messages']) if isinstance(msg, HumanMessage)),
                                          None)]

        # Append current input to existing messages instead of overwriting
        if input.get('input'):
            if isinstance(input['input'], str):
                current_message = input['input']
            else:
                current_message = input.get('input')[-1]

            # TODO: add handler after we add 2+ inputs (filterByType, etc.)
            if isinstance(current_message, HumanMessage):
                current_content = current_message.content
                if isinstance(current_content, list):
                    text_contents = [
                        item['text'] if isinstance(item, dict) and item.get('type') == 'text'
                        else item if isinstance(item, str)
                        else None
                        for item in current_content
                    ]
                    text_contents = [text for text in text_contents if text is not None]
                    input['input'] = ". ".join(text_contents)
                elif isinstance(current_content, str):
                    # on regenerate case
                    input['input'] = current_content
                else:
                    input['input'] = str(current_content)
            elif isinstance(current_message, str):
                input['input'] = current_message
            else:
                input['input'] = str(current_message)
            if input.get('messages'):
                # Ensure existing messages are LangChain objects
                input['messages'] = [convert_dict_to_message(msg) for msg in input['messages']]
                # Append to existing messages
                # input['messages'].append(current_message)
            else:
                # No existing messages, create new list
                input['messages'] = [current_message]
        logging.info(f"Input: {thread_id} - {input}")
        if self.checkpointer and self.checkpointer.get_tuple(config):
            self.update_state(config, input)
            result = super().invoke(None, config=config, *args, **kwargs)
        else:
            result = super().invoke(input, config=config, *args, **kwargs)
        try:
            if not result.get(PRINTER_NODE_RS):
                output = next((msg.content for msg in reversed(result['messages']) if not isinstance(msg, HumanMessage)),
                              result['messages'][-1].content)
            else:
                # used for printer node output - it will be reset by next `reset` node
                output = result.get(PRINTER_NODE_RS)
        except:
            output = list(result.values())[-1]
        config_state = self.get_state(config)
        is_execution_finished = not config_state.next
        if is_execution_finished:
            thread_id = None

        result_with_state = {
            "output": output,
            "thread_id": thread_id,
            "execution_finished": is_execution_finished
        }

        # Include all state values in the result
        if hasattr(config_state, 'values') and config_state.values:
            for key, value in config_state.values.items():
                result_with_state[key] = value

        return result_with_state

def merge_subgraphs(parent_yaml: str, registry: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge subgraphs into parent graph by flattening YAML structures.

    This function implements the complete flattening approach:
    1. Parse parent YAML
    2. Detect subgraph nodes
    3. Recursively flatten subgraphs
    4. Merge states, nodes, interrupts, and transitions
    5. Return single unified graph definition

    Args:
        parent_yaml: YAML string of parent graph
        registry: Global subgraph registry

    Returns:
        Dict containing flattened graph definition
    """
    import copy

    # Parse parent YAML
    parent_def = yaml.safe_load(parent_yaml)

    # Check if already flattened (prevent infinite recursion)
    if parent_def.get('_flattened', False):
        return parent_def

    # Find subgraph nodes in parent
    subgraph_nodes = []
    regular_nodes = []

    for node in parent_def.get('nodes', []):
        if node.get('type') == 'subgraph' or node.get('type') == 'pipeline':
            subgraph_nodes.append(node)
        else:
            regular_nodes.append(node)

    # If no subgraphs, return as-is
    if not subgraph_nodes:
        parent_def['_flattened'] = True
        return parent_def

    # Start with parent state and merge subgraph states
    merged_state = copy.deepcopy(parent_def.get('state', {}))
    merged_nodes = copy.deepcopy(regular_nodes)
    merged_interrupts_before = set(parent_def.get('interrupt_before', []))
    merged_interrupts_after = set(parent_def.get('interrupt_after', []))
    all_tools = []

    # Track node remapping for transition rewiring
    node_mapping = {}  # subgraph_node_id -> actual_internal_node_id

    # Process each subgraph
    for subgraph_node in subgraph_nodes:
        # Support both 'tool' and 'subgraph' fields for subgraph name
        subgraph_name = subgraph_node.get('tool') or subgraph_node.get('subgraph')
        subgraph_node_id = subgraph_node['id']

        if subgraph_name not in registry:
            logger.warning(f"Subgraph '{subgraph_name}' not found in registry")
            continue

        # Get subgraph definition
        subgraph_entry = registry[subgraph_name]
        subgraph_yaml = subgraph_entry['yaml']
        subgraph_tools = subgraph_entry.get('tools', [])

        # Recursively flatten the subgraph (in case it has nested subgraphs)
        subgraph_def = merge_subgraphs(subgraph_yaml, registry)

        # Collect tools from subgraph
        all_tools.extend(subgraph_tools)

        # Merge state (union of all fields)
        for field_name, field_type in subgraph_def.get('state', {}).items():
            if field_name not in merged_state:
                merged_state[field_name] = field_type
            elif merged_state[field_name] != field_type:
                logger.warning(f"State field '{field_name}' type mismatch: {merged_state[field_name]} vs {field_type}")

        # Map subgraph node to its entry point
        subgraph_entry_point = subgraph_def.get('entry_point')
        if subgraph_entry_point:
            node_mapping[subgraph_node_id] = subgraph_entry_point
            logger.debug(f"Mapped subgraph node '{subgraph_node_id}' to entry point '{subgraph_entry_point}'")

        # Add subgraph nodes without prefixing (keep original IDs)
        for sub_node in subgraph_def.get('nodes', []):
            # Keep original node ID - no prefixing
            new_node = copy.deepcopy(sub_node)
            merged_nodes.append(new_node)

        # Handle the original subgraph node's transition - apply it to nodes that end with END
        original_transition = subgraph_node.get('transition')
        if original_transition and original_transition != 'END' and original_transition != END:
            # Find nodes in this subgraph that have END transitions and update them
            for node in merged_nodes:
                # Check if this is a node from the current subgraph by checking if it was just added
                # and has an END transition
                if node.get('transition') == 'END' and node in subgraph_def.get('nodes', []):
                    node['transition'] = original_transition

        # Merge interrupts without prefixing (keep original names)
        for interrupt in subgraph_def.get('interrupt_before', []):
            merged_interrupts_before.add(interrupt)  # No prefixing
        for interrupt in subgraph_def.get('interrupt_after', []):
            merged_interrupts_after.add(interrupt)  # No prefixing

    # Handle entry point - keep parent's unless it's a subgraph node
    entry_point = parent_def.get('entry_point')
    logger.debug(f"Original entry point: {entry_point}")
    logger.debug(f"Node mapping: {node_mapping}")
    if entry_point in node_mapping:
        # Parent entry point is a subgraph, redirect to subgraph's entry point
        old_entry_point = entry_point
        entry_point = node_mapping[entry_point]
        logger.debug(f"Entry point changed from {old_entry_point} to {entry_point}")
    else:
        logger.debug(f"Entry point {entry_point} not in node mapping, keeping as-is")

    # Rewrite transitions in regular nodes that point to subgraph nodes
    for node in merged_nodes:
        # Handle direct transitions
        if 'transition' in node:
            transition = node['transition']
            if transition in node_mapping:
                node['transition'] = node_mapping[transition]

        # Handle conditional transitions
        if 'condition' in node:
            condition = node['condition']
            if 'conditional_outputs' in condition:
                new_outputs = []
                for output in condition['conditional_outputs']:
                    if output in node_mapping:
                        new_outputs.append(node_mapping[output])
                    else:
                        new_outputs.append(output)
                condition['conditional_outputs'] = new_outputs

            if 'default_output' in condition:
                default = condition['default_output']
                if default in node_mapping:
                    condition['default_output'] = node_mapping[default]

            # Update condition_definition Jinja2 template to replace subgraph node references
            if 'condition_definition' in condition:
                condition_definition = condition['condition_definition']
                # Replace subgraph node references in the Jinja2 template
                for subgraph_node_id, subgraph_entry_point in node_mapping.items():
                    condition_definition = condition_definition.replace(subgraph_node_id, subgraph_entry_point)
                condition['condition_definition'] = condition_definition

        # Handle decision nodes
        if 'decision' in node:
            decision = node['decision']
            # Update decision.nodes list to replace subgraph node references
            if 'nodes' in decision:
                new_nodes = []
                for decision_node in decision['nodes']:
                    if decision_node in node_mapping:
                        new_nodes.append(node_mapping[decision_node])
                    else:
                        new_nodes.append(decision_node)
                decision['nodes'] = new_nodes

            # Update decision.default_output to replace subgraph node references
            if 'default_output' in decision:
                default_output = decision['default_output']
                if default_output in node_mapping:
                    decision['default_output'] = node_mapping[default_output]

    # Build final flattened definition
    flattened = {
        'name': parent_def.get('name', 'FlattenedGraph'),
        'state': merged_state,
        'nodes': merged_nodes,
        'entry_point': entry_point,
        '_flattened': True,
        '_all_tools': all_tools  # Store tools for later collection
    }

    # Add interrupts if present
    if merged_interrupts_before:
        flattened['interrupt_before'] = list(merged_interrupts_before)
    if merged_interrupts_after:
        flattened['interrupt_after'] = list(merged_interrupts_after)

    return flattened


def detect_and_flatten_subgraphs(yaml_schema: str) -> tuple[str, list]:
    """
    Detect subgraphs in YAML and flatten them if found.

    Returns:
        tuple: (flattened_yaml_string, collected_tools)
    """
    # Parse to check for subgraphs
    schema_dict = yaml.safe_load(yaml_schema)
    subgraph_nodes = [
        node for node in schema_dict.get('nodes', [])
        if node.get('type') == 'subgraph' or node.get('type') == 'pipeline'
    ]

    if not subgraph_nodes:
        return yaml_schema, []

    # Check if all required subgraphs are available in registry
    missing_subgraphs = []
    for node in subgraph_nodes:
        # Support both 'tool' and 'subgraph' fields for subgraph name
        # Don't clean the string - registry keys use original names
        subgraph_name = node.get('tool') or node.get('subgraph')
        if subgraph_name and subgraph_name not in SUBGRAPH_REGISTRY:
            missing_subgraphs.append(subgraph_name)

    if missing_subgraphs:
        logger.warning(f"Cannot flatten - missing subgraphs: {missing_subgraphs}")
        return yaml_schema, []

    # Flatten the graph
    flattened_def = merge_subgraphs(yaml_schema, SUBGRAPH_REGISTRY)

    # Extract tools
    all_tools = flattened_def.pop('_all_tools', [])

    # Convert back to YAML
    flattened_yaml = yaml.dump(flattened_def, default_flow_style=False)

    return flattened_yaml, all_tools

