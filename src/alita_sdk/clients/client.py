import logging
import requests
from typing import Dict, List, Any, Optional
from jinja2 import Environment, DebugUndefined, meta
from langchain_core.pydantic_v1 import BaseModel, Field

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    BaseMessage,
    ToolMessage
)
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import  AgentExecutor
from langchain_core.utils.function_calling import convert_to_openai_function

logger = logging.getLogger(__name__)
from ..agents import create_mixed_agent
from ..agents.alita_openai import AlitaAssistantRunnable
from ..toolkits.prompt import PromptToolkit
from ..toolkits.datasource import DatasourcesToolkit
from alita_tools.openapi import AlitaOpenAPIToolkit
from pydantic import create_model

class Jinja2TemplatedChatMessagesTemplate(ChatPromptTemplate):
    
    def _resolve_variables(self, message:BaseMessage, kwargs:Dict) -> BaseMessage:
        environment = Environment(undefined=DebugUndefined)
        template = environment.from_string(message.content)
        content = template.render(kwargs)
        if isinstance(message, SystemMessage):
            return SystemMessage(content=content)
        elif isinstance(message, AIMessage):
            return AIMessage(content=content)
        elif isinstance(message, HumanMessage):
            return HumanMessage(content=content)
        elif isinstance(message, ToolMessage):
            return ToolMessage(content=content)
        else:
            return BaseMessage(content=content)

    def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
        """Format the chat template into a list of finalized messages.

        Args:
            **kwargs: keyword arguments to use for filling in template variables
                      in all the template messages in this chat template.

        Returns:
            list of formatted messages
        """
        kwargs = self._merge_partial_and_user_variables(**kwargs)
        result = []
        for message_template in self.messages:
            if isinstance(message_template, BaseMessage):
                message = self._resolve_variables(message_template, kwargs)
                logger.debug(message.content)
                result.append(message)
        return result
    

class AlitaDataSource:
    def __init__(self, alita:Any, datasource_id:int, name:str, description: str,
                 datasource_settings, datasource_predict_settings):
        self.alita = alita
        self.name = name
        self.description = description
        self.datasource_id = datasource_id
        self.datasource_settings = datasource_settings
        self.datasource_predict_settings = datasource_predict_settings
    
    def predict(self, user_input: str, chat_history: Optional[list[BaseMessage]]=[]):
        messages = chat_history + [HumanMessage(content=user_input)]
        return self.alita.rag(self.datasource_id, messages, 
                              self.datasource_settings, 
                              self.datasource_predict_settings)
        
    def search(self, query: str):
        return self.alita.search(self.datasource_id, [HumanMessage(content=query)], 
                                  self.datasource_settings)
        

class AlitaPrompt:
    def __init__(self, alita:Any, prompt: ChatPromptTemplate, name:str, description: str, llm_settings: dict):
        self.alita = alita
        self.prompt = prompt
        self.name = name
        self.llm_settings = llm_settings
        self.description = description
    
    def create_pydantic_model(self):
        fields = {}
        for variable in self.prompt.input_variables:
            fields[variable] = (str, None)
        if "input" not in list(fields.keys()):
            fields["input"] = (str, None)
        return create_model("PromptVariables", **fields)
        
    
    def predict(self, variables: dict={}):
        input = variables.pop("input", None)
        alita_vars = []
        for key, value in variables.items():
            alita_vars.append({
                "name": key,
                "value": value
            })
        messages = [SystemMessage(content=self.prompt.messages[0].content), HumanMessage(content=input)]
        result = []
        for message in self.alita.predict(messages, self.llm_settings, variables=alita_vars):
            result.append(message.content)
        return "\n\n".join(result)


class Assistant:
    def __init__(self, client:Any, prompt:ChatPromptTemplate, tools: list, 
                 openai_tools: Optional[Dict]=None):
        self.prompt = prompt
        self.client = client
        self.tools = tools
        self.openai_tools = openai_tools
    
    def getAgentExecutor(self):
        agent = create_mixed_agent(llm=self.client, tools=self.tools, prompt=self.prompt)
        return AgentExecutor.from_agent_and_tools(agent=agent, tools=self.tools,
                                                  verbose=True, handle_parsing_errors=True, 
                                                  max_execution_time=None, return_intermediate_steps=True)
        
    def getOpenAIAgentExecutor(self):
        agent = AlitaAssistantRunnable(client=self.client, assistant=self)
        return AgentExecutor.from_agent_and_tools(agent=agent, tools=self.tools,
                                                  verbose=True, handle_parsing_errors=True, 
                                                  max_execution_time=None,
                                                  return_intermediate_steps=True)
    
    # This one is used only in Alita OpenAI
    def apredict(self, messages: list[BaseMessage]):
        yield from self.client.ainvoke([self.prompt.messages[0]] + messages, functions=self.openai_tools)
    
    def predict(self, messages: list[BaseMessage]):
        response = self.client.invoke([self.prompt.messages[0]] + messages, functions=self.openai_tools)
        return response
    

