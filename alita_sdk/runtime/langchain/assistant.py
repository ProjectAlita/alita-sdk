import logging
from datetime import datetime
from typing import Any, Optional

from jinja2 import Environment, DebugUndefined
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import BaseTool, ToolException

from .langraph_agent import create_graph
from .constants import (
    USER_ADDON, QA_ASSISTANT, NERDY_ASSISTANT, QUIRKY_ASSISTANT, CYNICAL_ASSISTANT,
    DEFAULT_ASSISTANT, PLAN_ADDON, PYODITE_ADDON, DATA_ANALYSIS_ADDON,
    SEARCH_INDEX_ADDON, FILE_HANDLING_INSTRUCTIONS
)
from ..middleware.base import Middleware, MiddlewareManager

logger = logging.getLogger(__name__)

# Canonical app_type values (imported from clients.client for reference)
APP_TYPE_AGENT = "agent"      # Standard LangGraph react agent with tools
APP_TYPE_PIPELINE = "pipeline"  # Graph-based workflow agent
APP_TYPE_PREDICT = "predict"    # Special agent without memory store


class Assistant:
    def __init__(self,
                 alita: 'AlitaClient',
                 data: dict,
                 client: 'LLMLikeObject',
                 chat_history: list[BaseMessage] = [],
                 app_type: str = APP_TYPE_AGENT,
                 tools: Optional[list] = [],
                 memory: Optional[Any] = None,
                 store: Optional[BaseStore] = None,
                 debug_mode: Optional[bool] = False,
                 mcp_tokens: Optional[dict] = None,
                 conversation_id: Optional[str] = None,
                 ignored_mcp_servers: Optional[list] = None,
                 persona: Optional[str] = "generic",
                 is_subgraph: bool = False,
                 lazy_tools_mode: Optional[bool] = None,
                 middleware: Optional[list[Middleware]] = None):

        self.app_type = app_type
        self.memory = memory
        self.store = store
        self.persona = persona
        self.max_iterations = data.get('meta', {}).get('step_limit', 25)
        self.is_subgraph = is_subgraph  # Store is_subgraph flag

        # Current participant ID - used for self-filtering in tools
        self.current_participant_id = data.get('current_participant_id')

        # Swarm mode - enables multi-agent collaboration with shared message history
        # Check both conversation-level internal_tools and agent version meta internal_tools
        conversation_internal_tools = data.get('internal_tools', [])
        version_internal_tools = data.get('meta', {}).get('internal_tools', [])
        self.swarm_mode = 'swarm' in conversation_internal_tools or 'swarm' in version_internal_tools

        # Lazy tools mode - reduces token usage by using meta-tools instead of binding all tools
        # Can be set via: 1) constructor param, 2) data['meta']['lazy_tools_mode'], 3) default False
        if lazy_tools_mode is not None:
            self.lazy_tools_mode = lazy_tools_mode
        else:
            self.lazy_tools_mode = data.get('meta', {}).get('lazy_tools_mode', False)

        logger.debug("Data for agent creation: %s", data)
        logger.info("App type: %s", app_type)

        self.alita_client = alita
        self.client = client
        # For predict agents, use the client as-is since it's already configured
        # if app_type == "predict":
        #     self.client = client
        # else:
        #     # For other agent types, configure client from llm_settings
        #     self.client = copy(client)
        #     self.client.max_tokens = data['llm_settings']['max_tokens']
        #     self.client.temperature = data['llm_settings']['temperature']
        #     self.client.top_p = data['llm_settings']['top_p']
        #     self.client.top_k = data['llm_settings']['top_k']
        #     self.client.model_name = data['llm_settings']['model_name']
        #     self.client.integration_uid = data['llm_settings']['integration_uid']

        #     model_type = data["llm_settings"]["indexer_config"]["ai_model"]
        #     model_params = data["llm_settings"]["indexer_config"]["ai_model_params"]
        #     #
        #     target_pkg, target_name = model_type.rsplit(".", 1)
        #     target_cls = getattr(
        #         importlib.import_module(target_pkg),
        #         target_name
        #     )
        #     self.client = target_cls(**model_params)
        # validate agents compatibility: non-pipeline agents cannot have pipelines as toolkits
        # if app_type not in ["pipeline", "predict"]:
        #     tools_to_check = data.get('tools', [])
        #     if any(tool['agent_type'] == 'pipeline' for tool in tools_to_check):
        #         raise ToolException("Non-pipeline agents cannot have pipelines as a toolkits. "
        #                             "Review toolkits configuration or use pipeline as master agent.")

        # configure memory store if memory tool is defined (not needed for predict agents)
        if app_type != APP_TYPE_PREDICT:
            memory_tool = next((tool for tool in data.get('tools', []) if tool['type'] == 'memory'), None)
            self._configure_store(memory_tool)
        else:
            # For predict agents, initialize memory store to None since they don't use memory
            self.store = None

        # Lazy import to avoid circular dependency
        from ..toolkits.tools import get_tools
        version_tools = data['tools']
        # Handle internal tools
        meta = data.get('meta', {})
        if meta.get("internal_tools"):
            # Find bucket from artifact toolkit marked with is_attachment flag
            bucket_name = None
            for tool in version_tools:
                if tool.get('type') == 'artifact' and tool.get('is_attachment'):
                    bucket_name = tool.get('settings', {}).get('bucket')
                    break
            # Fallback: use first artifact toolkit with a bucket
            if not bucket_name:
                for tool in version_tools:
                    if tool.get('type') == 'artifact' and tool.get('settings', {}).get('bucket'):
                        bucket_name = tool['settings']['bucket']
                        break

            for internal_tool_name in meta.get("internal_tools"):
                tool_config = {"type": "internal_tool", "name": internal_tool_name, "settings": {}}
                if bucket_name:
                    tool_config["settings"]["bucket_name"] = bucket_name
                version_tools.append(tool_config)

        self.tools = get_tools(
            version_tools,
            alita_client=alita,
            llm=self.client,
            memory_store=self.store,
            debug_mode=debug_mode,
            mcp_tokens=mcp_tokens,
            conversation_id=conversation_id,
            ignored_mcp_servers=ignored_mcp_servers,
            current_participant_id=self.current_participant_id
        )
        if tools:
            self.tools += tools

        # Initialize middleware manager and add middleware tools
        # Middleware tools are tracked separately as "always-bind" tools
        # In lazy_tools_mode, these are bound directly to LLM (not via ToolRegistry)
        self.middleware_manager = MiddlewareManager()
        self._middleware_prompt = ""
        self._always_bind_tools = []  # Tools to always bind directly (not via ToolRegistry)
        if middleware:
            for mw in middleware:
                self.middleware_manager.add(mw)
            # Get tools from all middleware - these are always-bind tools
            middleware_tools = self.middleware_manager.get_all_tools()
            if middleware_tools:
                # Store middleware tools separately for always-bind behavior
                self._always_bind_tools = list(middleware_tools)
                # Also add to main tools list for non-lazy mode and tool availability
                self.tools += middleware_tools
                logger.info(f"Added {len(middleware_tools)} middleware tools (always-bind in lazy mode)")
            # Get combined system prompt from middleware
            self._middleware_prompt = self.middleware_manager.get_combined_prompt()
            # Notify middleware of conversation start
            if conversation_id:
                context_messages = self.middleware_manager.start_conversation(conversation_id)
                if context_messages:
                    logger.info(f"Middleware context: {context_messages}")

        # In lazy tools mode, don't rename tools - ToolRegistry handles namespacing by toolkit
        # Only add suffixes in non-lazy mode where tools are bound directly to LLM
        if not self.lazy_tools_mode:
            tool_name_counts = {}
            for tool in self.tools:
                if hasattr(tool, 'name'):
                    base_name = tool.name
                    if base_name in tool_name_counts:
                        tool_name_counts[base_name] += 1
                        new_name = f"{base_name}_{tool_name_counts[base_name]}"
                        tool.name = new_name
                        logger.info(f"Tool name collision (non-lazy mode): '{base_name}' -> '{new_name}'")
                    else:
                        tool_name_counts[base_name] = 0

        logger.info(f"Tools initialized: {len(self.tools)} tools (lazy_mode={self.lazy_tools_mode})")

        # All supported agent types (agent, pipeline, predict) use instructions directly
        # LangGraph handles message construction internally
        self.prompt = data['instructions']

        # Store variables for Jinja2 template resolution
        # Variables come from data['variables'] (list of {name, value} dicts from API)
        # These are merged with application_variables in client.application() before reaching here
        self.prompt_variables = {}
        variables_list = data.get('variables', [])
        if variables_list:
            for var in variables_list:
                if isinstance(var, dict) and var.get('name'):
                    # Capture variables with non-empty values (empty values are runtime placeholders)
                    value = var.get('value')
                    if value is not None and value != '':
                        self.prompt_variables[var['name']] = value
            if self.prompt_variables:
                logger.info(f"Captured {len(self.prompt_variables)} Jinja2 variables: {list(self.prompt_variables.keys())}")

        # Also support variables from meta (dict format) for flexibility
        if meta.get('variables') and isinstance(meta['variables'], dict):
            self.prompt_variables.update(meta['variables'])
            logger.debug(f"Added meta variables: {list(meta['variables'].keys())}")

        try:
            logger.info(
                f"Client was created with client setting: temperature - {self.client._get_model_default_parameters}")
        except Exception:
            logger.info(
                f"Client was created with client setting: temperature - {self.client.temperature} : {self.client.max_tokens}")

    def _configure_store(self, memory_tool: dict | None) -> None:
        """
        Configure the memory store based on a memory_tool definition.
        Only creates a new store if one does not already exist.
        """
        if not memory_tool or self.store is not None:
            return
        from .store_manager import get_manager
        conn_str = memory_tool['settings'].get('pgvector_configuration', {}).get('connection_string', '')
        store = get_manager().get_store(conn_str)
        self.store = store

    def _resolve_jinja2_variables(self, template_str: str, extra_context: Optional[dict] = None) -> str:
        """
        Resolve Jinja2 variables in a template string.

        This method processes Jinja2 templates ({{variable}}) with available context.
        Uses DebugUndefined to leave unresolved variables as-is rather than failing.

        Available context variables:
        - current_date: Current date (YYYY-MM-DD)
        - current_time: Current time (HH:MM:SS)
        - current_datetime: Current datetime (YYYY-MM-DD HH:MM:SS)
        - Any variables from self.prompt_variables
        - Any variables passed via extra_context

        Args:
            template_str: String that may contain Jinja2 template variables
            extra_context: Optional dict of additional context variables

        Returns:
            String with resolved Jinja2 variables
        """
        if not template_str or '{{' not in template_str:
            # Fast path: no Jinja2 syntax detected
            return template_str

        try:
            # Build context with system variables
            now = datetime.now()
            context = {
                'current_date': now.strftime('%Y-%m-%d'),
                'current_time': now.strftime('%H:%M:%S'),
                'current_datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
            }

            # Add variables from prompt configuration
            if hasattr(self, 'prompt_variables') and self.prompt_variables:
                context.update(self.prompt_variables)

            # Add any extra context
            if extra_context:
                context.update(extra_context)

            # Process template with Jinja2
            # DebugUndefined leaves unresolved variables as {{variable}} rather than failing
            environment = Environment(undefined=DebugUndefined)
            template = environment.from_string(template_str)
            resolved = template.render(context)

            logger.debug(f"Jinja2 template resolved with context keys: {list(context.keys())}")
            return resolved

        except Exception as e:
            logger.warning(f"Failed to resolve Jinja2 variables in template: {e}")
            return template_str

    def runnable(self):
        """
        Create and return the appropriate agent based on app_type.

        Supported app_types:
        - 'pipeline': Graph-based workflow agent
        - 'agent', 'predict': LangGraph react agent with tool calling
        """
        if self.app_type == APP_TYPE_PIPELINE:
            return self.pipeline()
        elif self.app_type in [APP_TYPE_AGENT, APP_TYPE_PREDICT]:
            return self.getLangGraphReactAgent()
        else:
            # Unsupported app_type - fall back to agent
            logger.warning(f"Unsupported app_type '{self.app_type}', falling back to LangGraph agent")
            return self.getLangGraphReactAgent()

    def getLangGraphReactAgent(self):
        """
        Create a LangGraph react agent using a tool-calling agent pattern.
        This creates a proper LangGraphAgentRunnable with modern tool support.

        If swarm_mode is enabled and there are agent tools (Application tools),
        creates a swarm-style multi-agent system where all agents share message history.
        """
        # Exclude compiled graph runnables from simple tool agents
        simple_tools = [t for t in self.tools if isinstance(t, (BaseTool, CompiledStateGraph))]

        # Check if swarm mode should be used
        if self.swarm_mode:
            # Separate agent tools from regular tools
            agent_tools = [t for t in simple_tools if self._is_agent_tool(t)]
            if agent_tools:
                logger.info(f"Swarm mode enabled with {len(agent_tools)} child agents")
                return self._create_swarm_agent(simple_tools, agent_tools)
            else:
                logger.info("Swarm mode enabled but no agent tools found, using standard agent")

        # Set up memory/checkpointer if available
        checkpointer = None
        if self.memory is not None:
            checkpointer = self.memory
        elif self.store is not None:
            # Convert store to checkpointer if needed
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
        else:
            # Ensure we have a checkpointer for conversation persistence
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
            logger.info("Using default MemorySaver for conversation persistence")

        # Resolve Jinja2 variables in prompt instructions
        # Variables from data['variables'] (via get_app_version_details API) and system variables are processed here
        prompt_instructions = self._resolve_jinja2_variables(self.prompt)
        if prompt_instructions != self.prompt:
            logger.info(f"Jinja2 variables resolved in prompt (changed from {len(self.prompt)} to {len(prompt_instructions)} chars)")

        # Add tool binding only if tools are present
        tool_names = []
        if simple_tools:
            tool_names = [tool.name for tool in simple_tools]
            if self.lazy_tools_mode:
                logger.info(f"Available tools: {len(tool_names)} (lazy mode - will use meta-tools)")
            else:
                logger.info("Binding tools: %s", tool_names)

        user_addon = USER_ADDON.format(prompt=str(prompt_instructions)) if prompt_instructions else ""
        # Check for planning tools (any of them indicates planning capability)
        has_planning_tools = any(t in tool_names for t in ['update_plan', 'start_step', 'complete_step'])
        # Use middleware prompt if available, otherwise fall back to PLAN_ADDON
        plan_addon = self._middleware_prompt if self._middleware_prompt else (PLAN_ADDON if has_planning_tools else "")
        data_analysis_addon = DATA_ANALYSIS_ADDON if 'pandas_analyze_data' in tool_names else ""
        pyodite_addon = PYODITE_ADDON if 'pyodide_sandbox' in tool_names else ""
        search_index_addon = SEARCH_INDEX_ADDON if 'stepback_summary_index' in tool_names else ""

        # Select assistant template based on persona
        persona_templates = {
            "qa": QA_ASSISTANT,
            "nerdy": NERDY_ASSISTANT,
            "quirky": QUIRKY_ASSISTANT,
            "cynical": CYNICAL_ASSISTANT,
        }

        # For agent/predict types, use instructions directly without wrapping
        # Persona templates (DEFAULT_ASSISTANT, etc.) are only used when persona is specified
        if self.app_type in [APP_TYPE_AGENT, APP_TYPE_PREDICT] and prompt_instructions:
            # Use agent's own instructions as the base system prompt
            # Append addons only when their corresponding tools are present
            addons = "\n\n---\n\n".join(filter(None, [
                plan_addon,
                search_index_addon,
                FILE_HANDLING_INSTRUCTIONS if simple_tools else "",
                pyodite_addon,
                data_analysis_addon
            ]))
            escaped_prompt = f"{prompt_instructions}\n\n---\n\n{addons}" if addons else str(prompt_instructions)
            logger.info(f"Using agent's own instructions directly (app_type={self.app_type})")
        else:
            # Fallback to persona-based template wrapping
            base_assistant = persona_templates.get(self.persona, DEFAULT_ASSISTANT)
            escaped_prompt = base_assistant.format(
                users_instructions=user_addon,
                planning_instructions=plan_addon,
                pyodite_addon=pyodite_addon,
                data_analysis_addon=data_analysis_addon,
                search_index_addon=search_index_addon,
                file_handling_instructions=FILE_HANDLING_INSTRUCTIONS
            )

        # Properly setup the prompt for YAML
        import yaml

        # Create the schema as a dictionary first, then convert to YAML
        state_messages_config = {'type': 'list'}
        
        schema_dict = {
            'name': 'react_agent',
            'state': {
                'input': {
                    'type': 'str'
                },
                'messages': state_messages_config
            },
            'nodes': [{
                'id': 'agent',
                'type': 'llm',
                'prompt': {
                    'template': escaped_prompt
                },
                'input_mapping': {
                    'system': {
                        'type': 'fixed',
                        'value': escaped_prompt
                    },
                    'task': {
                        'type': 'variable',
                        'value': 'input'
                    },
                    'chat_history': {
                        'type': 'variable',
                        'value': 'messages'
                    }
                },
                'step_limit': self.max_iterations,
                'input': ['messages'],
                'output': ['messages'],
                'transition': 'END'
            }],
            'entry_point': 'agent'
        }
        
        # Add tool-specific parameters only if tools exist and NOT in lazy mode
        # In lazy mode, we don't bind tool_names so the LLMNode uses meta-tools instead
        if simple_tools and not self.lazy_tools_mode:
            schema_dict['nodes'][0]['tool_names'] = tool_names
        
        # Convert to YAML string
        yaml_schema = yaml.dump(schema_dict, default_flow_style=False, allow_unicode=True)
        
        # Use create_graph function to build the agent like other graph types
        from .langraph_agent import create_graph
    
        agent = create_graph(
            client=self.client,
            yaml_schema=yaml_schema,
            tools=simple_tools,
            memory=checkpointer,
            store=self.store,
            debug=False,
            for_subgraph=False,
            lazy_tools_mode=self.lazy_tools_mode,
            alita_client=self.alita_client,
            steps_limit=self.max_iterations,
            always_bind_tools=self._always_bind_tools  # Middleware tools always bound directly
        )

        return agent

    def pipeline(self):
        memory = self.memory
        #
        if memory is None:
            from langgraph.checkpoint.memory import MemorySaver  # pylint: disable=E0401,C0415
            memory = MemorySaver()
        #
        agent = create_graph(
            client=self.client, tools=self.tools,
            yaml_schema=self.prompt, memory=memory,
            alita_client=self.alita_client,
            steps_limit=self.max_iterations,
            for_subgraph=self.is_subgraph,  # Pass for_subgraph flag to filter PrinterNodes
            lazy_tools_mode=self.lazy_tools_mode,
            always_bind_tools=self._always_bind_tools  # Middleware tools always bound directly
        )
        #
        return agent

    def _is_agent_tool(self, tool: BaseTool) -> bool:
        """
        Check if a tool is an Application tool (represents a child agent).

        Application tools wrap other agents/pipelines and can be identified by:
        - Being an instance of the Application class
        - Having an 'application' attribute (the wrapped runnable)
        """
        from ..tools.application import Application
        if isinstance(tool, Application):
            return True
        # Fallback: check for application attribute
        if hasattr(tool, 'application') and tool.application is not None:
            return True
        return False

    def _build_swarm_compatible_agent(self, model, tools: list, prompt: str, agent_name: str):
        """
        Build a react agent compatible with langgraph-swarm.

        This is a workaround for langgraph version incompatibility where
        create_react_agent uses 'input_schema' parameter but StateGraph.add_node
        only accepts 'input'. We build the agent manually using StateGraph API.

        Args:
            model: The LLM client
            tools: List of tools for this agent
            prompt: System prompt for the agent
            agent_name: Name for the compiled agent

        Returns:
            CompiledStateGraph with proper name for swarm integration
        """
        from typing import Annotated, TypedDict
        from langchain_core.messages import AIMessage
        from langgraph.graph import StateGraph, END, MessagesState
        from langgraph.prebuilt import ToolNode

        # Bind tools to model
        if tools:
            model_with_tools = model.bind_tools(tools)
        else:
            model_with_tools = model

        # Define agent node that calls the model
        def call_model(state: MessagesState):
            messages = state["messages"]
            # Prepend system message with prompt
            system_msg = SystemMessage(content=prompt)
            response = model_with_tools.invoke([system_msg] + list(messages))
            return {"messages": [response]}

        # Define routing logic
        def should_continue(state: MessagesState):
            messages = state["messages"]
            last_message = messages[-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"
            return END

        # Build the graph using MessagesState (compatible with swarm)
        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", call_model)
        if tools:
            workflow.add_node("tools", ToolNode(tools))

        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue)
        if tools:
            workflow.add_edge("tools", "agent")

        # Compile with name - this is what swarm uses to identify agents
        return workflow.compile(name=agent_name)

    def _create_swarm_agent(self, all_tools: list, agent_tools: list):
        """
        Create a swarm-style multi-agent system where all child agents share message history.

        This implementation manually builds the swarm using StateGraph to avoid
        version incompatibilities with langgraph_swarm's create_swarm function.

        Architecture:
        - Parent agent is the default entry point
        - Child agents are accessible via handoff tools
        - All agents share the same message history via SwarmState
        - Control flows between agents based on handoffs

        Args:
            all_tools: All tools including agent tools
            agent_tools: Subset of tools that are Application (child agent) tools
        """
        from typing import Literal, Optional, Annotated
        from langchain_core.messages import AIMessage, ToolMessage
        from langchain_core.tools import StructuredTool
        from langgraph.graph import StateGraph, END, START, MessagesState
        from langgraph.prebuilt import ToolNode
        from langgraph.checkpoint.memory import MemorySaver

        # For swarm mode, always use a fresh MemorySaver to avoid corrupted state
        # from previous failed runs. The message history is passed via invoke(),
        # so we don't need to persist across invocations.
        checkpointer = MemorySaver()
        logger.info("[SWARM] Using fresh MemorySaver for swarm mode (avoiding shared memory corruption)")

        # Separate regular tools from agent tools
        regular_tools = [t for t in all_tools if t not in agent_tools]

        # Resolve prompt
        prompt_instructions = self._resolve_jinja2_variables(self.prompt)

        # Build agent name list for type hints
        agent_names = ["parent"] + [t.name for t in agent_tools]

        # Create SwarmState class with active_agent tracking
        class SwarmState(MessagesState):
            """State schema for the multi-agent swarm."""
            active_agent: Optional[str] = None

        # Create simple handoff tools that return messages instead of Command objects
        def create_simple_handoff_tool(target_agent: str, description: str):
            """Create a simple handoff tool that returns a string message."""
            def handoff_func() -> str:
                return f"Successfully transferred to {target_agent}"

            return StructuredTool.from_function(
                func=handoff_func,
                name=f"transfer_to_{target_agent}",
                description=description
            )

        # Create handoff tools for each child agent
        parent_handoff_tools = []
        child_agent_descriptions = []

        # Handoff tool to return to parent
        handoff_to_parent = create_simple_handoff_tool(
            "parent",
            "Hand control back to the main assistant when done with the specialized task"
        )

        child_configs = []  # Store child agent configurations

        for agent_tool in agent_tools:
            agent_name = agent_tool.name
            original_name = agent_tool.metadata.get('original_name', agent_name) if hasattr(agent_tool, 'metadata') else agent_name

            # Create handoff tool for parent to call this child
            handoff_tool_name = f"transfer_to_{agent_name}"
            handoff_to_child = create_simple_handoff_tool(
                agent_name,
                f"Hand off to {original_name}: {agent_tool.description}"
            )
            parent_handoff_tools.append(handoff_to_child)

            # Track child agent info
            child_agent_descriptions.append({
                'name': original_name,
                'handoff_tool': handoff_tool_name,
                'description': agent_tool.description
            })

            # Store child config for later node creation
            child_system_prompt = f"You are {original_name}. {agent_tool.description}\n\nComplete your task using the available tools. When done, use 'transfer_to_parent' to return control to the main assistant."
            child_configs.append({
                'name': agent_name,
                'tools': [agent_tool, handoff_to_parent],
                'prompt': child_system_prompt
            })

        # Build swarm instructions for the parent prompt
        swarm_prompt_addon = self._build_swarm_prompt_addon(child_agent_descriptions)
        enhanced_prompt = f"{prompt_instructions}\n\n{swarm_prompt_addon}"

        # Parent tools = regular tools + handoff tools to children
        parent_tools = regular_tools + parent_handoff_tools

        # Build the swarm StateGraph manually
        workflow = StateGraph(SwarmState)

        # Helper function to filter orphaned tool_use blocks from message history
        def filter_orphaned_tool_calls(messages: list) -> list:
            """
            Remove or fix orphaned tool_use blocks that don't have matching tool_result blocks.
            Anthropic requires every tool_use to have a corresponding tool_result immediately after.
            """
            if not messages:
                return messages

            # Collect all tool_call_ids that have corresponding ToolMessages
            tool_result_ids = set()
            for msg in messages:
                if isinstance(msg, ToolMessage):
                    if hasattr(msg, 'tool_call_id') and msg.tool_call_id:
                        tool_result_ids.add(msg.tool_call_id)

            # Filter messages, removing AIMessages with orphaned tool_calls
            cleaned_messages = []
            for msg in messages:
                if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    # Check if all tool_calls have matching results
                    orphaned_calls = []
                    valid_calls = []
                    for tc in msg.tool_calls:
                        tc_id = tc.get('id', '')
                        if tc_id in tool_result_ids:
                            valid_calls.append(tc)
                        else:
                            orphaned_calls.append(tc)
                            logger.warning(f"[SWARM] Filtering orphaned tool_call: {tc_id}")

                    if orphaned_calls and not valid_calls:
                        # All tool_calls are orphaned - convert to plain AIMessage without tool_calls
                        if msg.content:
                            cleaned_msg = AIMessage(content=msg.content)
                            cleaned_messages.append(cleaned_msg)
                        # Skip if no content either
                    elif orphaned_calls:
                        # Some tool_calls are orphaned - create new message with only valid calls
                        cleaned_msg = AIMessage(content=msg.content, tool_calls=valid_calls)
                        cleaned_messages.append(cleaned_msg)
                    else:
                        # All tool_calls have matching results
                        cleaned_messages.append(msg)
                else:
                    cleaned_messages.append(msg)

            return cleaned_messages

        # Helper function to create agent node
        def make_agent_node(model, tools, prompt, agent_name):
            """Create an agent node function."""
            if tools:
                model_with_tools = model.bind_tools(tools)
            else:
                model_with_tools = model

            def agent_node(state: SwarmState):
                messages = state["messages"]
                # Filter out existing system messages to avoid "multiple non-consecutive system messages" error
                filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]
                # Filter orphaned tool_use blocks to avoid Anthropic API errors
                filtered_messages = filter_orphaned_tool_calls(filtered_messages)
                system_msg = SystemMessage(content=prompt)
                response = model_with_tools.invoke([system_msg] + filtered_messages)
                return {"messages": [response]}

            return agent_node

        # Helper to check for handoff in tool calls
        def get_handoff_destination(message: AIMessage) -> Optional[str]:
            """Check if the message contains a handoff tool call."""
            if not hasattr(message, 'tool_calls') or not message.tool_calls:
                return None
            for tool_call in message.tool_calls:
                tool_name = tool_call.get('name', '')
                if tool_name.startswith('transfer_to_'):
                    return tool_name.replace('transfer_to_', '')
            return None

        # Custom tool node that updates active_agent on handoff
        def make_tool_node_with_handoff(tools, agent_names_list):
            """Create a tool node that handles handoff state updates."""
            base_tool_node = ToolNode(tools)

            def tool_node_with_handoff(state: SwarmState):
                # Execute tools normally
                result = base_tool_node.invoke(state)

                # Check if there was a handoff in the last AI message
                messages = state.get("messages", [])
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage):
                        handoff_dest = get_handoff_destination(msg)
                        if handoff_dest and handoff_dest in agent_names_list:
                            # Update active_agent in the result
                            if isinstance(result, dict):
                                result["active_agent"] = handoff_dest
                            else:
                                result = {"messages": result.get("messages", []), "active_agent": handoff_dest}
                            logger.info(f"[SWARM] Handoff detected: transferring to {handoff_dest}")
                        break
                return result

            return tool_node_with_handoff

        # Add parent agent node
        parent_node = make_agent_node(self.client, parent_tools, enhanced_prompt, "parent")
        workflow.add_node("parent", parent_node)

        # Add parent tools node with handoff handling
        if parent_tools:
            workflow.add_node("parent_tools", make_tool_node_with_handoff(parent_tools, agent_names))

        # Add child agent nodes
        for config in child_configs:
            child_node = make_agent_node(self.client, config['tools'], config['prompt'], config['name'])
            workflow.add_node(config['name'], child_node)
            # Add child tools node with handoff handling
            if config['tools']:
                workflow.add_node(f"{config['name']}_tools", make_tool_node_with_handoff(config['tools'], agent_names))

        # Router function to route to active agent
        def route_to_active_agent(state: SwarmState) -> str:
            return state.get("active_agent", "parent") or "parent"

        # Routing logic after parent agent
        def route_after_parent(state: SwarmState) -> str:
            messages = state["messages"]
            if not messages:
                return END
            last_message = messages[-1]
            if isinstance(last_message, AIMessage):
                # Check for handoff
                handoff_dest = get_handoff_destination(last_message)
                if handoff_dest and handoff_dest != "parent":
                    return "parent_tools"  # Process handoff tool first
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    return "parent_tools"
            return END

        # Routing logic after parent tools
        def route_after_parent_tools(state: SwarmState) -> str:
            # Check active_agent first (set by handoff)
            active = state.get("active_agent")
            if active and active in agent_names and active != "parent":
                return active

            messages = state["messages"]
            if not messages:
                return "parent"
            # Check the last AI message for handoff
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    handoff_dest = get_handoff_destination(msg)
                    if handoff_dest and handoff_dest in agent_names:
                        return handoff_dest
                    break
            return "parent"

        # Add routing from START
        workflow.add_conditional_edges(START, route_to_active_agent, {name: name for name in agent_names})

        # Add routing after parent
        workflow.add_conditional_edges("parent", route_after_parent, {
            "parent_tools": "parent_tools",
            END: END
        })

        # Add routing after parent tools
        tool_routes = {name: name for name in agent_names}
        tool_routes["parent"] = "parent"
        workflow.add_conditional_edges("parent_tools", route_after_parent_tools, tool_routes)

        # Add routing for child agents
        for config in child_configs:
            child_name = config['name']

            def make_child_router(child_name):
                def route_after_child(state: SwarmState) -> str:
                    messages = state["messages"]
                    if not messages:
                        return END
                    last_message = messages[-1]
                    if isinstance(last_message, AIMessage):
                        handoff_dest = get_handoff_destination(last_message)
                        if handoff_dest:
                            return f"{child_name}_tools"
                        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                            return f"{child_name}_tools"
                    return END
                return route_after_child

            def make_child_tools_router(child_name, agent_names_list):
                def route_after_child_tools(state: SwarmState) -> str:
                    # Check active_agent first (set by handoff)
                    active = state.get("active_agent")
                    if active and active in agent_names_list and active != child_name:
                        return active

                    messages = state["messages"]
                    for msg in reversed(messages):
                        if isinstance(msg, AIMessage):
                            handoff_dest = get_handoff_destination(msg)
                            if handoff_dest and handoff_dest in agent_names_list:
                                return handoff_dest
                            break
                    return child_name
                return route_after_child_tools

            workflow.add_conditional_edges(child_name, make_child_router(child_name), {
                f"{child_name}_tools": f"{child_name}_tools",
                END: END
            })

            child_tool_routes = {name: name for name in agent_names}
            child_tool_routes[child_name] = child_name
            workflow.add_conditional_edges(f"{child_name}_tools", make_child_tools_router(child_name, agent_names), child_tool_routes)

        # Compile with checkpointer
        try:
            compiled = workflow.compile(checkpointer=checkpointer, store=self.store)
            logger.info(f"Created manual swarm agent with {len(agent_tools)} child agents: {[t.name for t in agent_tools]}")
            return compiled
        except Exception as e:
            logger.error(f"Failed to compile swarm: {type(e).__name__}: {e}", exc_info=True)
            raise

    def _build_swarm_prompt_addon(self, child_agents: list) -> str:
        """
        Build prompt instructions explaining available child agents for handoff.

        Args:
            child_agents: List of dicts with 'name', 'handoff_tool', 'description'

        Returns:
            Formatted string to append to the parent agent's prompt
        """
        if not child_agents:
            return ""

        lines = [
            "## Available Specialist Agents",
            "",
            "You can delegate tasks to the following specialist agents by using their handoff tools.",
            "When you hand off to a specialist, they will have access to the full conversation history.",
            "After completing their task, control will return to you.",
            ""
        ]

        for agent in child_agents:
            lines.append(f"### {agent['name']}")
            lines.append(f"- **Handoff tool**: `{agent['handoff_tool']}`")
            lines.append(f"- **Specialization**: {agent['description']}")
            lines.append("")

        lines.extend([
            "## When to Hand Off",
            "",
            "- Hand off when a task requires the specialist's specific capabilities",
            "- You can hand off multiple times to different specialists as needed",
            "- After a specialist completes their work, continue coordinating the overall task",
        ])

        return "\n".join(lines)

    def _get_checkpointer(self):
        """Get or create a checkpointer for conversation persistence."""
        if self.memory is not None:
            return self.memory
        elif self.store is not None:
            from langgraph.checkpoint.memory import MemorySaver
            return MemorySaver()
        else:
            from langgraph.checkpoint.memory import MemorySaver
            logger.info("Using default MemorySaver for conversation persistence")
            return MemorySaver()
