import logging
import importlib
from copy import deepcopy as copy
from typing import Any, Optional
from langchain.agents import (
    AgentExecutor, create_openai_tools_agent,
    create_json_chat_agent)
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from .agents.xml_chat import create_xml_chat_agent
from .langraph_agent import create_graph
from langchain_core.messages import (
    BaseMessage, SystemMessage, HumanMessage
)
from langchain_core.prompts import MessagesPlaceholder
from .constants import REACT_ADDON, REACT_VARS, XML_ADDON
from .chat_message_template import Jinja2TemplatedChatMessagesTemplate
from ..tools.echo import EchoTool
from langchain_core.tools import BaseTool, ToolException
from jinja2 import Environment, DebugUndefined

logger = logging.getLogger(__name__)

class Assistant:
    def __init__(self,
                 alita: 'AlitaClient',
                 data: dict,
                 client: 'LLMLikeObject',
                 chat_history: list[BaseMessage] = [],
                 app_type: str = "openai",
                 tools: Optional[list] = [],
                 memory: Optional[Any] = None,
                 store: Optional[BaseStore] = None,
                 debug_mode: Optional[bool] = False):

        self.app_type = app_type
        self.memory = memory
        self.store = store
        self.max_iterations = data.get('meta', {}).get('step_limit', 25)

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
        if app_type != "predict":
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
            for internal_tool_name in meta.get("internal_tools"):
                version_tools.append({"type": "internal_tool", "name": internal_tool_name})

        self.tools = get_tools(version_tools, alita_client=alita, llm=self.client, memory_store=self.store, debug_mode=debug_mode)
        if tools:
            self.tools += tools
        # Handle prompt setup
        if app_type in ["pipeline", "predict", "react"]:
            self.prompt = data['instructions']
        else:
            messages = [SystemMessage(content=data['instructions'])]
            messages.append(MessagesPlaceholder("chat_history"))
            if app_type == "react":
                messages.append(HumanMessage(REACT_ADDON))
            elif app_type == "xml":
                messages.append(HumanMessage(XML_ADDON))
            elif app_type in ['openai', 'dial']:
                messages.append(MessagesPlaceholder("input"))
            messages.append(MessagesPlaceholder("agent_scratchpad"))
            variables = {}
            input_variables = []
            for variable in data['variables']:
                if variable['value'] != "":
                    variables[variable['name']] = variable['value']
                else:
                    input_variables.append(variable['name'])
            if app_type in ["react", "xml"]:
                input_variables = list(set(input_variables + REACT_VARS))

            if chat_history and isinstance(chat_history, list):
                messages.extend(chat_history)
            self.prompt = Jinja2TemplatedChatMessagesTemplate(messages=messages)
            if input_variables:
                if hasattr(self.prompt, 'input_variables') and self.prompt.input_variables is not None:
                    self.prompt.input_variables.extend(input_variables)
                else:
                    self.prompt.input_variables = input_variables
            if variables:
                self.prompt.partial_variables = variables
            try:
                logger.info(
                    f"Client was created with client setting: temperature - {self.client._get_model_default_parameters}")
            except Exception as e:
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

    def runnable(self):
        if self.app_type == 'pipeline':
            return self.pipeline()
        elif self.app_type == 'xml':
            return self.getXMLAgentExecutor()
        elif self.app_type in ['predict', 'react', 'openai']:
            return self.getLangGraphReactAgent()
        else:
            self.tools = [EchoTool()] + self.tools
            return self.getAgentExecutor()

    def _agent_executor(self, agent: Any):
        return AgentExecutor.from_agent_and_tools(agent=agent, tools=self.tools,
                                                  verbose=True, handle_parsing_errors=True,
                                                  max_execution_time=None, return_intermediate_steps=True,
                                                  max_iterations=self.max_iterations)

    def getAgentExecutor(self):
        # Exclude compiled graph runnables from simple tool agents
        simple_tools = [t for t in self.tools if isinstance(t, (BaseTool, CompiledStateGraph))]
        agent = create_json_chat_agent(llm=self.client, tools=simple_tools, prompt=self.prompt)
        return self._agent_executor(agent)

    def getXMLAgentExecutor(self):
        # Exclude compiled graph runnables from simple tool agents
        simple_tools = [t for t in self.tools if isinstance(t, (BaseTool, CompiledStateGraph))]
        agent = create_xml_chat_agent(llm=self.client, tools=simple_tools, prompt=self.prompt)
        return self._agent_executor(agent)

    def getOpenAIToolsAgentExecutor(self):
        # Exclude compiled graph runnables from simple tool agents
        simple_tools = [t for t in self.tools if isinstance(t, (BaseTool, CompiledStateGraph))]
        agent = create_openai_tools_agent(llm=self.client, tools=simple_tools, prompt=self.prompt)
        return self._agent_executor(agent)

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
        
        # Extract all messages from prompt/chat history for LangGraph
        chat_history_messages = []
        prompt_instructions = None
        
        if hasattr(self.prompt, 'messages') and self.prompt.messages:
            # Extract all messages from the prompt to use as chat history
            for message in self.prompt.messages:
                # Skip placeholders (MessagesPlaceholder instances) as they are not actual messages
                if hasattr(message, 'variable_name'):  # MessagesPlaceholder has variable_name attribute
                    continue
                # Skip template messages (contains {{variable}} patterns)
                if hasattr(message, 'content') and isinstance(message.content, str) and '{{' in message.content and '}}' in message.content:
                    continue
                # Include actual chat history messages
                chat_history_messages.append(message)
        
        # Only use prompt_instructions if explicitly specified (for predict app_type)
        if self.app_type == "predict" and isinstance(self.prompt, str):
            prompt_instructions = self.prompt

        # take the system message from the openai prompt as a prompt instructions
        if self.app_type == "openai" and hasattr(self.prompt, 'messages'):
            prompt_instructions = self.__take_prompt_from_openai_messages()
        
        # Create a unified YAML schema with conditional tool binding
        # Build the base node configuration
        node_config = {
            'id': 'agent',
            'type': 'llm',
            'prompt': {
                'template': prompt_instructions or "You are a helpful assistant."
            },
            'input': ['messages'],
            'output': ['messages'],
            'transition': 'END'
        }
        
        # Add tool binding only if tools are present
        if simple_tools:
            tool_names = [tool.name for tool in simple_tools]
            tool_names_yaml = str(tool_names).replace("'", '"')  # Convert to YAML-compatible format
            node_config['tool_names'] = tool_names_yaml
            logger.info("Binding tools: %s", tool_names)
        
        # Properly setup the prompt for YAML
        import yaml
        escaped_prompt = prompt_instructions or "You are a helpful assistant."
        
        # Create the schema as a dictionary first, then convert to YAML
        state_messages_config = {'type': 'list'}
        
        # Only set initial messages if there's actual conversation history (not just system prompts)
        actual_conversation_messages = [
            msg for msg in chat_history_messages 
            if not isinstance(msg, SystemMessage)  # Exclude system messages as they're handled by prompt template
        ]
        
        if actual_conversation_messages:
            state_messages_config['value'] = actual_conversation_messages
            logger.info(f"Setting initial conversation history with {len(actual_conversation_messages)} messages")
        
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
        
        # Add tool-specific parameters only if tools exist
        if simple_tools:
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
            steps_limit=self.max_iterations
        )
        #
        return agent

    # This one is used only in Alita and OpenAI
    def apredict(self, messages: list[BaseMessage]):
        yield from self.client.ainvoke(messages)

    def predict(self, messages: list[BaseMessage]):
        return self.client.invoke(messages)

    def __take_prompt_from_openai_messages(self):
        if self.prompt and self.prompt.messages:
            for message in self.prompt.messages:
                # we don't need any message placeholder from the openai agent prompt
                if hasattr(message, 'variable_name'):
                    continue
                # take only the content of the system message from the openai prompt
                if isinstance(message, SystemMessage):
                    environment = Environment(undefined=DebugUndefined)
                    template = environment.from_string(message.content)
                    return template.render(self.prompt.partial_variables)
        return None
