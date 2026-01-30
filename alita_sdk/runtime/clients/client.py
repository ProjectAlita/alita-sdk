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
from langchain_anthropic import ChatAnthropic

from ..langchain.assistant import Assistant as LangChainAssistant
from .artifact import Artifact
from ..langchain.chat_message_template import Jinja2TemplatedChatMessagesTemplate
from ..utils.mcp_oauth import McpAuthorizationRequired
from ...tools import get_available_toolkit_models, instantiate_toolkit
from ...tools.base_indexer_toolkit import IndexTools

logger = logging.getLogger(__name__)


# Canonical app_type values
APP_TYPE_AGENT = "agent"      # Standard LangGraph react agent with tools
APP_TYPE_PIPELINE = "pipeline"  # Graph-based workflow agent
APP_TYPE_PREDICT = "predict"    # Special agent without memory store

# Legacy app_type mappings for backwards compatibility
_APP_TYPE_ALIASES = {
    "react": APP_TYPE_AGENT,
    "openai": APP_TYPE_AGENT,
    "alita": APP_TYPE_AGENT,
    "llama": APP_TYPE_AGENT,
    "dial": APP_TYPE_AGENT,
    "autogen": APP_TYPE_AGENT,
    # Canonical types map to themselves
    "agent": APP_TYPE_AGENT,
    "pipeline": APP_TYPE_PIPELINE,
    "predict": APP_TYPE_PREDICT,
}


