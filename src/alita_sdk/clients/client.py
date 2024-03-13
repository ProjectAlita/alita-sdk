import logging
import requests
from typing import Dict, List, Any, Optional
from jinja2 import Environment, DebugUndefined, meta

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    BaseMessage,
    ToolMessage
)
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

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
    def __init__(self, alita:Any, datasource_id:int, datasource_settings, datasource_predict_settings):
        self.alita = alita
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

    def prompt(self, prompt_id, prompt_version_id, chat_history=None):
        url = f"{self.prompt_versions}/{prompt_id}/{prompt_version_id}"
        data = requests.get(url, headers=self.headers).json()
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
        return template

    def datasource(self, datasource_id:int) -> AlitaDataSource:
        url = f"{self.datasources}/{datasource_id}"
        data = requests.get(url, headers=self.headers).json()
        ai_model = data['version_details']['datasource_settings']['chat']['chat_model']
        datasource_model = data['version_details']['datasource_settings']['chat']['embedding_model']
        temperature = data['version_details']['datasource_settings']['chat']['temperature']
        top_p = data['version_details']['datasource_settings']['chat']['top_p']
        top_k = data['version_details']['datasource_settings']['chat']['top_k']
        max_length = data['version_details']['datasource_settings']['chat']['max_length']
        stream = data['version_details']['datasource_settings']['chat'].get('stream', True)
        cut_off_score = data['version_details']['datasource_settings']['chat'].get('cut_off_score', 0.5)
        page_top_k = data['version_details']['datasource_settings']['chat'].get('page_top_k', 5)
        fetch_k = data['version_details']['datasource_settings']['chat'].get('fetch_k', 30)
        embedding_k = data['version_details']['datasource_settings']['chat'].get('embedding_k', 5)
        datasource_settings = {
            "embedding_integration_uid": datasource_model['integration_uid'],
            "embedding_model_name": datasource_model['model_name'],
            "cut_off_score": cut_off_score,
            "page_top_k": page_top_k,
            "fetch_k": fetch_k,
            "top_k": embedding_k
        }
        datasource_predict_settings = {
            "ai_integration_uid": ai_model["integration_uid"],
            "ai_model_name": ai_model["model_name"],
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_length": max_length,
            "stream": stream,
        }
        return AlitaDataSource(self, datasource_id,datasource_settings, datasource_predict_settings)
        
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
            for message in response_data['messages']:
                if message.get('role') == 'user':
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
            "embedding_integration_uid": datasource_settings['embedding_integration_uid'],
            "embedding_model_name": datasource_settings['embedding_model_name'],
            "cut_off_score": datasource_settings["cut_off_score"],
            "page_top_k": datasource_settings["page_top_k"],
            "fetch_k": datasource_settings["fetch_k"],
            "top_k": datasource_settings["top_k"]
        }
        headers = self.headers | {"Content-Type": "application/json"}
        response = requests.post(f"{self.datasources_search}/{datasource_id}", headers=headers, json=data).json()
        content = "\n\n".join([finding["page_content"] for finding in response["findings"]])
        return AIMessage(content=content, additional_kwargs={"references": response['references']})
        
