
import logging
import importlib
from copy import deepcopy as copy
from typing import Any, Optional
from langchain.agents import (
    AgentExecutor, create_react_agent, 
    create_openai_tools_agent)
from ..langchain.mixedAgentRenderes import render_react_text_description_and_args
from ..langchain.mixedAgentParser import MixedAgentOutputParser
from .langraph_agent import create_graph
from langchain_core.messages import (
    BaseMessage, SystemMessage, HumanMessage
)
from langchain_core.prompts import MessagesPlaceholder
from .constants import REACT_ADDON, REACT_VARS
from .chat_message_template import Jinja2TemplatedChatMessagesTemplate
from ..tools.echo import EchoTool
from ..toolkits.tools import get_tools
logger = logging.getLogger(__name__)

class Assistant:
    
    def __init__(self, 
                 alita: 'AlitaClient',
                 data: dict, 
                 client: 'LLMLikeObject', 
                 chat_history: list[BaseMessage] = [], 
                 app_type: str = "openai", 
                 tools: Optional[list] = [],
                 memory: Optional[dict] = {}):
        
        self.client = copy(client)
        self.client.max_tokens = data['llm_settings']['max_tokens']
        self.client.temperature = data['llm_settings']['temperature']
        self.client.top_p = data['llm_settings']['top_p']
        self.client.top_k = data['llm_settings']['top_k']
        self.client.model_name = data['llm_settings']['model_name']
        self.client.integration_uid = data['llm_settings']['integration_uid']
        
        self.app_type = app_type
        self.memory = memory
        
        if app_type == "pipeline":
            self.tools = get_tools(data['tools'], alita, True)
            self.prompt = data['instructions']
        else:
            self.tools = get_tools(data['tools'], alita) + tools
            if app_type == "react":
                data['instructions'] += REACT_ADDON
            messages = [SystemMessage(content=data['instructions'])]
            if app_type in ['openai', 'dial']:
                messages.append(MessagesPlaceholder("chat_history"))
                messages.append(HumanMessage("{{input}}"))
                messages.append(MessagesPlaceholder("agent_scratchpad"))
            variables = {}
            input_variables = []
            for variable in data['variables']:
                if variable['value'] != "":
                    variables[variable['name']] = variable['value']
                else:
                    input_variables.append(variable['name'])
            if app_type == "react":
                input_variables = list(set(input_variables + REACT_VARS))
            if chat_history and isinstance(chat_history, list):
                messages.extend(chat_history)
            self.prompt = Jinja2TemplatedChatMessagesTemplate(messages=messages)
            if input_variables and not variables:
                self.prompt.input_variables = input_variables
            if variables:
                self.prompt.partial_variables = variables
            if "indexer_config" in data["llm_settings"]:
                model_type = data["llm_settings"]["indexer_config"]["ai_model"]
                model_params = data["llm_settings"]["indexer_config"]["ai_model_params"]
                #
                target_pkg, target_name = model_type.rsplit(".", 1)
                target_cls = getattr(
                    importlib.import_module(target_pkg),
                    target_name
                )
                self.client = target_cls(**model_params)
            else:
                integration_details = data['llm_settings']['integration_details']
                #
                from langchain_openai import AzureChatOpenAI
                self.client = AzureChatOpenAI(
                    azure_endpoint=integration_details['settings']['api_base'],
                    deployment_name=data['llm_settings']['model_name'],
                    openai_api_version=integration_details['settings']['api_version'],
                    openai_api_key=integration_details['settings']['api_token'] if isinstance(integration_details['settings']['api_token'], str) else integration_details['settings']['api_token']['value'],
                    temperature=data['llm_settings']['temperature'],
                    max_tokens=data['llm_settings']['max_tokens'],
                    # timeout=600,
                )
            try:
                logger.info(f"Client was created with client setting: temperature - {self.client._get_model_default_parameters}")
            except Exception as e:
                logger.info(f"Client was created with client setting: temperature - {self.client.temperature} : {self.client.max_tokens}")
    
    def runnable(self):
        if self.app_type == 'pipeline':
            return self.pipeline()
        elif self.app_type == 'openai':
            return self.getOpenAIToolsAgentExecutor()
        else:
            self.tools = [EchoTool()] + self.tools
            return self.getAgentExecutor()    
        
    def _agent_executor(self, agent: Any):
        return AgentExecutor.from_agent_and_tools(agent=agent, tools=self.tools,
                                                  verbose=True, handle_parsing_errors=True,
                                                  max_execution_time=None, return_intermediate_steps=True)

    def getAgentExecutor(self):
        agent = create_react_agent(llm=self.client, tools=self.tools, prompt=self.prompt,
                                   output_parser=MixedAgentOutputParser(), 
                                   tools_renderer=render_react_text_description_and_args)
        return self._agent_executor(agent)
    
    
    def getOpenAIToolsAgentExecutor(self):
        agent = create_openai_tools_agent(llm=self.client, tools=self.tools, prompt=self.prompt)
        return self._agent_executor(agent)
    
    def pipeline(self):
        if self.memory:
            if isinstance(self.memory, dict):
                if self.memory.get('type') == 'postgres':
                    from psycopg import Connection
                    from langgraph.checkpoint.postgres import PostgresSaver
                    with Connection.connect(memory["connection_string"], **memory["connection_kwargs"]) as conn:
                        memory = PostgresSaver(conn)
                else:
                    import sqlite3
                    from langgraph.checkpoint.sqlite import SqliteSaver
                    try:
                        memory = SqliteSaver(sqlite3.connect('/data/cache/memory.db', check_same_thread=False))
                    except sqlite3.OperationalError:
                        memory = SqliteSaver(sqlite3.connect('memory.db', check_same_thread=False))
            elif self.memory:
                from langgraph.checkpoint.memory import MemorySaver
                memory = MemorySaver()
        else:
            import sqlite3
            from langgraph.checkpoint.sqlite import SqliteSaver
            try:
                memory = SqliteSaver(sqlite3.connect('/data/cache/memory.db', check_same_thread=False))
            except sqlite3.OperationalError:
                memory = SqliteSaver(sqlite3.connect('memory.db', check_same_thread=False))
        agent = create_graph(
            client=self.client, tools=self.tools,
            yaml_schema=self.prompt, memory=memory
        )
        return agent

    # This one is used only in Alita and OpenAI
    def apredict(self, messages: list[BaseMessage]):
        yield from self.client.ainvoke(messages)

    def predict(self, messages: list[BaseMessage]):
        return self.client.invoke(messages)
