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
from ..middleware.tool_exception_handler import ToolExceptionHandlerMiddleware
from ..middleware.base import Middleware, MiddlewareManager
from ..utils.utils import deduplicate_tool_names

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
        self.swarm_mode = ('swarm' in conversation_internal_tools or 'swarm' in version_internal_tools) and app_type != 'pipeline'

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

        # Handle internal tools from both locations:
        # - Root level 'internal_tools' (used by predict_agent)
        # - Meta level 'meta.internal_tools' (used by application agent)
        meta = data.get('meta', {})
        internal_tools_list = data.get('internal_tools', []) or meta.get('internal_tools', [])

        # Filter out mode flags that aren't actual tools
        mode_flags = {'lazy_tools_mode'}
        actual_internal_tools = [t for t in internal_tools_list if t not in mode_flags]

        if actual_internal_tools:
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

            # Build internal tool configs
            internal_tool_configs = []
            for internal_tool_name in actual_internal_tools:
                tool_config = {"type": "internal_tool", "name": internal_tool_name, "settings": {}}
                if bucket_name:
                    tool_config["settings"]["bucket_name"] = bucket_name
                internal_tool_configs.append(tool_config)

            # Insert internal tools at the FRONT of version_tools
            # This ensures they are "first class citizens" - bound to LLM before other toolkits
            version_tools = internal_tool_configs + version_tools

            logger.info(f"Added {len(actual_internal_tools)} internal tools as first-class: {actual_internal_tools}")

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
                if not isinstance(mw, ToolExceptionHandlerMiddleware):
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

            # Apply tool wrapping from ToolExceptionHandlerMiddleware if present
            exception_handlers = [mw for mw in middleware if isinstance(mw, ToolExceptionHandlerMiddleware)]
            if exception_handlers:
                # Validate only one exception handler is present
                if len(exception_handlers) > 1:
                    raise ValueError(
                        f"Only one ToolExceptionHandlerMiddleware is supported per assistant. "
                        f"Found {len(exception_handlers)} instances."
                    )

                # Use the exception handler middleware
                exception_handler = exception_handlers[0]
                wrapped_tools = []
                for tool in self.tools:
                    wrapped_tool = exception_handler.wrap_tool(tool)
                    wrapped_tools.append(wrapped_tool)
                self.tools = wrapped_tools
                # Also wrap always-bind tools
                self._always_bind_tools = [exception_handler.wrap_tool(t) for t in self._always_bind_tools]
                logger.info(f"Wrapped {len(self.tools)} tools with ToolExceptionHandlerMiddleware")

        # In lazy tools mode, don't rename tools - ToolRegistry handles namespacing by toolkit.
        # Only add suffixes in non-lazy mode where tools are bound directly to LLM.
        # Note: if lazy mode is later auto-disabled (< 20 tools), create_graph() handles dedup.
        if not self.lazy_tools_mode:
            deduplicate_tool_names(self.tools, context="init")

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

    @staticmethod
    def _unwrap_tool(tool: BaseTool) -> BaseTool:
        """Return the original tool if it was wrapped by middleware, otherwise return as-is."""
        return getattr(tool, '_original_tool', tool)

    def _is_agent_tool(self, tool: BaseTool) -> bool:
        """
        Check if a tool is an Application tool (represents a child agent).

        Application tools wrap other agents/pipelines and can be identified by:
        - Being an instance of the Application class
        - Having an 'application' attribute (the wrapped runnable)

        If the tool was wrapped by ToolExceptionHandlerMiddleware, checks the
        original unwrapped tool (via _original_tool) to preserve type identity.
        """
        original = self._unwrap_tool(tool)
        from ..tools.application import Application
        if isinstance(original, Application):
            return True
        # Fallback: check for application attribute
        if hasattr(original, 'application') and original.application is not None:
            return True
        return False


    def _create_swarm_agent(self, all_tools: list, agent_tools: list):
        """
        Create a swarm-style multi-agent system using the official langgraph-swarm library.

        Uses create_swarm() with compiled subgraphs per agent and Command-based handoffs.
        Follows the official peer-to-peer pattern: every agent has handoff tools to every
        other agent. There is no parent/child hierarchy — all agents are peers.

        Architecture:
        - All agents are peers in a flat swarm graph
        - The main agent is just the default_active_agent entry point
        - Each agent has create_handoff_tool for every other peer
        - Pipelines are wrapped as tools inside virtual LLM-equipped peer agents
        - Handoffs use Command(goto=X, graph=Command.PARENT) from official create_handoff_tool()
        - All agents share message history via SwarmState

        Args:
            all_tools: All tools including agent tools
            agent_tools: Subset of tools that are Application (child agent) tools
        """
        from typing import Optional
        from langchain_core.messages import AIMessage, ToolMessage
        from langchain_core.callbacks.manager import dispatch_custom_event
        from langchain_core.runnables import RunnableConfig
        from langgraph.graph import StateGraph, END, START, MessagesState
        from langgraph.prebuilt import ToolNode
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.types import Command
        from langgraph_swarm import create_swarm, create_handoff_tool

        # For swarm mode, always use a fresh MemorySaver to avoid corrupted state
        # from previous failed runs. The message history is passed via invoke(),
        # so we don't need to persist across invocations.
        checkpointer = MemorySaver()
        logger.info("[SWARM] Using fresh MemorySaver for swarm mode")

        # Separate regular tools from agent tools
        regular_tools = [t for t in all_tools if t not in agent_tools]

        # Resolve prompt
        prompt_instructions = self._resolve_jinja2_variables(self.prompt)

        # Stable internal name for the main agent (the default_active_agent).
        # Not "parent" or "coordinator" — just another peer in the swarm.
        main_agent_name = "main_agent"

        # --- Helper: filter orphaned tool_use blocks from message history ---
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
                        if msg.content:
                            cleaned_messages.append(AIMessage(content=msg.content))
                    elif orphaned_calls:
                        cleaned_messages.append(AIMessage(content=msg.content, tool_calls=valid_calls))
                    else:
                        cleaned_messages.append(msg)
                else:
                    cleaned_messages.append(msg)

            return cleaned_messages

        # --- Helper: create agent model node with custom event emission ---
        def make_agent_node(model, tools, prompt, agent_name):
            """Create an agent model node function with swarm event emission."""
            if tools:
                model_with_tools = model.bind_tools(tools)
            else:
                model_with_tools = model

            def agent_node(state: MessagesState, config: RunnableConfig = None):
                messages = state["messages"]
                # Filter out existing system messages to avoid "multiple non-consecutive system messages" error
                filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]
                # Filter orphaned tool_use blocks to avoid Anthropic API errors
                filtered_messages = filter_orphaned_tool_calls(filtered_messages)

                # Emit swarm agent start event
                if config:
                    try:
                        dispatch_custom_event(
                            "swarm_agent_start",
                            {
                                "agent_name": agent_name,
                                "is_default_agent": agent_name == main_agent_name,
                                "message_count": len(filtered_messages),
                            },
                            config=config
                        )
                    except Exception as e:
                        logger.debug(f"[SWARM] Failed to emit swarm_agent_start event: {e}")

                system_msg = SystemMessage(content=prompt)
                response = model_with_tools.invoke([system_msg] + filtered_messages, config)

                # Guard against multiple simultaneous handoff tool calls.
                # langgraph-swarm can only follow one Command(goto=...) per turn;
                # extra transfer_to_* calls would leave orphaned tool_calls in the
                # message history, crashing the next LLM invocation.
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    transfer_calls = [tc for tc in response.tool_calls if tc.get('name', '').startswith('transfer_to_')]
                    if len(transfer_calls) > 1:
                        from langchain_core.messages import AIMessage
                        logger.warning(
                            f"[SWARM] LLM emitted {len(transfer_calls)} simultaneous handoff calls. "
                            f"Keeping only the first: {transfer_calls[0].get('name')}"
                        )
                        non_transfer = [tc for tc in response.tool_calls if not tc.get('name', '').startswith('transfer_to_')]
                        response = AIMessage(
                            content=response.content,
                            tool_calls=non_transfer + [transfer_calls[0]],
                        )

                # Emit swarm agent response event
                if config:
                    try:
                        content = response.content if hasattr(response, 'content') else str(response)
                        has_tool_calls = bool(getattr(response, 'tool_calls', None))
                        tool_call_names = [tc.get('name') for tc in (response.tool_calls or [])] if has_tool_calls else []
                        dispatch_custom_event(
                            "swarm_agent_response",
                            {
                                "agent_name": agent_name,
                                "is_default_agent": agent_name == main_agent_name,
                                "content": content,
                                "has_tool_calls": has_tool_calls,
                                "tool_calls": tool_call_names,
                            },
                            config=config
                        )

                        # Emit swarm_handoff event if this response contains a handoff tool call
                        for tc_name in tool_call_names:
                            if tc_name.startswith('transfer_to_'):
                                to_agent = tc_name.replace('transfer_to_', '')
                                dispatch_custom_event(
                                    "swarm_handoff",
                                    {
                                        "from_agent": agent_name,
                                        "to_agent": to_agent,
                                    },
                                    config=config
                                )
                                logger.info(f"[SWARM] Handoff detected: transferring from {agent_name} to {to_agent}")
                                break
                    except Exception as e:
                        logger.debug(f"[SWARM] Failed to emit swarm event: {e}")

                return {"messages": [response]}

            return agent_node

        # --- Helper: build a compiled agent subgraph ---
        def build_agent_subgraph(model, tools, system_prompt, agent_name):
            """Build a compiled agent subgraph with model→tools loop."""
            builder = StateGraph(MessagesState)

            # Model node with custom events + orphaned tool filtering
            model_node = make_agent_node(model, tools, system_prompt, agent_name)
            builder.add_node("model", model_node)

            # Standard ToolNode — handles Command objects natively for handoffs
            if tools:
                tool_node = ToolNode(tools)
                builder.add_node("tools", tool_node)

            def should_continue(state):
                last = state["messages"][-1]
                if isinstance(last, AIMessage) and getattr(last, 'tool_calls', None):
                    return "tools"
                return END

            builder.add_edge(START, "model")
            if tools:
                builder.add_conditional_edges("model", should_continue, {"tools": "tools", END: END})
                builder.add_edge("tools", "model")
            else:
                builder.add_edge("model", END)

            return builder.compile(name=agent_name)

        # --- Helper: build a direct invocation subgraph (no LLM wrapper) ---
        def build_direct_invocation_subgraph(application_tool, agent_name, is_pipeline=False):
            """Build a subgraph that directly invokes an Application tool.

            Instead of wrapping the application in a virtual LLM agent (which may
            fail to call the tool with proper parameters), this subgraph directly
            invokes the Application tool and hands control back to the main agent.

            Uses a proper ToolNode-based handoff (via create_handoff_tool) so that
            the Command propagates correctly through create_swarm()'s routing.
            """
            import uuid as _uuid
            builder = StateGraph(MessagesState)

            # Create a handoff tool for routing back to main_agent via ToolNode
            handoff_back_tool = create_handoff_tool(
                agent_name=main_agent_name,
                description="Hand back to the main coordinating agent after completing the task"
            )

            def invoke_application(state: MessagesState, config: RunnableConfig = None):
                messages = state["messages"]

                # Emit swarm agent start event
                if config:
                    try:
                        dispatch_custom_event(
                            "swarm_agent_start",
                            {
                                "agent_name": agent_name,
                                "is_default_agent": False,
                                "message_count": len(messages),
                            },
                            config=config
                        )
                    except Exception as e:
                        logger.debug(f"[SWARM] Failed to emit swarm_agent_start: {e}")

                # Extract the user's task from the last HumanMessage
                task = ""
                for msg in reversed(messages):
                    if isinstance(msg, HumanMessage):
                        content = msg.content
                        if isinstance(content, list):
                            content = "\n".join(
                                block.get("text", "") if isinstance(block, dict) else str(block)
                                for block in content
                            )
                        if isinstance(content, str) and content.strip():
                            task = content.strip()
                            break

                if not task:
                    task = "Execute the assigned task"
                    logger.warning(f"[SWARM] No HumanMessage found for {agent_name}, using default task")

                logger.info(
                    f"[SWARM] Direct invoking {'pipeline' if is_pipeline else 'agent'} "
                    f"'{agent_name}' with task: {task[:100]}..."
                )

                # Invoke the Application tool directly
                try:
                    result = application_tool.invoke({"task": task, "chat_history": []})
                    if isinstance(result, dict):
                        content = result.get("output", str(result))
                    elif isinstance(result, str):
                        content = result
                    else:
                        content = str(result)
                except Exception as e:
                    logger.error(f"[SWARM] Direct invocation of '{agent_name}' failed: {e}", exc_info=True)
                    content = f"Execution failed: {e}"

                # Emit swarm agent response event
                if config:
                    try:
                        dispatch_custom_event(
                            "swarm_agent_response",
                            {
                                "agent_name": agent_name,
                                "is_default_agent": False,
                                "content": content[:500] if isinstance(content, str) else str(content)[:500],
                                "has_tool_calls": False,
                                "tool_calls": [],
                            },
                            config=config
                        )
                    except Exception as e:
                        logger.debug(f"[SWARM] Failed to emit swarm_agent_response: {e}")

                logger.info(f"[SWARM] Direct invocation of '{agent_name}' completed, handing back to '{main_agent_name}'")

                # Return result as AIMessage with a handoff tool_call.
                # The ToolNode will process the handoff tool and generate a proper
                # Command(goto=main_agent, graph=Command.PARENT) that create_swarm()
                # knows how to route.
                tool_call_id = f"handoff_back_{_uuid.uuid4().hex[:8]}"
                return {"messages": [
                    AIMessage(
                        content=content,
                        tool_calls=[{
                            "name": f"transfer_to_{main_agent_name}",
                            "args": {},
                            "id": tool_call_id,
                        }]
                    )
                ]}

            tool_node = ToolNode([handoff_back_tool])

            builder.add_node("invoke", invoke_application)
            builder.add_node("tools", tool_node)
            builder.add_edge(START, "invoke")
            builder.add_edge("invoke", "tools")
            builder.add_edge("tools", END)

            return builder.compile(name=agent_name)

        # === PASS 1: Collect all peer agent metadata ===
        # Pipelines: use direct invocation (no LLM wrapper needed)
        # Agents: use Application tool inside LLM peer (preserves peer-to-peer handoffs)
        peer_configs = []

        for agent_tool in agent_tools:
            # If the tool was wrapped by ToolExceptionHandlerMiddleware, unwrap to
            # access Application-specific attributes (client, args_runnable, etc.)
            original_agent_tool = self._unwrap_tool(agent_tool)

            agent_name = agent_tool.name
            original_name = agent_tool.metadata.get('original_name', agent_name) if hasattr(agent_tool, 'metadata') else agent_name

            # Detect pipeline vs agent
            is_pipeline = getattr(original_agent_tool, 'is_subgraph', False)

            if is_pipeline:
                # Pipeline: force string output so the result is usable as text
                original_agent_tool.is_subgraph = False
                if hasattr(original_agent_tool, 'args_runnable') and isinstance(original_agent_tool.args_runnable, dict):
                    original_agent_tool.args_runnable['is_subgraph'] = False
                logger.info(f"[SWARM] Pipeline peer '{original_name}': will use direct invocation")
            else:
                logger.info(f"[SWARM] Agent peer '{original_name}': will use Application tool in LLM peer")

            # Extract peer agent's own instructions from version_details if available
            peer_instructions = None
            vd = getattr(original_agent_tool, 'args_runnable', {}).get('version_details')
            if vd and vd.get('instructions'):
                peer_instructions = vd['instructions']

            peer_configs.append({
                'name': agent_name,
                'original_name': original_name,
                'description': agent_tool.description,
                'application_tool': original_agent_tool,
                'agent_tool': agent_tool,  # Wrapped tool for LLM peers
                'is_pipeline': is_pipeline,
                'instructions': peer_instructions,
            })

        # === PASS 2: Create handoff tools for all agents ===
        # Official langgraph-swarm pattern: each agent gets create_handoff_tool
        # for every OTHER agent in the swarm (peer-to-peer, bidirectional).
        # Pipeline peers don't need handoff tools (they auto-return via Command).
        all_agent_names = [main_agent_name] + [cfg['name'] for cfg in peer_configs]

        def create_handoffs_for(agent_name_self):
            """Create handoff tools for all agents EXCEPT agent_name_self."""
            handoffs = []
            for target_name in all_agent_names:
                if target_name == agent_name_self:
                    continue
                if target_name == main_agent_name:
                    desc = "Hand off to the main coordinating agent"
                else:
                    target_cfg = next((c for c in peer_configs if c['name'] == target_name), None)
                    desc = (f"Hand off to {target_cfg['original_name']}: {target_cfg['description']}"
                            if target_cfg else f"Hand off to {target_name}")
                handoffs.append(create_handoff_tool(
                    agent_name=target_name,
                    description=desc,
                ))
            return handoffs

        # --- Main agent setup ---
        main_handoff_tools = create_handoffs_for(main_agent_name)
        peer_agent_descriptions = [{
            'name': cfg['original_name'],
            'handoff_tool': f"transfer_to_{cfg['name']}",
            'description': cfg['description'],
        } for cfg in peer_configs]

        swarm_prompt_addon = self._build_swarm_prompt_addon(peer_agent_descriptions, agent_role="main")
        enhanced_prompt = f"{prompt_instructions}\n\n{swarm_prompt_addon}"
        main_tools = regular_tools + main_handoff_tools

        # Deduplicate tool names for swarm main agent.
        # Swarm uses model.bind_tools() directly (not create_graph/ToolRegistry),
        # so unique names are required. If lazy_tools_mode was True, __init__
        # skipped dedup — fix it here before binding.
        renamed = deduplicate_tool_names(main_tools, context="swarm-main")
        if renamed:
            logger.info(f"[SWARM] Deduplicated {renamed} tool names for main agent")

        # --- Agent peer setup (LLM peers with Application tool + handoff tools) ---
        compiled_agent_peers = []
        for cfg in peer_configs:
            if cfg['is_pipeline']:
                continue  # Pipelines use direct invocation, handled below

            peer_handoff_tools = create_handoffs_for(cfg['name'])

            # Build peer descriptions for this agent's prompt (excluding itself)
            other_agents = [{
                'name': main_agent_name,
                'handoff_tool': f"transfer_to_{main_agent_name}",
                'description': "The main coordinating agent",
            }]
            for other_cfg in peer_configs:
                if other_cfg['name'] != cfg['name']:
                    other_agents.append({
                        'name': other_cfg['original_name'],
                        'handoff_tool': f"transfer_to_{other_cfg['name']}",
                        'description': other_cfg['description'],
                    })

            peer_prompt_addon = self._build_swarm_prompt_addon(other_agents, agent_role="peer")

            if cfg['instructions']:
                base_prompt = self._resolve_jinja2_variables(cfg['instructions'])
            else:
                base_prompt = f"You are {cfg['original_name']}. {cfg['description']}"

            # Add explicit instructions to call the Application tool
            tool_name = cfg['name']
            tool_instruction = (
                f"\n\n## How to Execute Your Task\n"
                f"You have access to the `{tool_name}` tool which executes your full agent capabilities.\n"
                f"To process a request:\n"
                f"1. ALWAYS call the `{tool_name}` tool with the user's request as the `task` parameter.\n"
                f"2. After receiving the result, hand off to the appropriate agent.\n"
                f"3. Do NOT respond with your own text without calling the `{tool_name}` tool first.\n"
            )

            peer_system_prompt = f"{base_prompt}{tool_instruction}\n{peer_prompt_addon}"

            # Simplify the Application tool schema for swarm peers.
            # The default schema includes chat_history: Optional[list[BaseMessage]] which
            # LLMs can't construct (BaseMessage is a Pydantic model, not JSON-serializable).
            # For swarm peers, chat_history is always [] so we remove it from the schema.
            swarm_tool = cfg['agent_tool']
            try:
                from pydantic import create_model as _create_model
                from pydantic.fields import Field as _Field
                # Keep task + any agent variables, but drop chat_history
                swarm_fields = {}
                for field_name, field_info in swarm_tool.args_schema.model_fields.items():
                    if field_name == 'chat_history':
                        continue  # Skip - always [] in swarm context
                    swarm_fields[field_name] = (
                        field_info.annotation,
                        _Field(description=field_info.description, default=field_info.default)
                    )
                if not swarm_fields:
                    swarm_fields['task'] = (str, _Field(description="Task for the agent to execute"))
                safe = ''.join(c if c.isalnum() else '_' for c in cfg['name'])
                simplified_schema = _create_model(f"{safe}SwarmSchema", **swarm_fields)
                swarm_tool = swarm_tool.model_copy(update={'args_schema': simplified_schema})
                logger.info(f"[SWARM] Simplified schema for '{cfg['name']}': {list(swarm_fields.keys())}")
            except Exception as e:
                logger.warning(f"[SWARM] Could not simplify schema for '{cfg['name']}': {e}, using original")

            # Agent peer gets: Application tool (wrapping the full agent) + handoff tools
            all_peer_tools = [swarm_tool] + peer_handoff_tools

            compiled_agent_peers.append({
                'name': cfg['name'],
                'tools': all_peer_tools,
                'prompt': peer_system_prompt,
            })

        # --- Build compiled subgraphs for all agents ---
        # Main agent: LLM-based subgraph with regular tools + handoff tools
        # Agent peers: LLM-based subgraph with Application tool + handoff tools
        # Pipeline peers: Direct invocation subgraphs (no LLM)
        main_graph = build_agent_subgraph(self.client, main_tools, enhanced_prompt, main_agent_name)

        peer_graphs = []
        for cfg in peer_configs:
            if cfg['is_pipeline']:
                # Pipeline: direct invocation (reliable, no LLM needed)
                peer_graph = build_direct_invocation_subgraph(
                    application_tool=cfg['application_tool'],
                    agent_name=cfg['name'],
                    is_pipeline=True,
                )
                logger.info(f"[SWARM] Built direct invocation subgraph for pipeline peer '{cfg['name']}'")
            else:
                # Agent: LLM peer with Application tool + handoff tools
                agent_peer_cfg = next(c for c in compiled_agent_peers if c['name'] == cfg['name'])
                peer_graph = build_agent_subgraph(
                    self.client, agent_peer_cfg['tools'],
                    agent_peer_cfg['prompt'], cfg['name']
                )
                logger.info(f"[SWARM] Built LLM agent subgraph for agent peer '{cfg['name']}'")
            peer_graphs.append(peer_graph)

        # --- Adapter to convert swarm output to {"output": ...} format ---
        class SwarmResultAdapter:
            """Wraps a compiled swarm graph to return {"output": ...} format expected by pylon."""
            def __init__(self, compiled_graph):
                self._graph = compiled_graph

            def invoke(self, input, config=None, **kwargs):
                result = self._graph.invoke(input, config, **kwargs)
                messages = result.get("messages", [])
                output = None
                for msg in reversed(messages):
                    if hasattr(msg, 'content') and not isinstance(msg, HumanMessage):
                        content = msg.content
                        if isinstance(content, list):
                            content = "\n".join(
                                block.get("text", "") if isinstance(block, dict) else str(block)
                                for block in content
                            )
                        if isinstance(content, str) and content.strip():
                            output = content
                            break
                return {
                    "output": output or "",
                    "thread_id": None,
                    "execution_finished": True,
                }

        # --- Wire with official create_swarm() ---
        try:
            swarm = create_swarm(
                [main_graph] + peer_graphs,
                default_active_agent=main_agent_name
            )
            compiled = swarm.compile(checkpointer=checkpointer, store=self.store)
            logger.info(
                f"[SWARM] Created swarm with {len(peer_configs)} direct-invocation peers: "
                f"{[cfg['name'] for cfg in peer_configs]}, "
                f"default_active_agent='{main_agent_name}'"
            )
            return SwarmResultAdapter(compiled)
        except Exception as e:
            logger.error(f"[SWARM] Failed to compile swarm: {type(e).__name__}: {e}", exc_info=True)
            raise

    def _build_swarm_prompt_addon(self, peer_agents: list, agent_role: str = "main") -> str:
        """
        Build prompt instructions explaining available peer agents for handoff.

        Args:
            peer_agents: List of dicts with 'name', 'handoff_tool', 'description'
            agent_role: Either "main" (the default entry agent) or "peer" (a peer agent)

        Returns:
            Formatted string to append to the agent's prompt
        """
        if not peer_agents:
            return ""

        lines = [
            "## Available Peer Agents",
            "",
        ]

        if agent_role == "main":
            lines.extend([
                "You can delegate tasks to the following peer agents by using their handoff tools.",
                "When you hand off to a peer, they will have access to the full conversation history.",
                "",
            ])
        else:
            lines.extend([
                "You are part of a multi-agent swarm. You can hand off to the following peer agents.",
                "When you have completed your task, you MUST hand off to another agent "
                "(typically the main agent) so the conversation can continue.",
                "If you simply respond with text and no tool calls, the entire swarm will stop.",
                "",
            ])

        for agent in peer_agents:
            lines.append(f"### {agent['name']}")
            lines.append(f"- **Handoff tool**: `{agent['handoff_tool']}`")
            lines.append(f"- **Specialization**: {agent['description']}")
            lines.append("")

        lines.extend([
            "## When to Hand Off",
            "",
            "- Hand off when a task requires another agent's specific capabilities",
            "- **IMPORTANT: Hand off to only ONE agent at a time.** Do not call multiple transfer tools in the same response.",
            "- You can hand off to different agents sequentially as needed",
        ])

        if agent_role == "peer":
            lines.extend([
                "- **When you finish your assigned task**, hand off back to the "
                "main agent or to the next relevant peer so the conversation continues.",
                "- Only respond with final text (no tool calls) if you are certain "
                "the entire user request is fully complete.",
            ])
        else:
            lines.extend([
                "- After a peer completes their work, they will hand control "
                "back to you or to another relevant peer.",
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