def normalize_app_type(app_type: str) -> str:
    """
    Normalize app_type to canonical value.

    Canonical types:
    - 'agent': Standard LangGraph react agent (replaces react, openai, alita, llama, dial, autogen)
    - 'pipeline': Graph-based workflow agent
    - 'predict': Special agent without memory store

    Args:
        app_type: Raw app_type string from API or config

    Returns:
        Normalized canonical app_type
    """
    normalized = _APP_TYPE_ALIASES.get(app_type, APP_TYPE_AGENT)
    if app_type and app_type != normalized:
        logger.debug(f"Normalized app_type '{app_type}' -> '{normalized}'")
    return normalized


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
        self.api_v2_path = '/api/v2'
        self.llm_path = '/llm/v1'
        self.allm_path = '/llm'
        self.project_id = project_id
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            'X-SECRET': kwargs.get('XSECRET', 'secret')
        }
        if api_extra_headers is not None:
            self.headers.update(api_extra_headers)
        self.predict_url = f"{self.base_url}{self.api_path}/prompt_lib/predict/prompt_lib/{self.project_id}"
        self.base_app_url = f"{self.base_url}{self.api_v2_path}/elitea_core/application/prompt_lib/"
        self.base_public_app_url = f"{self.base_url}{self.api_path}/applications/public_application/prompt_lib/"
        self.app = f"{self.base_app_url}{self.project_id}"
        self.mcp_tools_list = f"{self.base_url}{self.api_path}/mcp_sse/tools_list/{self.project_id}"
        self.mcp_tools_call = f"{self.base_url}{self.api_path}/mcp_sse/tools_call/{self.project_id}"
        self.application_versions = f"{self.base_url}{self.api_path}/applications/version/prompt_lib/{self.project_id}"
        self.list_apps_url = f"{self.base_url}{self.api_path}/applications/applications/prompt_lib/{self.project_id}"
        self.integration_details = f"{self.base_url}{self.api_path}/integrations/integration/{self.project_id}"
        self.secrets_url = f"{self.base_url}{self.api_path}/secrets/secret/{self.project_id}"
        self.artifacts_url = f"{self.base_url}{self.api_v2_path}/artifacts/artifacts/default/{self.project_id}"
        self.artifact_url = f"{self.base_url}{self.api_v2_path}/artifacts/artifact/default/{self.project_id}"
        self.artifact_by_id_url = f"{self.base_url}{self.api_v2_path}/artifacts/artifact_id/default/{self.project_id}"
        self.bucket_url = f"{self.base_url}{self.api_v2_path}/artifacts/buckets/{self.project_id}"
        self.configurations_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=configurations&unsecret=true'
        self.ai_section_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=ai'
        self.models_url = f'{self.base_url}{self.api_path}/configurations/models/{self.project_id}?include_shared=true'
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

    def get_app_details(self, application_id: int, version_name: Optional[str] = None):
        url = f"{self.app}/{application_id}" if version_name is None else f"{self.app}/{application_id}/{version_name}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data


    def get_public_app_details(self, application_id: int, version_name: str = None) -> dict:
        """
        Get application details from the public project.

        Uses the public_application endpoint which auto-resolves to the public project.
        This is used when accessing applications from public projects that the current
        user may not have direct access to.

        Args:
            application_id: The ID of the application to fetch
            version_name: Optional specific version name. If not provided, gets latest published.

        Returns:
            dict with application details including 'version_details' for the published version

        Raises:
            ApiDetailsRequestError: If the application is not found or has no published version
        """
        url = f"{self.base_public_app_url}{application_id}"
        if version_name:
            url = f"{url}/{version_name}"

        resp = requests.get(url, headers=self.headers, verify=False)
        if resp.ok:
            data = resp.json()
            logger.info(f"[PUBLIC_APP] Successfully fetched public app {application_id}: {data.get('name')}")
            return data

        logger.error(f"[PUBLIC_APP] Failed to fetch public application: {resp.status_code} - {resp.text}. "
                    f"Application ID: {application_id}")
        raise ApiDetailsRequestError(
            f"Failed to fetch public application {application_id}. "
            f"Application may not exist or may not have a published version."
        )

    def toolkit(self, toolkit_id: int):
        url = f"{self.base_url}{self.api_path}/tool/prompt_lib/{self.project_id}/{toolkit_id}"
        response = requests.get(url, headers=self.headers, verify=False)
        if not response.ok:
            raise ValueError(f"Failed to fetch toolkit {toolkit_id}: {response.text}")
        
        tool_data = response.json()
        if 'settings' not in tool_data:
            tool_data['settings'] = {}
        tool_data['settings']['alita'] = self
        
        return instantiate_toolkit(tool_data)

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

    def get_available_models(self):
        """Get list of available models from the configurations API.

        Returns:
            List of model dictionaries with 'name' and other properties,
            or empty list if request fails.
        """
        resp = requests.get(self.models_url, headers=self.headers, verify=False)
        if resp.ok:
            data = resp.json()
            # API returns {"items": [...], ...}
            return data.get('items', [])
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

    def get_llm(self, model_name: str, model_config: dict):
        """
        Get a ChatOpenAI or ChatAnthropic model instance based on the model name and configuration.

        Args:
            model_name: Name of the model to retrieve
            model_config: Configuration parameters for the model

        Returns:
            An instance of ChatOpenAI or ChatAnthropic configured with the provided parameters.
        """
        if not model_name:
            raise ValueError("Model name must be provided")

        # Determine if this is an Anthropic model
        model_name_lower = model_name.lower()
        is_anthropic = "anthropic" in model_name_lower or "claude" in model_name_lower

        logger.info(f"Creating {'ChatAnthropic' if is_anthropic else 'ChatOpenAI'} model: {model_name} with config: {model_config}")

        try:
            from tools import this  # pylint: disable=E0401,C0415
            worker_config = this.for_module("indexer_worker").descriptor.config
        except:  # pylint: disable=W0702
            worker_config = {}

        use_responses_api = False

        if worker_config and isinstance(worker_config, dict):
            for target_name_tag in worker_config.get("use_responses_api_for", []):
                if target_name_tag in model_name:
                    use_responses_api = True
                    break

        # handle case when max_tokens are auto-configurable == -1 or None
        llm_max_tokens = model_config.get("max_tokens", None)
        if llm_max_tokens is None or llm_max_tokens == -1:
            logger.warning(f'User selected `MAX COMPLETION TOKENS` as `auto` or value is None/missing')
            # default number for a case when auto is selected for an agent
            llm_max_tokens = 4000

        if is_anthropic:
            # ChatAnthropic configuration
            # Anthropic requires max_tokens to be an integer, never None
            target_kwargs = {
                "base_url": f"{self.base_url}{self.allm_path}",
                "model": model_name,
                "api_key": self.auth_token,
                "streaming": model_config.get("streaming", True),
                "max_tokens": llm_max_tokens,  # Always an integer now
                "temperature": model_config.get("temperature"),
                "max_retries": model_config.get("max_retries", 3),
                "default_headers": {"openai-organization": str(self.project_id),
                                    "Authorization": f"Bearer {self.auth_token}"},
            }
            
            # TODO": Check on ChatAnthropic client when they get "effort" support back
            if model_config.get("reasoning_effort"):
                if model_config["reasoning_effort"].lower() == "low":
                    target_kwargs['thinking'] = {"type": "enabled", "budget_tokens": 2048}
                    target_kwargs['temperature'] = 1
                    target_kwargs["max_tokens"] = 2048 + target_kwargs["max_tokens"]
                elif model_config["reasoning_effort"].lower() == "medium":
                    target_kwargs['thinking'] = {"type": "enabled", "budget_tokens": 4096}
                    target_kwargs['temperature'] = 1
                    target_kwargs["max_tokens"] = 4096 + target_kwargs["max_tokens"]
                elif model_config["reasoning_effort"].lower() == "high":
                    target_kwargs['thinking'] = {"type": "enabled", "budget_tokens": 9092}
                    target_kwargs['temperature'] = 1
                    target_kwargs["max_tokens"] = 9092 + target_kwargs["max_tokens"]
                    
            # Add http_client if provided
            if "http_client" in model_config:
                target_kwargs["http_client"] = model_config["http_client"]
            
            llm = ChatAnthropic(**target_kwargs)
        else:
            # ChatOpenAI configuration
            target_kwargs = {
                "base_url": f"{self.base_url}{self.llm_path}",
                "model": model_name,
                "api_key": self.auth_token,
                "streaming": model_config.get("streaming", True),
                "stream_usage": model_config.get("stream_usage", True),
                "max_tokens": llm_max_tokens,
                "temperature": model_config.get("temperature"),
                "reasoning_effort": model_config.get("reasoning_effort"),
                "max_retries": model_config.get("max_retries", 3),
                "seed": model_config.get("seed", None),
                "openai_organization": str(self.project_id),
            }

            if use_responses_api:
                target_kwargs["use_responses_api"] = True
            
            llm = ChatOpenAI(**target_kwargs)
        return llm
        
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
        """Get application version details for the client's project."""
        url = f"{self.base_url}{self.api_path}/applications/version/prompt_lib/{self.project_id}/{application_id}/{application_version_id}"
        if self.configurations:
            configs = self.configurations
        else:
            configs = self.fetch_available_configurations()

        resp = requests.patch(url, headers=self.headers, verify=False, json={'configurations': configs})
        if resp.ok:
            return resp.json()
        logger.error(f"Failed to fetch application version details: {resp.status_code} - {resp.text}."
                     f" Application ID: {application_id}, Version ID: {application_version_id}, Project ID: {self.project_id}")
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
                    llm: Optional[ChatOpenAI] = None, mcp_tokens: Optional[dict] = None,
                    conversation_id: Optional[str] = None, ignored_mcp_servers: Optional[list] = None,
                    is_subgraph: bool = False, middleware: Optional[list] = None):
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
            max_tokens = data['llm_settings'].get('max_tokens', 4000)
            if max_tokens == -1:
                # default nuber for case when auto is selected for agent
                max_tokens = 4000
            llm = self.get_llm(
                model_name=data['llm_settings']['model_name'],
                model_config={
                    "max_tokens": max_tokens,
                    "reasoning_effort": data['llm_settings'].get('reasoning_effort'),
                    "temperature": data['llm_settings']['temperature'],
                    "model_project_id": data['llm_settings'].get('model_project_id'),
                }
            )
        # Normalize app_type to canonical value (agent, pipeline, or predict)
        if not app_type:
            app_type = data.get("agent_type", "agent")
        app_type = normalize_app_type(app_type)

        # Auto-create middleware based on internal_tools configuration
        # This bridges the UI's internal_tools toggles to the middleware system
        middleware_list = list(middleware) if middleware else []
        internal_tools = data.get('meta', {}).get('internal_tools', [])
        if 'planner' in internal_tools:
            # Create PlanningMiddleware when planner is enabled in internal_tools
            from ..middleware.planning import PlanningMiddleware
            planning_middleware = PlanningMiddleware(
                conversation_id=conversation_id,
                connection_string=None,  # Uses filesystem storage by default
            )
            middleware_list.append(planning_middleware)
            logger.info(f"Auto-created PlanningMiddleware for conversation_id={conversation_id}")

        # Extract lazy_tools_mode from internal_tools (it's a mode flag, not an actual tool)
        # UI stores it in meta.internal_tools array, not as meta.lazy_tools_mode boolean
        lazy_tools_mode = 'lazy_tools_mode' in internal_tools

        # LangChainAssistant constructor calls get_tools() which may raise McpAuthorizationRequired
        # The exception will propagate naturally to the indexer worker's outer handler
        if runtime == 'nonrunnable':
            return LangChainAssistant(self, data, llm, chat_history, app_type,
                                      tools=tools, memory=memory, store=store, mcp_tokens=mcp_tokens,
                                      conversation_id=conversation_id, ignored_mcp_servers=ignored_mcp_servers,
                                      is_subgraph=is_subgraph,
                                      middleware=middleware_list if middleware_list else None,
                                      lazy_tools_mode=lazy_tools_mode)
        if runtime == 'langchain':
            return LangChainAssistant(self, data, llm,
                                      chat_history, app_type,
                                      tools=tools, memory=memory, store=store, mcp_tokens=mcp_tokens,
                                      conversation_id=conversation_id, ignored_mcp_servers=ignored_mcp_servers,
                                      is_subgraph=is_subgraph,
                                      middleware=middleware_list if middleware_list else None,
                                      lazy_tools_mode=lazy_tools_mode).runnable()
        elif runtime == 'llama':
            raise NotImplementedError("LLama runtime is not supported")

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

    def create_artifact(self, bucket_name, artifact_name, artifact_data, source: str = 'generated', prompt: str = None):
        # Sanitize filename to prevent regex errors during indexing
        sanitized_name, was_modified = self._sanitize_artifact_name(artifact_name)
        if was_modified:
            logger.warning(f"Artifact filename sanitized: '{artifact_name}' -> '{sanitized_name}'")
        
        url = f'{self.artifacts_url}/{bucket_name.lower()}'
        form_data = {'source': source}
        if prompt:
            form_data['prompt'] = prompt
        data = requests.post(url, headers=self.headers, files={
            'file': (sanitized_name, artifact_data)
        }, data=form_data, verify=False)
        return self._process_requst(data)
    
    @staticmethod
    def _parse_content_disposition(header: str) -> str:
        """Parse filename from Content-Disposition header."""
        if not header:
            return ""

        # Try to extract filename from header
        # Format: 'inline; filename="image.png"' or 'attachment; filename="image.png"'
        import re

        # Try filename*= first (RFC 5987 extended format)
        match = re.search(r"filename\*=(?:UTF-8'')?([^;]+)", header)
        if match:
            from urllib.parse import unquote
            return unquote(match.group(1).strip('"\''))

        # Try regular filename=
        match = re.search(r'filename="?([^";]+)"?', header)
        if match:
            return match.group(1).strip('"\'')

        return ""

    def download_artifact_by_id(self, artifact_id: str) -> tuple:
        """Download artifact by ID and return (file_bytes, filename) tuple."""
        url = f"{self.artifact_by_id_url}/{artifact_id}"
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

        # Extract filename from Content-Disposition header
        content_disposition = data.headers.get('Content-Disposition', '')
        filename = self._parse_content_disposition(content_disposition)

        # Fallback filename if header parsing fails
        if not filename:
            # Try to detect extension from file content
            try:
                import filetype
                kind = filetype.guess(data.content)
                extension = f".{kind.extension}" if kind else ""
            except Exception:
                extension = ""

            filename = f"file_{artifact_id[:8]}{extension}"

        return data.content, filename

    @staticmethod
    def _sanitize_artifact_name(filename: str) -> tuple:
        """Sanitize filename for safe storage and regex pattern matching."""
        import re
        from pathlib import Path
        
        if not filename or not filename.strip():
            return "unnamed_file", True
        
        original = filename
        path_obj = Path(filename)
        name = path_obj.stem
        extension = path_obj.suffix
        
        # Whitelist: alphanumeric, underscore, hyphen, space, Unicode letters/digits
        sanitized_name = re.sub(r'[^\w\s-]', '', name, flags=re.UNICODE)
        sanitized_name = re.sub(r'[-\s]+', '-', sanitized_name)
        sanitized_name = sanitized_name.strip('-').strip()
        
        if not sanitized_name:
            sanitized_name = "file"
        
        if extension:
            extension = re.sub(r'[^\w.-]', '', extension, flags=re.UNICODE)
        
        sanitized = sanitized_name + extension
        return sanitized, (sanitized != original)

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

    def _get_real_user_id(self):
        try:
            import tasknode_task # pylint: disable=E0401
            monitoring_meta = tasknode_task.meta.get("monitoring", {})
            return monitoring_meta["user_id"]
        except Exception as e:
            logger.debug(f"Error: Could not determine user ID for MCP tool: {e}")
            return None

    def predict_agent(self, llm: ChatOpenAI, instructions: str = "You are a helpful assistant.",
                      tools: Optional[list] = None, chat_history: Optional[List[Any]] = None,
                      memory=None, runtime='langchain', variables: Optional[list] = None,
                      store: Optional[BaseStore] = None, debug_mode: Optional[bool] = False,
                      mcp_tokens: Optional[dict] = None, conversation_id: Optional[str] = None,
                      ignored_mcp_servers: Optional[list] = None, persona: Optional[str] = "generic",
                      lazy_tools_mode: Optional[bool] = False, internal_tools: Optional[list] = None):
        """
        Create a predict-type agent with minimal configuration.

        Args:
            llm: The LLM to use
            instructions: System instructions for the agent
            tools: Optional list of tool configurations (not tool instances) to provide to the agent.
                   Tool configs will be processed through get_tools() to create tool instances.
                   Each tool config should have 'type', 'settings', etc.
            chat_history: Optional chat history
            memory: Optional memory/checkpointer
            runtime: Runtime type (default: 'langchain')
            variables: Optional list of variables for the agent
            store: Optional store for memory
            debug_mode: Enable debug mode for cases when assistant can be initialized without tools
            ignored_mcp_servers: Optional list of MCP server URLs to ignore (user chose to continue without auth)
            persona: Default persona for chat: 'generic' or 'qa' (default: 'generic')
            lazy_tools_mode: Enable lazy tools mode to reduce token usage with many toolkits (default: False)
            internal_tools: Optional list of internal tool names (e.g., ['swarm', 'planner']).
                           Enables special modes like swarm for multi-agent collaboration.

        Returns:
            Runnable agent ready for execution
        """
        if tools is None:
            tools = []
        if chat_history is None:
            chat_history = []
        if variables is None:
            variables = []
        if internal_tools is None:
            internal_tools = []

        # Create a minimal data structure for predict agent
        # All LLM settings are taken from the passed client instance
        # Note: 'tools' here are tool CONFIGURATIONS, not tool instances
        # They will be converted to tool instances by LangChainAssistant via get_tools()
        agent_data = {
            'instructions': instructions,
            'tools': tools,  # Tool configs that will be processed by get_tools()
            'variables': variables,
            'internal_tools': internal_tools  # Mode flags like 'swarm' for multi-agent collaboration
        }

        # Auto-create middleware based on internal_tools in the tools list
        # Check if any tool config is an internal_tool with name='planner'
        middleware_list = []
        has_planner = any(
            t.get('type') == 'internal_tool' and t.get('name') == 'planner'
            for t in tools
        )
        if has_planner:
            from ..middleware.planning import PlanningMiddleware
            planning_middleware = PlanningMiddleware(
                conversation_id=conversation_id,
                connection_string=None,  # Uses filesystem storage by default
            )
            middleware_list.append(planning_middleware)
            logger.info(f"Auto-created PlanningMiddleware for predict agent (conversation_id={conversation_id})")

        # LangChainAssistant constructor calls get_tools() which may raise McpAuthorizationRequired
        # The exception will propagate naturally to the indexer worker's outer handler
        return LangChainAssistant(
            self,
            agent_data,
            llm,
            chat_history,
            "predict",
            memory=memory,
            store=store,
            debug_mode=debug_mode,
            mcp_tokens=mcp_tokens,
            conversation_id=conversation_id,
            ignored_mcp_servers=ignored_mcp_servers,
            persona=persona,
            middleware=middleware_list if middleware_list else None,
            lazy_tools_mode=lazy_tools_mode
        ).runnable()

    def test_toolkit_tool(self, toolkit_config: dict, tool_name: str, tool_params: dict = None,
                          runtime_config: dict = None, llm_model: str = None,
                          llm_config: dict = None, mcp_tokens: dict = None) -> dict:
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
            mcp_tokens: Optional dictionary of MCP OAuth tokens by server URL
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
            try:
                tools = instantiate_toolkit_with_client(toolkit_config, llm, self, mcp_tokens=mcp_tokens, use_prefix=False)
            except McpAuthorizationRequired:
                # Re-raise McpAuthorizationRequired to allow proper handling upstream
                logger.info(f"McpAuthorizationRequired detected, re-raising")
                raise
            except Exception as toolkit_error:
                # For other errors, return error response
                return {
                    "success": False,
                    "error": f"Failed to instantiate toolkit '{toolkit_config.get('toolkit_name')}': {str(toolkit_error)}",
                    "tool_name": tool_name,
                    "toolkit_config": toolkit_config_parsed_json,
                    "llm_model": llm_model,
                    "events_dispatched": events_dispatched,
                    "execution_time_seconds": 0.0
                }

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

                # Create comprehensive error message
                error_msg = f"Tool '{tool_name}' not found in toolkit '{toolkit_config.get('toolkit_name')}'.\n"

                # Custom error for index tools
                if toolkit_name in [tool.value for tool in IndexTools]:
                    error_msg += f" Please make sure proper PGVector configuration and embedding model are set in the platform.\n"

                if base_available_tools:
                    error_msg += f" Available tools: {base_available_tools}"
                elif available_tools:
                    error_msg += f" Available tools: {available_tools}"
                else:
                    error_msg += " No tools found in the toolkit."

                # Add helpful hint about naming conventions
                if '___' in tool_name:
                    error_msg += f" Note: Tool names no longer use '___' prefixes. Try using just the base name '{extract_base_tool_name(tool_name)}'."

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
            # Re-raise McpAuthorizationRequired to allow proper handling upstream
            if isinstance(e, McpAuthorizationRequired):
                raise
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

    def test_mcp_connection(self, toolkit_config: dict, mcp_tokens: dict = None) -> dict:
        """
        Test MCP server connection using protocol-level list_tools.

        This method verifies MCP server connectivity and authentication by calling
        the protocol-level tools/list JSON-RPC method (NOT executing a tool).
        This is ideal for auth checks as it validates the connection without
        requiring any tool execution.

        Args:
            toolkit_config: Configuration dictionary for the MCP toolkit containing:
                - toolkit_name: Name of the toolkit
                - settings: Dictionary with 'url', optional 'headers', 'session_id'
            mcp_tokens: Optional dictionary of MCP OAuth tokens by server URL
                Format: {canonical_url: {access_token: str, session_id: str}}

        Returns:
            Dictionary containing:
                - success: Boolean indicating if the connection was successful
                - tools: List of tool names available on the MCP server (if successful)
                - tools_count: Number of tools discovered
                - server_session_id: Session ID provided by the server (if any)
                - error: Error message (if unsuccessful)
                - toolkit_config: Original toolkit configuration

        Raises:
            McpAuthorizationRequired: If MCP server requires OAuth authorization

        Example:
            >>> config = {
            ...     'toolkit_name': 'my-mcp-server',
            ...     'type': 'mcp',
            ...     'settings': {
            ...         'url': 'https://mcp-server.example.com/mcp',
            ...         'headers': {'X-Custom': 'value'}
            ...     }
            ... }
            >>> result = client.test_mcp_connection(config)
            >>> if result['success']:
            ...     print(f"Connected! Found {result['tools_count']} tools")
        """
        import asyncio
        import time
        # Migration: Use UnifiedMcpClient (wraps langchain-mcp-adapters) instead of custom McpClient
        from ..utils.mcp_adapter import UnifiedMcpClient as McpClient
        from ..utils.mcp_oauth import canonical_resource

        toolkit_name = toolkit_config.get('toolkit_name', 'unknown')
        settings = toolkit_config.get('settings', {})

        # Extract connection parameters
        url = settings.get('url')
        if not url:
            return {
                "success": False,
                "error": "MCP toolkit configuration missing 'url' in settings",
                "toolkit_config": toolkit_config,
                "tools": [],
                "tools_count": 0
            }

        headers = settings.get('headers') or {}
        session_id = settings.get('session_id')

        # Apply OAuth token if available
        if mcp_tokens and url:
            canonical_url = canonical_resource(url)
            token_data = mcp_tokens.get(canonical_url)
            if token_data:
                if isinstance(token_data, dict):
                    access_token = token_data.get('access_token')
                    if not session_id:
                        session_id = token_data.get('session_id')
                else:
                    # Backward compatibility: plain token string
                    access_token = token_data

                if access_token:
                    headers = dict(headers)  # Copy to avoid mutating original
                    headers.setdefault('Authorization', f'Bearer {access_token}')
                    logger.info(f"[MCP Auth Check] Applied OAuth token for {canonical_url}")

        logger.info(f"Testing MCP connection to '{toolkit_name}' at {url}")

        start_time = time.time()

        async def _test_connection():
            client = McpClient(
                url=url,
                session_id=session_id,
                headers=headers,
                timeout=60  # Reasonable timeout for connection test
            )

            async with client:
                # Initialize MCP protocol session
                await client.initialize()
                logger.info(f"[MCP Auth Check] Session initialized (transport={client.detected_transport})")

                # Call protocol-level list_tools (tools/list JSON-RPC method)
                tools = await client.list_tools()

                return {
                    "tools": tools,
                    "server_session_id": client.server_session_id,
                    "transport": client.detected_transport
                }

        try:
            # Run async operation
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, create a new task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _test_connection())
                        result = future.result(timeout=120)
                else:
                    result = loop.run_until_complete(_test_connection())
            except RuntimeError:
                # No event loop, create one
                result = asyncio.run(_test_connection())

            execution_time = time.time() - start_time

            # Extract tool names for the response
            tool_names = [tool.get('name', 'unknown') for tool in result.get('tools', [])]

            logger.info(f"[MCP Auth Check] Connection successful to '{toolkit_name}': {len(tool_names)} tools in {execution_time:.3f}s")

            return {
                "success": True,
                "tools": tool_names,
                "tools_count": len(tool_names),
                "server_session_id": result.get('server_session_id'),
                "transport": result.get('transport'),
                "toolkit_config": toolkit_config,
                "execution_time_seconds": execution_time
            }

        except McpAuthorizationRequired:
            # Re-raise to allow proper handling upstream
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[MCP Auth Check] Connection failed to '{toolkit_name}': {str(e)}")
            return {
                "success": False,
                "error": f"MCP connection failed: {str(e)}",
                "toolkit_config": toolkit_config,
                "tools": [],
                "tools_count": 0,
                "execution_time_seconds": execution_time
            }
