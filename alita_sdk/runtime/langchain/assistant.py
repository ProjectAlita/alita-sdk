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
                 lazy_tools_mode: Optional[bool] = None):

        self.app_type = app_type
        self.memory = memory
        self.store = store
        self.persona = persona
        self.max_iterations = data.get('meta', {}).get('step_limit', 25)
        self.is_subgraph = is_subgraph  # Store is_subgraph flag

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
            ignored_mcp_servers=ignored_mcp_servers
        )
        if tools:
            self.tools += tools

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
        """
        # Exclude compiled graph runnables from simple tool agents
        simple_tools = [t for t in self.tools if isinstance(t, (BaseTool, CompiledStateGraph))]

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
        plan_addon = PLAN_ADDON if 'update_plan' in tool_names else ""
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
            steps_limit=self.max_iterations
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
            lazy_tools_mode=self.lazy_tools_mode
        )
        #
        return agent

    # This one is used only in Alita and OpenAI
    def apredict(self, messages: list[BaseMessage]):
        yield from self.client.ainvoke(messages)

    def predict(self, messages: list[BaseMessage]):
        return self.client.invoke(messages)