class AlitaClient:
    def __init__(self, base_url: str, project_id: int, auth_token: str):
        self.base_url = base_url
        self.project_id = project_id
        self.auth_token = auth_token        
        self.headers = {
            "Authorization": f"Bearer {auth_token}"
        }
        self.predict_url = f"{self.base_url}/api/v1/prompt_lib/predict/prompt_lib/{self.project_id}"
        self.prompt_versions = f"{self.base_url}/api/v1/prompt_lib/version/prompt_lib/{self.project_id}"
        self.prompts = f"{self.base_url}/api/v1/prompt_lib/prompt/prompt_lib/{self.project_id}"
        self.datasources = f"{self.base_url}/api/v1/datasources/datasource/prompt_lib/{self.project_id}"
        self.datasources_predict = f"{self.base_url}/api/v1/datasources/predict/prompt_lib/{self.project_id}"
        self.datasources_search = f"{self.base_url}/api/v1/datasources/search/prompt_lib/{self.project_id}"
        self.application_versions = f"{self.base_url}/api/v1/applications/version/prompt_lib/{self.project_id}"
        

    def prompt(self, prompt_id, prompt_version_id, chat_history=None, return_tool=False):
        url = f"{self.prompt_versions}/{prompt_id}/{prompt_version_id}"
        data = requests.get(url, headers=self.headers).json()
        model_settings = data['model_settings']
        messages = [SystemMessage(content=data['context'])]
        variables = {}
        if data['messages']:
            for message in data['messages']:
                if message.get('role') == 'assistant':
                    messages.append(AIMessage(content=message['content']))
                elif message.get('role') == 'user':
                    messages.append(HumanMessage(content=message['content']))
                else:
                    messages.append(SystemMessage(content=message['content']))
        if chat_history and isinstance(chat_history, list[BaseMessage]):
            messages.extend(chat_history)
        input_variables = []
        for variable in data['variables']:
            if variable['value']:
                variables[variable['name']] = variable['value']
            else:
                input_variables.append(variable['name'])
        template = Jinja2TemplatedChatMessagesTemplate(messages=messages)
        if input_variables and not variables:
            template.input_variables = input_variables
        if variables:
            template.partial_variables = variables
        if not return_tool:
            return template
        else:
            url = f"{self.prompts}/{prompt_id}"
            data = requests.get(url, headers=self.headers).json()
            return AlitaPrompt(self, template, data['name'], data['description'], model_settings)

    
    def application(self, client: Any, application_id:int, application_version_id:int):
        url = f"{self.application_versions}/{application_id}/{application_version_id}"
        data = requests.get(url, headers=self.headers).json()
        messages = [SystemMessage(content=data['instructions'])]
        variables = {}
        input_variables = []
        for variable in data['variables']:
            print(variable)
            if variable['value'] != "":
                variables[variable['name']] = variable['value']
            else:
                input_variables.append(variable['name'])
        template = Jinja2TemplatedChatMessagesTemplate(messages=messages)
        if input_variables and not variables:
            template.input_variables = input_variables
        if variables:
            template.partial_variables = variables
        if input_variables:
            prompt_type = 'react'
        else:
            prompt_type = 'openai'
        prompts = []
        tools = []
        for tool in data['tools']:
            if tool['type'] == 'prompt':
                prompts.append([tool['settings']['prompt_id'], tool['settings']['prompt_version_id']])
            elif tool['type'] == 'datasource':
                tools += DatasourcesToolkit.get_toolkit(self, [tool['settings']['datasource_id']], tool['settings']['selected_tools']).get_tools()
            elif tool['type'] == 'openapi':
                headers = {}
                if tool['settings'].get('authentication'):
                    if tool['settings']['authentication']['type'] == 'api_key': 
                        auth_type = tool['settings']['authentication']['settings']['auth_type']
                        auth_key = tool["settings"]["authentication"]["settings"]["api_key"]
                        if auth_type.lower() == 'bearer':
                            headers['Authorization'] = f'Bearer {auth_key}'
                        if auth_type.lower() == 'basic':
                            headers['Authorization'] = f'Basic {auth_key}'
                        if auth_type.lower() == 'custom':
                            headers[tool["settings"]["authentication"]["settings"]["custom_header_name"]] = f'{auth_key}'  
                tools += AlitaOpenAPIToolkit.get_toolkit(tool['settings']['schema_settings'], headers={}).get_tools()
        if len(prompts) > 0:
            tools += PromptToolkit.get_toolkit(self, prompts).get_tools() 
        if prompt_type == 'openai':
            open_ai_funcs = [convert_to_openai_function(t) for t in tools]
            return Assistant(client, template, tools, open_ai_funcs).getOpenAIAgentExecutor()
        else:
            return Assistant(client, template, tools).getAgentExecutor()

    def datasource(self, datasource_id:int) -> AlitaDataSource:
        url = f"{self.datasources}/{datasource_id}"
        data = requests.get(url, headers=self.headers).json()
        datasource_model = data['version_details']['datasource_settings']['chat']['chat_settings_embedding']
        chat_model = data['version_details']['datasource_settings']['chat']['chat_settings_ai']
        return AlitaDataSource(self, datasource_id, data["name"], data["description"],
                               datasource_model, chat_model)
    
    def assistant(self, prompt_id: int, prompt_version_id: int, 
                  tools: list, openai_tools: Optional[Dict]=None, 
                  client: Optional[Any] = None):
        prompt = self.prompt(prompt_id=prompt_id, prompt_version_id=prompt_version_id)
        return Assistant(client, prompt, tools, openai_tools)
    
    def _prepare_messages(self, messages: list[BaseMessage]):
        context = ''
        chat_history = []
        if messages[0].type == "system":
            context = messages[0].content
        for message in messages[1:-1]:
            if message.type == 'human':
                chat_history.append({
                    'role': 'user',
                    'content': message.content
                })
            elif message.type == 'system':
                chat_history.append({
                    'role': 'system',
                    'content': message.content
                })
            else:
                chat_history.append({
                    'role': 'assistant',
                    'content': message.content
                })
        user_input = messages[-1].content
        return context, chat_history, user_input
    
    def _prepare_payload(self, messages: list[BaseMessage], model_settings: dict, variables: dict):
        context, chat_history, user_input = self._prepare_messages(messages)
        if not variables:
            variables = []
        return {
            "type": "chat",
            "project_id": self.project_id,
            "context": context,
            "model_settings": model_settings,
            "user_input": user_input,
            "chat_history": chat_history,
            "variables": variables,
            "format_response": True
        }
        
    def async_predict(self, messages: list[BaseMessage], model_settings: dict, variables: list[dict]=None):
        # TODO: Modify to make it appropriate stream response
        prompt_data = self._prepare_payload(messages, model_settings, variables)
        response = requests.post(self.predict_url, headers=self.headers, json=prompt_data)
        logger.info(response.content)
        response_data = response.json()
        for message in response_data['messages']:
            if message.get('role') == 'user':
                yield HumanMessage(content=message['content'])
            else:
                yield AIMessage(content=message['content'])
    
    def predict(self, messages: list[BaseMessage], model_settings: dict, variables: list[dict]=None):
        prompt_data = self._prepare_payload(messages, model_settings, variables)
        
        response = requests.post(self.predict_url, headers=self.headers, json=prompt_data)
        if response.status_code != 200:
            logger.error("Error in response of predict: {response.content}")
            raise requests.exceptions.HTTPError(response.content)
        try:
            response_data = response.json()
            response_messages = []
            print(response_data['messages'])
            for message in response_data['messages']:
                if message.get('type') == 'user':
                    response_messages.append(HumanMessage(content=message['content']))
                else:
                    response_messages.append(AIMessage(content=message['content']))
            return response_messages
        except TypeError:
            logger.error(f"TypeError in response of predict: {response_data}")
            raise
    
    def rag(self, datasource_id:int, messages:list[BaseMessage], 
        datasource_settings: dict, datasource_predict_settings: dict):
        context, chat_history, user_input = self._prepare_messages(messages)
        data = {
            "input": user_input,
            "context": '',
            "chat_history": chat_history,
            "chat_settings_ai": datasource_predict_settings,
            "chat_settings_embedding": datasource_settings
        }
        if context:
            data['context'] = context
        headers = self.headers | {"Content-Type": "application/json"}
        response = requests.post(f"{self.datasources_predict}/{datasource_id}", headers=headers, json=data).json()
        return AIMessage(content=response['response'], additional_kwargs={"references": response['references']})
    
    def search(self, datasource_id:int, messages:list[BaseMessage], datasource_settings: dict):
        _, _, user_input = self._prepare_messages(messages)
        data = {
            "chat_history": [
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            "chat_settings_embedding": datasource_settings,
            "str_content": True
        }
        headers = self.headers | {"Content-Type": "application/json"}
        response = requests.post(f"{self.datasources_search}/{datasource_id}", headers=headers, json=data).json()
        content = "\n\n".join([finding["page_content"] for finding in response["findings"]])
        return AIMessage(content=content, additional_kwargs={"references": response['references']})
