import logging
import requests
from urllib.parse import quote

from typing import Dict, List, Any, Optional

from langchain_core.messages import (
    AIMessage, HumanMessage,
    SystemMessage, BaseMessage,
)

from ..langchain.assistant import Assistant as LangChainAssistant
# from ..llamaindex.assistant import Assistant as LLamaAssistant
from .prompt import AlitaPrompt
from .datasource import AlitaDataSource
from .artifact import Artifact
from ..langchain.chat_message_template import Jinja2TemplatedChatMessagesTemplate


logger = logging.getLogger(__name__)


class ApiDetailsRequestError(Exception):
    ...


class AlitaClient:
    def __init__(self,
                 base_url: str,
                 project_id: int,
                 auth_token: str,
                 api_extra_headers: Optional[dict] = None,
                 configurations: Optional[list] = None,
                 **kwargs):

        self.base_url = base_url.rstrip('/')
        self.api_path = '/api/v1'
        self.project_id = project_id
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            'X-SECRET': kwargs.get('XSECRET', 'secret')
        }
        if api_extra_headers is not None:
            self.headers.update(api_extra_headers)
        self.predict_url = f"{self.base_url}{self.api_path}/prompt_lib/predict/prompt_lib/{self.project_id}"
        self.prompt_versions = f"{self.base_url}{self.api_path}/prompt_lib/version/prompt_lib/{self.project_id}"
        self.prompts = f"{self.base_url}{self.api_path}/prompt_lib/prompt/prompt_lib/{self.project_id}"
        self.datasources = f"{self.base_url}{self.api_path}/datasources/datasource/prompt_lib/{self.project_id}"
        self.datasources_predict = f"{self.base_url}{self.api_path}/datasources/predict/prompt_lib/{self.project_id}"
        self.datasources_search = f"{self.base_url}{self.api_path}/datasources/search/prompt_lib/{self.project_id}"
        self.app = f"{self.base_url}{self.api_path}/applications/application/prompt_lib/{self.project_id}"
        self.application_versions = f"{self.base_url}{self.api_path}/applications/version/prompt_lib/{self.project_id}"
        self.list_apps_url = f"{self.base_url}{self.api_path}/applications/applications/prompt_lib/{self.project_id}"
        self.integration_details = f"{self.base_url}{self.api_path}/integrations/integration/{self.project_id}"
        self.secrets_url = f"{self.base_url}{self.api_path}/secrets/secret/{self.project_id}"
        self.artifacts_url = f"{self.base_url}{self.api_path}/artifacts/artifacts/{self.project_id}"
        self.artifact_url = f"{self.base_url}{self.api_path}/artifacts/artifact/{self.project_id}"
        self.bucket_url = f"{self.base_url}{self.api_path}/artifacts/buckets/{self.project_id}"
        self.configurations_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=configurations&unsecret=true'
        self.ai_section_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=ai'
        self.configurations: list = configurations or []

    def prompt(self, prompt_id, prompt_version_id, chat_history=None, return_tool=False):
        url = f"{self.prompt_versions}/{prompt_id}/{prompt_version_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
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
        if chat_history and isinstance(chat_history, list):
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
            data = requests.get(url, headers=self.headers, verify=False).json()
            return AlitaPrompt(self, template, data['name'], data['description'], model_settings)

    def get_app_details(self, application_id: int):
        url = f"{self.app}/{application_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data

    def get_list_of_apps(self):
        apps = []
        limit = 10
        offset = 0
        total_count = None

        while total_count is None or offset < total_count:
            params = {'offset': offset, 'limit': limit}
            resp = requests.get(self.list_apps_url, headers=self.headers, params=params, verify=False)

            if resp.ok:
                data = resp.json()
                total_count = data.get('total')
                apps.extend([{"name": app['name'], "id": app['id']} for app in data.get('rows', [])])
                offset += limit
            else:
                break

        return apps
            
    def fetch_available_configurations(self) -> list:
        resp = requests.get(self.configurations_url, headers=self.headers, verify=False)
        if resp.ok:
            return resp.json()
        return []

    def all_models_and_integrations(self):
        resp = requests.get(self.ai_section_url, headers=self.headers, verify=False)
        if resp.ok:
            return resp.json()
        return []

    def get_app_version_details(self, application_id: int, application_version_id: int) -> dict:
        url = f"{self.application_versions}/{application_id}/{application_version_id}"
        if self.configurations:
            configs = self.configurations
        else:
            configs = self.fetch_available_configurations()

        resp = requests.patch(url, headers=self.headers, verify=False, json={'configurations': configs})
        if resp.ok:
            return resp.json()
        raise ApiDetailsRequestError

    def get_integration_details(self, integration_id: str, format_for_model: bool = False):
        url = f"{self.integration_details}/{integration_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data

    def unsecret(self, secret_name: str):
        url = f"{self.secrets_url}/{secret_name}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data.get('secret', None)

    def application(self, client: Any, application_id: int, application_version_id: int,
                    tools: Optional[list] = None, chat_history: Optional[List[Any]] = None,
                    app_type=None, memory=None, runtime='langchain',
                    application_variables: Optional[dict] = None):
        if tools is None:
            tools = []
        if chat_history is None:
            chat_history = []
        data = self.get_app_version_details(application_id, application_version_id)

        if application_variables:
            for var in data.get('variables', {}):
                if var['name'] in application_variables:
                    var.update(application_variables[var['name']])

        if not app_type:
            app_type = data.get("agent_type", "react")
        if app_type == "alita":
            app_type = "react"
        elif app_type == "llama":
            app_type = "react"
        elif app_type == "dial":
            app_type = "openai"
        elif app_type == 'autogen':
            app_type = "openai"
        if runtime == 'nonrunnable':
            return LangChainAssistant(self, data, client, chat_history, app_type, 
                                      tools=tools, memory=memory)
        if runtime == 'langchain':
            return LangChainAssistant(self, data, client, 
                                      chat_history, app_type, 
                                      tools=tools, memory=memory).runnable()
        elif runtime == 'llama':
            raise NotImplementedError("LLama runtime is not supported")
        

    def datasource(self, datasource_id: int) -> AlitaDataSource:
        url = f"{self.datasources}/{datasource_id}"
        response = requests.get(url, headers=self.headers, verify=False)
        if not response.ok:
            raise Exception(f'Datasource request failed with code {response.status_code}\n{response.content}')
        data = response.json()
        ds_chat = data['version_details']['datasource_settings']['chat']
        if not ds_chat:
            raise Exception(f'Datasource with id {datasource_id} has missing model settings')
        datasource_model = ds_chat['chat_settings_embedding']
        chat_model = ds_chat['chat_settings_ai']
        return AlitaDataSource(self, datasource_id, data["name"], data["description"],
                               datasource_model, chat_model)

    def assistant(self, prompt_id: int, prompt_version_id: int,
                  tools: list, openai_tools: Optional[Dict] = None,
                  client: Optional[Any] = None, chat_history: Optional[list] = None):
        prompt = self.prompt(prompt_id=prompt_id, prompt_version_id=prompt_version_id, chat_history=chat_history)
        return LangChainAssistant(client, prompt, tools, openai_tools)

    def artifact(self, bucket_name):
        return Artifact(self, bucket_name)

    def _process_requst(self, data: requests.Response) -> Dict[str, str]:
        if data.status_code == 403:
            return {"error": "You are not authorized to access this resource"}
        elif data.status_code == 404:
            return {"error": "Resource not found"}
        elif data.status_code != 200:
            return {
                "error": "An error occurred while fetching the resource",
                "content": data.text
            }
        else:
            return data.json()

    def bucket_exists(self, bucket_name):
        try:
            resp = self._process_requst(
                requests.get(f'{self.bucket_url}', headers=self.headers, verify=False)
            )
            for each in resp.get('rows', []):
                if each['name'] == bucket_name:
                    return True
            return False
        except:
            return False

    def create_bucket(self, bucket_name, expiration_measure = "months", expiration_value = 1):
        post_data = {
            "name": bucket_name,
            "expiration_measure": expiration_measure,
            "expiration_value": expiration_value
        }
        resp = requests.post(f'{self.bucket_url}', headers=self.headers, json=post_data, verify=False)
        return self._process_requst(resp)

    def list_artifacts(self, bucket_name: str):
        url = f'{self.artifacts_url}/{bucket_name}'
        data = requests.get(url, headers=self.headers, verify=False)
        return self._process_requst(data)

    def create_artifact(self, bucket_name, artifact_name, artifact_data):
        url = f'{self.artifacts_url}/{bucket_name.lower()}'
        data = requests.post(url, headers=self.headers, files={
            'file': (artifact_name, artifact_data)
        }, verify=False)
        return self._process_requst(data)

    def download_artifact(self, bucket_name, artifact_name):
        url = f'{self.artifact_url}/{bucket_name}/{artifact_name}'
        data = requests.get(url, headers=self.headers, verify=False)
        if data.status_code == 403:
            return {"error": "You are not authorized to access this resource"}
        elif data.status_code == 404:
            return {"error": "Resource not found"}
        elif data.status_code != 200:
            return {
                "error": "An error occurred while fetching the resource",
                "content": data.content
            }
        return data.content

    def delete_artifact(self, bucket_name, artifact_name):
        url = f'{self.artifact_url}/{bucket_name}/{quote(artifact_name)}'
        data = requests.delete(url, headers=self.headers, verify=False)
        return self._process_requst(data)

    def _prepare_messages(self, messages: list[BaseMessage]):
        chat_history = []
        for message in messages:
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
        return chat_history

    def _prepare_payload(self, messages: list[BaseMessage], model_settings: dict, variables: list[dict]):
        chat_history = self._prepare_messages(messages)
        if not variables:
            variables = []
        return {
            "type": "chat",
            "project_id": self.project_id,
            "context": '',
            "model_settings": model_settings,
            "user_input": '',
            "messages": chat_history,
            "variables": variables,
            "format_response": True
        }

    def async_predict(self, messages: list[BaseMessage], model_settings: dict, variables: list[dict] = None):
        # TODO: Modify to make it appropriate stream response
        prompt_data = self._prepare_payload(messages, model_settings, variables)
        response = requests.post(self.predict_url, headers=self.headers, json=prompt_data, verify=False)
        logger.info(response.content)
        response_data = response.json()
        for message in response_data['messages']:
            if message.get('role') == 'user':
                yield HumanMessage(content=message['content'])
            else:
                yield AIMessage(content=message['content'])

    def predict(self, messages: list[BaseMessage], model_settings: dict, variables: list[dict] = None):
        prompt_data = self._prepare_payload(messages, model_settings, variables)
        response = requests.post(self.predict_url, headers=self.headers, json=prompt_data, verify=False)
        
        if response.status_code != 200:
            logger.error(f"Error in response of predict: {response.content}")
            raise requests.exceptions.HTTPError(response.content)
        try:
            response_data = response.json()
            response_messages = []
            for message in response_data['messages']:
                if message.get('type') == 'user':
                    response_messages.append(HumanMessage(content=message['content']))
                else:
                    response_messages.append(AIMessage(content=message['content']))
            return response_messages
        except TypeError:
            logger.error(f"TypeError in response of predict: {response.content}")
            raise

    def rag(self, datasource_id: int,
            user_input: Optional[str] = '',
            context: Optional[str] = None,
            chat_history: Optional[list] = None,
            datasource_settings: Optional[dict] = None,
            datasource_predict_settings: Optional[dict] = None):
        data = {
            "input": user_input,
            "chat_history": chat_history,
        }
        if context is not None:
            data["context"] = context
        if datasource_settings is not None:
            data["chat_settings_embedding"] = datasource_settings
        if datasource_predict_settings is not None:
            data["datasource_predict_settings"] = datasource_predict_settings
        headers = self.headers | {"Content-Type": "application/json"}
        response = requests.post(f"{self.datasources_predict}/{datasource_id}", headers=headers, json=data,
                                 verify=False).json()
        return AIMessage(content=response['response'], additional_kwargs={"references": response['references']})

    def search(self, datasource_id: int, messages: list[BaseMessage], datasource_settings: dict) -> AIMessage:
        chat_history = self._prepare_messages(messages)
        user_input = ''
        for message in chat_history[::-1]:
            if message['role'] == 'user':
                user_input = message['content']
                break
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
        response = requests.post(f"{self.datasources_search}/{datasource_id}", headers=headers, json=data, verify=False)
        if not response.ok:
            raise Exception(f'Search request failed with code {response.status_code}\n{response.content}')
        resp_data = response.json()
        # content = "\n\n".join([finding["page_content"] for finding in response["findings"]])
        content = resp_data["findings"]
        references = resp_data['references']
        return AIMessage(content=content, additional_kwargs={"references": references})
