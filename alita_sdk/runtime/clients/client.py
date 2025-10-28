import logging
from copy import deepcopy

import requests
from urllib.parse import quote

from typing import Dict, List, Any, Optional

from langchain_core.messages import (
    AIMessage, HumanMessage,
    SystemMessage, BaseMessage,
)
from langchain_core.tools import ToolException
from langgraph.store.base import BaseStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from ..langchain.assistant import Assistant as LangChainAssistant
# from ..llamaindex.assistant import Assistant as LLamaAssistant
from .prompt import AlitaPrompt
from .datasource import AlitaDataSource
from .artifact import Artifact
from ..langchain.chat_message_template import Jinja2TemplatedChatMessagesTemplate
from ..utils.utils import TOOLKIT_SPLITTER
from ...tools import get_available_toolkit_models

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
        self.llm_path = '/llm/v1'
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
        self.mcp_tools_list = f"{self.base_url}{self.api_path}/mcp_sse/tools_list/{self.project_id}"
        self.mcp_tools_call = f"{self.base_url}{self.api_path}/mcp_sse/tools_call/{self.project_id}"
        self.application_versions = f"{self.base_url}{self.api_path}/applications/version/prompt_lib/{self.project_id}"
        self.list_apps_url = f"{self.base_url}{self.api_path}/applications/applications/prompt_lib/{self.project_id}"
        self.integration_details = f"{self.base_url}{self.api_path}/integrations/integration/{self.project_id}"
        self.secrets_url = f"{self.base_url}{self.api_path}/secrets/secret/{self.project_id}"
        self.artifacts_url = f"{self.base_url}{self.api_path}/artifacts/artifacts/default/{self.project_id}"
        self.artifact_url = f"{self.base_url}{self.api_path}/artifacts/artifact/default/{self.project_id}"
        self.bucket_url = f"{self.base_url}{self.api_path}/artifacts/buckets/{self.project_id}"
        self.configurations_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=configurations&unsecret=true'
        self.ai_section_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=ai'
        self.image_generation_url = f"{self.base_url}{self.llm_path}/images/generations"
        self.configurations: list = configurations or []
        self.model_timeout = kwargs.get('model_timeout', 120)
        self.model_image_generation = kwargs.get('model_image_generation')

    def get_mcp_toolkits(self):
        if user_id := self._get_real_user_id():
            url = f"{self.mcp_tools_list}/{user_id}"
            data = requests.get(url, headers=self.headers, verify=False).json()
            return data
        else:
            return []

    def mcp_tool_call(self, params: dict[str, Any]):
        if user_id := self._get_real_user_id():
            url = f"{self.mcp_tools_call}/{user_id}"
            #
            # This loop iterates over each key-value pair in the arguments dictionary,
            # and if a value is a Pydantic object, it replaces it with its dictionary representation using .dict().
            for arg_name, arg_value in params.get('params', {}).get('arguments', {}).items():
                if isinstance(arg_value, list):
                    params['params']['arguments'][arg_name] = [
                        item.dict() if hasattr(item, "dict") and callable(item.dict) else item
                        for item in arg_value
                    ]
                elif hasattr(arg_value, "dict") and callable(arg_value.dict):
                    params['params']['arguments'][arg_name] = arg_value.dict()
            #
            response = requests.post(url, headers=self.headers, json=params, verify=False)
            try:
                return response.json()
            except (ValueError, TypeError):
                return response.text
        else:
            return f"Error: Could not determine user ID for MCP tool call"

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

    def get_embeddings(self, embedding_model: str) -> OpenAIEmbeddings:
        """
        Get an instance of OpenAIEmbeddings configured with the project ID and auth token.

        Returns:
            An instance of OpenAIEmbeddings configured for the project.
        """
        return OpenAIEmbeddings(
            base_url=f"{self.base_url}{self.llm_path}",
            model=embedding_model,
            api_key=self.auth_token,
            openai_organization=str(self.project_id),
            request_timeout=self.model_timeout
        )

    def get_llm(self, model_name: str, model_config: dict) -> ChatOpenAI:
        """
        Get a ChatOpenAI model instance based on the model name and configuration.

        Args:
            model_name: Name of the model to retrieve
            model_config: Configuration parameters for the model

        Returns:
            An instance of ChatOpenAI configured with the provided parameters.
        """
        if not model_name:
            raise ValueError("Model name must be provided")

        logger.info(f"Creating ChatOpenAI model: {model_name} with config: {model_config}")

        return ChatOpenAI(
            base_url=f"{self.base_url}{self.llm_path}",
            model=model_name,
            api_key=self.auth_token,
            streaming=model_config.get("streaming", True),
            stream_usage=model_config.get("stream_usage", True),
            max_tokens=model_config.get("max_tokens", None),
            temperature=model_config.get("temperature"),
            max_retries=model_config.get("max_retries", 3),
            seed=model_config.get("seed", None),
            openai_organization=str(self.project_id),
        )

    def generate_image(self,
                       prompt: str,
                       n: int = 1,
                       size: str = "auto",
                       quality: str = "auto",
                       response_format: str = "b64_json",
                       style: Optional[str] = None) -> dict:

        if not self.model_image_generation:
            raise ValueError("Image generation model is not configured for this client")

        image_generation_data = {
            "prompt": prompt,
            "model": self.model_image_generation,
            "n": n,
            "response_format": response_format,
        }

        # Only add optional parameters if they have meaningful values
        if size and size.lower() != "auto":
            image_generation_data["size"] = size

        if quality and quality.lower() != "auto":
            image_generation_data["quality"] = quality

        if style:
            image_generation_data["style"] = style

        # Standard headers for image generation
        image_headers = self.headers.copy()
        image_headers.update({
            "Content-Type": "application/json",
        })

        logger.info(f"Generating image with model: {self.model_image_generation}, prompt: {prompt[:50]}...")

        try:
            response = requests.post(
                self.image_generation_url,
                headers=image_headers,
                json=image_generation_data,
                verify=False,
                timeout=self.model_timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            logger.error(f"Image generation failed: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Image generation request failed: {e}")
            raise

    def get_app_version_details(self, application_id: int, application_version_id: int) -> dict:
        url = f"{self.application_versions}/{application_id}/{application_version_id}"
        if self.configurations:
            configs = self.configurations
        else:
            configs = self.fetch_available_configurations()

        resp = requests.patch(url, headers=self.headers, verify=False, json={'configurations': configs})
        if resp.ok:
            return resp.json()
        logger.error(f"Failed to fetch application version details: {resp.status_code} - {resp.text}."
                     f" Application ID: {application_id}, Version ID: {application_version_id}")
        raise ApiDetailsRequestError(f"Failed to fetch application version details for {application_id}/{application_version_id}.")

    def get_integration_details(self, integration_id: str, format_for_model: bool = False):
        url = f"{self.integration_details}/{integration_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data

    def unsecret(self, secret_name: str):
        url = f"{self.secrets_url}/{secret_name}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        logger.info(f"Unsecret response: {data}")
        return data.get('value', None)

    def application(self, application_id: int, application_version_id: int,
                    tools: Optional[list] = None, chat_history: Optional[List[Any]] = None,
                    app_type=None, memory=None, runtime='langchain',
                    application_variables: Optional[dict] = None,
                    version_details: Optional[dict] = None, store: Optional[BaseStore] = None,
                    llm: Optional[ChatOpenAI] = None):
        if tools is None:
            tools = []
        if chat_history is None:
            chat_history = []
        if version_details:
            data = version_details
        else:
            try:
                data = self.get_app_version_details(application_id, application_version_id)
            except ApiDetailsRequestError as e:
                error_msg = f"Failed to fetch application version details for {application_id}/{application_version_id}\nDetails: {e}"
                logger.error(error_msg)
                raise ToolException(error_msg)

        if application_variables:
            for var in data.get('variables', {}):
                if var['name'] in application_variables:
                    var.update(application_variables[var['name']])
        if llm is None:
            llm = self.get_llm(
                model_name=data['llm_settings']['model_name'],
                model_config={
                    "max_tokens": data['llm_settings']['max_tokens'],
                    "top_p": data['llm_settings']['top_p'],
                    "temperature": data['llm_settings']['temperature'],
                    "model_project_id": data['llm_settings'].get('model_project_id'),
                }
            )
        if not app_type:
            app_type = data.get("agent_type", "react")
        if app_type == "alita":
            app_type = "react"
        elif app_type == "llama":
            app_type = "react"
        elif app_type == "dial":
            app_type = "react"
        elif app_type == 'autogen':
            app_type = "react"
        if runtime == 'nonrunnable':
            return LangChainAssistant(self, data, llm, chat_history, app_type,
                                      tools=tools, memory=memory, store=store)
        if runtime == 'langchain':
            return LangChainAssistant(self, data, llm,
                                      chat_history, app_type,
                                      tools=tools, memory=memory, store=store).runnable()
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
        # Ensure bucket name is lowercase as required by the API
        url = f'{self.artifacts_url}/{bucket_name.lower()}'
        data = requests.get(url, headers=self.headers, verify=False)
        return self._process_requst(data)

    def create_artifact(self, bucket_name, artifact_name, artifact_data):
        url = f'{self.artifacts_url}/{bucket_name.lower()}'
        data = requests.post(url, headers=self.headers, files={
            'file': (artifact_name, artifact_data)
        }, verify=False)
        return self._process_requst(data)

    def download_artifact(self, bucket_name, artifact_name):
        url = f'{self.artifact_url}/{bucket_name.lower()}/{artifact_name}'
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
        url = f'{self.artifact_url}/{bucket_name}'
        data = requests.delete(url, headers=self.headers, verify=False, params={'filename': quote(artifact_name)})
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
                if message.get('role') == 'user':
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

    def _get_real_user_id(self):
        try:
            import tasknode_task # pylint: disable=E0401
            monitoring_meta = tasknode_task.meta.get("monitoring", {})
            return monitoring_meta["user_id"]
        except Exception as e:
            logger.warning(f"Error: Could not determine user ID for MCP tool: {e}")
            return None

    def predict_agent(self, llm: ChatOpenAI, instructions: str = "You are a helpful assistant.",
                      tools: Optional[list] = None, chat_history: Optional[List[Any]] = None,
                      memory=None, runtime='langchain', variables: Optional[list] = None,
                      store: Optional[BaseStore] = None, debug_mode: Optional[bool] = False):
        """
        Create a predict-type agent with minimal configuration.

        Args:
            llm: The LLM to use
            instructions: System instructions for the agent
            tools: Optional list of tools to provide to the agent
            chat_history: Optional chat history
            memory: Optional memory/checkpointer
            runtime: Runtime type (default: 'langchain')
            variables: Optional list of variables for the agent
            store: Optional store for memory
            debug_mode: Enable debug mode for cases when assistant can be initialized without tools

        Returns:
            Runnable agent ready for execution
        """
        if tools is None:
            tools = []
        if chat_history is None:
            chat_history = []
        if variables is None:
            variables = []

        # Create a minimal data structure for predict agent
        # All LLM settings are taken from the passed client instance
        agent_data = {
            'instructions': instructions,
            'tools': tools,  # Tools are handled separately in predict agents
            'variables': variables
        }
        return LangChainAssistant(self, agent_data, llm,
                                  chat_history, "predict", memory=memory, store=store, debug_mode=debug_mode).runnable()

    def test_toolkit_tool(self, toolkit_config: dict, tool_name: str, tool_params: dict = None,
                          runtime_config: dict = None, llm_model: str = None,
                          llm_config: dict = None) -> dict:
        """
        Test a single tool from a toolkit with given parameters and runtime callbacks.

        This method initializes a toolkit, calls a specific tool, and supports runtime
        callbacks for event dispatching, enabling tools to send custom events back to
        the platform during execution.

        Args:
            toolkit_config: Configuration dictionary for the toolkit containing:
                - toolkit_name: Name of the toolkit (e.g., 'github', 'jira')
                - settings: Dictionary containing toolkit-specific settings
            tool_name: Name of the specific tool to call
            tool_params: Parameters to pass to the tool (default: empty dict)
            runtime_config: Runtime configuration with callbacks for events, containing:
                - callbacks: List of callback handlers for event processing
                - configurable: Additional configuration parameters
                - tags: Tags for the execution
            llm_model: Name of the LLM model to use (default: 'gpt-4o-mini')
            llm_config: Configuration for the LLM containing:
                - max_tokens: Maximum tokens for response (default: 1000)
                - temperature: Temperature for response generation (default: 0.1)
                - top_p: Top-p value for response generation (default: 1.0)

        Returns:
            Dictionary containing:
                - success: Boolean indicating if the operation was successful
                - result: The actual result from the tool (if successful)
                - error: Error message (if unsuccessful)
                - tool_name: Name of the executed tool
                - toolkit_config: Original toolkit configuration
                - events_dispatched: List of custom events dispatched during execution
                - llm_model: LLM model used for the test
                - execution_time_seconds: Time taken to execute the tool in seconds

        Example:
            >>> from langchain_core.callbacks import BaseCallbackHandler
            >>>
            >>> class TestCallback(BaseCallbackHandler):
            ...     def __init__(self):
            ...         self.events = []
            ...     def on_custom_event(self, name, data, **kwargs):
            ...         self.events.append({'name': name, 'data': data})
            >>>
            >>> callback = TestCallback()
            >>> runtime_config = {'callbacks': [callback]}
            >>>
            >>> config = {
            ...     'toolkit_name': 'github',
            ...     'settings': {'github_token': 'your_token'}
            ... }
            >>> result = client.test_toolkit_tool(
            ...     config, 'get_repository_info',
            ...     {'repo_name': 'alita'}, runtime_config,
            ...     llm_model='gpt-4o-mini',
            ...     llm_config={'temperature': 0.1}
            ... )
        """
        if tool_params is None:
            tool_params = {}
        if llm_model is None:
            llm_model = 'gpt-4o-mini'
        if llm_config is None:
            llm_config = {
                'max_tokens': 1024,
                'temperature': 0.1,
                'top_p': 1.0
            }
        import logging
        logger = logging.getLogger(__name__)
        toolkit_config_parsed_json = None
        events_dispatched = []

        try:
            toolkit_config_type = toolkit_config.get('type')
            available_toolkit_models = get_available_toolkit_models().get(toolkit_config_type)
            toolkit_config_parsed_json = deepcopy(toolkit_config)
            if available_toolkit_models:
                toolkit_class = available_toolkit_models['toolkit_class']
                toolkit_config_model_class = toolkit_class.toolkit_config_schema()
                toolkit_config_validated_settings = toolkit_config_model_class(
                    **toolkit_config.get('settings', {})
                ).model_dump(mode='json')
                toolkit_config_parsed_json['settings'] = toolkit_config_validated_settings
            else:
                logger.warning(f"Toolkit type '{toolkit_config_type}' is skipping model validation")
                toolkit_config_parsed_json['settings'] = None
        except Exception as toolkit_config_error:
            logger.error(f"Failed to validate toolkit configuration: {str(toolkit_config_error)}")
            return {
                "success": False,
                "error": f"Failed to validate toolkit configuration: {str(toolkit_config_error)}",
                "tool_name": tool_name,
                "toolkit_config": None,
                "llm_model": llm_model,
                "events_dispatched": events_dispatched,
                "execution_time_seconds": 0.0
            }

        try:
            from ..utils.toolkit_utils import instantiate_toolkit_with_client
            from langchain_core.runnables import RunnableConfig
            import logging
            import time

            logger.info(f"Testing tool '{tool_name}' from toolkit '{toolkit_config.get('toolkit_name')}' with LLM '{llm_model}'")

            # Create RunnableConfig for callback support
            config = None
            callbacks = []

            if runtime_config:
                callbacks = runtime_config.get('callbacks', [])
                if callbacks:
                    config = RunnableConfig(
                        callbacks=callbacks,
                        configurable=runtime_config.get('configurable', {}),
                        tags=runtime_config.get('tags', [])
                    )

            # Create LLM instance using the client's get_llm method
            try:
                llm = self.get_llm(llm_model, llm_config)
                logger.info(f"Created LLM instance: {llm_model} with config: {llm_config}")
            except Exception as llm_error:
                logger.error(f"Failed to create LLM instance: {str(llm_error)}")
                return {
                    "success": False,
                    "error": f"Failed to create LLM instance '{llm_model}': {str(llm_error)}",
                    "tool_name": tool_name,
                    "toolkit_config": toolkit_config_parsed_json,
                    "llm_model": llm_model,
                    "events_dispatched": events_dispatched,
                    "execution_time_seconds": 0.0
                }

            # Instantiate the toolkit with client and LLM support
            tools = instantiate_toolkit_with_client(toolkit_config, llm, self)

            if not tools:
                return {
                    "success": False,
                    "error": f"Failed to instantiate toolkit '{toolkit_config.get('toolkit_name')}' or no tools found",
                    "tool_name": tool_name,
                    "toolkit_config": toolkit_config_parsed_json,
                    "llm_model": llm_model,
                    "events_dispatched": events_dispatched,
                    "execution_time_seconds": 0.0
                }

            # Find the specific tool with smart name matching
            target_tool = None
            toolkit_name = toolkit_config.get('toolkit_name', '').lower()

            # Helper function to extract base tool name from full name
            def extract_base_tool_name(full_name: str) -> str:
                """Extract base tool name from toolkit___toolname format."""
                if '___' in full_name:
                    return full_name.split('___', 1)[1]
                return full_name

            # Helper function to create full tool name
            def create_full_tool_name(base_name: str, toolkit_name: str) -> str:
                """Create full tool name in toolkit___toolname format."""
                return f"{toolkit_name}___{base_name}"

            # Normalize tool_name to handle both formats
            # If user provides toolkit___toolname, extract just the tool name
            # If user provides just toolname, keep as is
            if '___' in tool_name:
                normalized_tool_name = extract_base_tool_name(tool_name)
                logger.info(f"Extracted base tool name '{normalized_tool_name}' from full name '{tool_name}'")
            else:
                normalized_tool_name = tool_name

            # Try multiple matching strategies
            for tool in tools:
                tool_name_attr = None
                if hasattr(tool, 'name'):
                    tool_name_attr = tool.name
                elif hasattr(tool, 'func') and hasattr(tool.func, '__name__'):
                    tool_name_attr = tool.func.__name__

                if tool_name_attr:
                    # Strategy 1: Exact match with provided name (handles both formats)
                    if tool_name_attr == tool_name:
                        target_tool = tool
                        logger.info(f"Found tool using exact match: '{tool_name_attr}'")
                        break

                    # Strategy 2: Match normalized name with toolkit prefix
                    expected_full_name = create_full_tool_name(normalized_tool_name, toolkit_name)
                    if tool_name_attr == expected_full_name:
                        target_tool = tool
                        logger.info(f"Found tool using toolkit prefix mapping: '{tool_name_attr}' for normalized name '{normalized_tool_name}'")
                        break

                    # Strategy 3: Match base names (extract from both sides)
                    base_tool_name = extract_base_tool_name(tool_name_attr)
                    if base_tool_name == normalized_tool_name:
                        target_tool = tool
                        logger.info(f"Found tool using base name mapping: '{tool_name_attr}' -> '{base_tool_name}' matches '{normalized_tool_name}'")
                        break

                    # Strategy 4: Match provided name with base tool name (reverse lookup)
                    if tool_name_attr == normalized_tool_name:
                        target_tool = tool
                        logger.info(f"Found tool using direct name match: '{tool_name_attr}' matches normalized '{normalized_tool_name}'")
                        break

            if target_tool is None:
                available_tools = []
                base_available_tools = []
                full_available_tools = []

                for tool in tools:
                    tool_name_attr = None
                    if hasattr(tool, 'name'):
                        tool_name_attr = tool.name
                    elif hasattr(tool, 'func') and hasattr(tool.func, '__name__'):
                        tool_name_attr = tool.func.__name__

                    if tool_name_attr:
                        available_tools.append(tool_name_attr)

                        # Extract base name for user-friendly error
                        base_name = extract_base_tool_name(tool_name_attr)
                        if base_name not in base_available_tools:
                            base_available_tools.append(base_name)

                        # Track full names separately
                        if TOOLKIT_SPLITTER in tool_name_attr:
                            full_available_tools.append(tool_name_attr)

                # Create comprehensive error message
                error_msg = f"Tool '{tool_name}' not found in toolkit '{toolkit_config.get('toolkit_name')}'."

                if base_available_tools and full_available_tools:
                    error_msg += f" Available tools: {base_available_tools} (base names) or {full_available_tools} (full names)"
                elif base_available_tools:
                    error_msg += f" Available tools: {base_available_tools}"
                elif available_tools:
                    error_msg += f" Available tools: {available_tools}"
                else:
                    error_msg += " No tools found in the toolkit."

                # Add helpful hint about naming conventions
                if '___' in tool_name:
                    error_msg += f" Note: You provided a full name '{tool_name}'. Try using just the base name '{extract_base_tool_name(tool_name)}'."
                elif full_available_tools:
                    possible_full_name = create_full_tool_name(tool_name, toolkit_name)
                    error_msg += f" Note: You provided a base name '{tool_name}'. The full name might be '{possible_full_name}'."

                return {
                    "success": False,
                    "error": error_msg,
                    "tool_name": tool_name,
                    "toolkit_config": toolkit_config_parsed_json,
                    "llm_model": llm_model,
                    "events_dispatched": events_dispatched,
                    "execution_time_seconds": 0.0
                }

            # Execute the tool with callback support
            try:
                # Log which tool was found and how
                actual_tool_name = getattr(target_tool, 'name', None) or getattr(target_tool.func, '__name__', 'unknown')

                # Determine which matching strategy was used
                if actual_tool_name == tool_name:
                    logger.info(f"Found tool '{tool_name}' using exact match")
                elif actual_tool_name == create_full_tool_name(normalized_tool_name, toolkit_name):
                    logger.info(f"Found tool '{tool_name}' using toolkit prefix mapping ('{actual_tool_name}' for normalized '{normalized_tool_name}')")
                elif extract_base_tool_name(actual_tool_name) == normalized_tool_name:
                    logger.info(f"Found tool '{tool_name}' using base name mapping ('{actual_tool_name}' -> '{extract_base_tool_name(actual_tool_name)}')")
                elif actual_tool_name == normalized_tool_name:
                    logger.info(f"Found tool '{tool_name}' using direct normalized name match ('{actual_tool_name}')")
                else:
                    logger.info(f"Found tool '{tool_name}' using fallback matching ('{actual_tool_name}')")

                logger.info(f"Executing tool '{tool_name}' (internal name: '{actual_tool_name}') with parameters: {tool_params}")

                # Start timing the tool execution
                start_time = time.time()

                # Different tools might have different invocation patterns
                if hasattr(target_tool, 'invoke'):
                    # Use config for tools that support RunnableConfig
                    if config is not None:
                        result = target_tool.invoke(tool_params, config=config)
                    else:
                        result = target_tool.invoke(tool_params)
                elif hasattr(target_tool, 'run'):
                    result = target_tool.run(tool_params)
                elif callable(target_tool):
                    result = target_tool(**tool_params)
                else:
                    execution_time = time.time() - start_time
                    return {
                        "success": False,
                        "error": f"Tool '{tool_name}' is not callable",
                        "tool_name": tool_name,
                        "toolkit_config": toolkit_config_parsed_json,
                        "llm_model": llm_model,
                        "events_dispatched": events_dispatched,
                        "execution_time_seconds": execution_time
                    }

                # Calculate execution time
                execution_time = time.time() - start_time

                # Extract events from callbacks if they support it
                for callback in callbacks:
                    if hasattr(callback, 'events'):
                        events_dispatched.extend(callback.events)
                    elif hasattr(callback, 'get_events'):
                        events_dispatched.extend(callback.get_events())
                    elif hasattr(callback, 'dispatched_events'):
                        events_dispatched.extend(callback.dispatched_events)

                logger.info(f"Tool '{tool_name}' executed successfully in {execution_time:.3f} seconds")

                return {
                    "success": True,
                    "result": result,
                    "tool_name": tool_name,
                    "toolkit_config": toolkit_config_parsed_json,
                    "llm_model": llm_model,
                    "events_dispatched": events_dispatched,
                    "execution_time_seconds": execution_time
                }

            except Exception as tool_error:
                # Calculate execution time even for failed executions
                execution_time = time.time() - start_time
                logger.error(f"Error executing tool '{tool_name}' after {execution_time:.3f} seconds: {str(tool_error)}")

                # Still collect events even if tool execution failed
                for callback in callbacks:
                    if hasattr(callback, 'events'):
                        events_dispatched.extend(callback.events)
                    elif hasattr(callback, 'get_events'):
                        events_dispatched.extend(callback.get_events())
                    elif hasattr(callback, 'dispatched_events'):
                        events_dispatched.extend(callback.dispatched_events)

                return {
                    "success": False,
                    "error": f"Tool execution failed: {str(tool_error)}",
                    "tool_name": tool_name,
                    "toolkit_config": toolkit_config_parsed_json,
                    "llm_model": llm_model,
                    "events_dispatched": events_dispatched,
                    "execution_time_seconds": execution_time
                }

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error in test_toolkit_tool: {str(e)}")
            return {
                "success": False,
                "error": f"Method execution failed: {str(e)}",
                "tool_name": tool_name,
                "toolkit_config": toolkit_config_parsed_json,
                "llm_model": llm_model if 'llm_model' in locals() else None,
                "events_dispatched": [],
                "execution_time_seconds": 0.0
            }
