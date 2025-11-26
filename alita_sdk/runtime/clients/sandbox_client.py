import logging
from typing import Dict, Optional
from urllib.parse import quote

import requests
from typing import Any
from json import dumps
import chardet

logger = logging.getLogger(__name__)


class ApiDetailsRequestError(Exception):
    ...


class SandboxArtifact:
    def __init__(self, client: Any, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        if not self.client.bucket_exists(bucket_name):
            self.client.create_bucket(bucket_name)

    def create(self, artifact_name: str, artifact_data: Any, bucket_name: str = None):
        try:
            if not bucket_name:
                bucket_name = self.bucket_name
            return dumps(self.client.create_artifact(bucket_name, artifact_name, artifact_data))
        except Exception as e:
            logger.error(f'Error: {e}')
            return f'Error: {e}'

    def get(self,
            artifact_name: str,
            bucket_name: str = None,
            is_capture_image: bool = False,
            page_number: int = None,
            sheet_name: str = None,
            excel_by_sheets: bool = False,
            llm=None):
        if not bucket_name:
            bucket_name = self.bucket_name
        data = self.client.download_artifact(bucket_name, artifact_name)
        if len(data) == 0:
            # empty file might be created
            return ''
        if isinstance(data, dict) and data['error']:
            return f'{data['error']}. {data['content'] if data['content'] else ''}'
        detected = chardet.detect(data)
        return data
        # TODO: add proper handling for binary files (images, pdf, etc.) for sandbox
        # if detected['encoding'] is not None:
        #     try:
        #         return data.decode(detected['encoding'])
        #     except Exception:
        #         logger.error('Error while default encoding')
        #         return parse_file_content(file_name=artifact_name,
        #                                   file_content=data,
        #                                   is_capture_image=is_capture_image,
        #                                   page_number=page_number,
        #                                   sheet_name=sheet_name,
        #                                   excel_by_sheets=excel_by_sheets,
        #                                   llm=llm)
        # else:
        #     return parse_file_content(file_name=artifact_name,
        #                               file_content=data,
        #                               is_capture_image=is_capture_image,
        #                               page_number=page_number,
        #                               sheet_name=sheet_name,
        #                               excel_by_sheets=excel_by_sheets,
        #                               llm=llm)

    def delete(self, artifact_name: str, bucket_name=None):
        if not bucket_name:
            bucket_name = self.bucket_name
        self.client.delete_artifact(bucket_name, artifact_name)

    def list(self, bucket_name: str = None, return_as_string=True) -> str | dict:
        if not bucket_name:
            bucket_name = self.bucket_name
        artifacts = self.client.list_artifacts(bucket_name)
        return str(artifacts) if return_as_string else artifacts

    def append(self, artifact_name: str, additional_data: Any, bucket_name: str = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        data = self.get(artifact_name, bucket_name)
        if data == 'Could not detect encoding':
            return data
        data += f'{additional_data}' if len(data) > 0 else additional_data
        self.client.create_artifact(bucket_name, artifact_name, data)
        return 'Data appended successfully'

    def overwrite(self, artifact_name: str, new_data: Any, bucket_name: str = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        return self.create(artifact_name, new_data, bucket_name)

    def get_content_bytes(self,
                          artifact_name: str,
                          bucket_name: str = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        return self.client.download_artifact(bucket_name, artifact_name)


class SandboxClient:
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
            'Authorization': f'Bearer {auth_token}',
            'X-SECRET': kwargs.get('XSECRET', 'secret')
        }
        if api_extra_headers is not None:
            self.headers.update(api_extra_headers)
        self.predict_url = f'{self.base_url}{self.api_path}/prompt_lib/predict/prompt_lib/{self.project_id}'
        self.prompt_versions = f'{self.base_url}{self.api_path}/prompt_lib/version/prompt_lib/{self.project_id}'
        self.prompts = f'{self.base_url}{self.api_path}/prompt_lib/prompt/prompt_lib/{self.project_id}'
        self.datasources = f'{self.base_url}{self.api_path}/datasources/datasource/prompt_lib/{self.project_id}'
        self.datasources_predict = f'{self.base_url}{self.api_path}/datasources/predict/prompt_lib/{self.project_id}'
        self.datasources_search = f'{self.base_url}{self.api_path}/datasources/search/prompt_lib/{self.project_id}'
        self.app = f'{self.base_url}{self.api_path}/applications/application/prompt_lib/{self.project_id}'
        self.mcp_tools_list = f'{self.base_url}{self.api_path}/mcp_sse/tools_list/{self.project_id}'
        self.mcp_tools_call = f'{self.base_url}{self.api_path}/mcp_sse/tools_call/{self.project_id}'
        self.application_versions = f'{self.base_url}{self.api_path}/applications/version/prompt_lib/{self.project_id}'
        self.list_apps_url = f'{self.base_url}{self.api_path}/applications/applications/prompt_lib/{self.project_id}'
        self.integration_details = f'{self.base_url}{self.api_path}/integrations/integration/{self.project_id}'
        self.secrets_url = f'{self.base_url}{self.api_path}/secrets/secret/{self.project_id}'
        self.artifacts_url = f'{self.base_url}{self.api_path}/artifacts/artifacts/default/{self.project_id}'
        self.artifact_url = f'{self.base_url}{self.api_path}/artifacts/artifact/default/{self.project_id}'
        self.bucket_url = f'{self.base_url}{self.api_path}/artifacts/buckets/{self.project_id}'
        self.configurations_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=configurations&unsecret=true'
        self.ai_section_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=ai'
        self.image_generation_url = f'{self.base_url}{self.llm_path}/images/generations'
        self.auth_user_url = f'{self.base_url}{self.api_path}/auth/user'
        self.configurations: list = configurations or []
        self.model_timeout = kwargs.get('model_timeout', 120)
        self.model_image_generation = kwargs.get('model_image_generation')

    def get_mcp_toolkits(self):
        if user_id := self._get_real_user_id():
            url = f'{self.mcp_tools_list}/{user_id}'
            data = requests.get(url, headers=self.headers, verify=False).json()
            return data
        else:
            return []

    def mcp_tool_call(self, params: dict[str, Any]):
        if user_id := self._get_real_user_id():
            url = f'{self.mcp_tools_call}/{user_id}'
            #
            # This loop iterates over each key-value pair in the arguments dictionary,
            # and if a value is a Pydantic object, it replaces it with its dictionary representation using .dict().
            for arg_name, arg_value in params.get('params', {}).get('arguments', {}).items():
                if isinstance(arg_value, list):
                    params['params']['arguments'][arg_name] = [
                        item.dict() if hasattr(item, 'dict') and callable(item.dict) else item
                        for item in arg_value
                    ]
                elif hasattr(arg_value, 'dict') and callable(arg_value.dict):
                    params['params']['arguments'][arg_name] = arg_value.dict()
            #
            response = requests.post(url, headers=self.headers, json=params, verify=False)
            try:
                return response.json()
            except (ValueError, TypeError):
                return response.text
        else:
            return f'Error: Could not determine user ID for MCP tool call'

    def get_app_details(self, application_id: int):
        url = f'{self.app}/{application_id}'
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
                apps.extend([{'name': app['name'], 'id': app['id']} for app in data.get('rows', [])])
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

    def generate_image(self,
                       prompt: str,
                       n: int = 1,
                       size: str = 'auto',
                       quality: str = 'auto',
                       response_format: str = 'b64_json',
                       style: Optional[str] = None) -> dict:

        if not self.model_image_generation:
            raise ValueError('Image generation model is not configured for this client')

        image_generation_data = {
            'prompt': prompt,
            'model': self.model_image_generation,
            'n': n,
            'response_format': response_format,
        }

        # Only add optional parameters if they have meaningful values
        if size and size.lower() != 'auto':
            image_generation_data['size'] = size

        if quality and quality.lower() != 'auto':
            image_generation_data['quality'] = quality

        if style:
            image_generation_data['style'] = style

        # Standard headers for image generation
        image_headers = self.headers.copy()
        image_headers.update({
            'Content-Type': 'application/json',
        })

        logger.info(f'Generating image with model: {self.model_image_generation}, prompt: {prompt[:50]}...')

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
            logger.error(f'Image generation failed: {e.response.status_code} - {e.response.text}')
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f'Image generation request failed: {e}')
            raise

    def get_app_version_details(self, application_id: int, application_version_id: int) -> dict:
        url = f'{self.application_versions}/{application_id}/{application_version_id}'
        if self.configurations:
            configs = self.configurations
        else:
            configs = self.fetch_available_configurations()

        resp = requests.patch(url, headers=self.headers, verify=False, json={'configurations': configs})
        if resp.ok:
            return resp.json()
        logger.error(f'Failed to fetch application version details: {resp.status_code} - {resp.text}.'
                     f' Application ID: {application_id}, Version ID: {application_version_id}')
        raise ApiDetailsRequestError(
            f'Failed to fetch application version details for {application_id}/{application_version_id}.')

    def get_integration_details(self, integration_id: str, format_for_model: bool = False):
        url = f'{self.integration_details}/{integration_id}'
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data

    def unsecret(self, secret_name: str):
        url = f'{self.secrets_url}/{secret_name}'
        data = requests.get(url, headers=self.headers, verify=False).json()
        logger.info(f'Unsecret response: {data}')
        return data.get('value', None)

    def artifact(self, bucket_name):
        return SandboxArtifact(self, bucket_name)

    def _process_requst(self, data: requests.Response) -> Dict[str, str]:
        if data.status_code == 403:
            return {'error': 'You are not authorized to access this resource'}
        elif data.status_code == 404:
            return {'error': 'Resource not found'}
        elif data.status_code != 200:
            return {
                'error': 'An error occurred while fetching the resource',
                'content': data.text
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

    def create_bucket(self, bucket_name, expiration_measure='months', expiration_value=1):
        post_data = {
            'name': bucket_name,
            'expiration_measure': expiration_measure,
            'expiration_value': expiration_value
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
            return {'error': 'You are not authorized to access this resource'}
        elif data.status_code == 404:
            return {'error': 'Resource not found'}
        elif data.status_code != 200:
            return {
                'error': 'An error occurred while fetching the resource',
                'content': data.content
            }
        return data.content

    def delete_artifact(self, bucket_name, artifact_name):
        url = f'{self.artifact_url}/{bucket_name}'
        data = requests.delete(url, headers=self.headers, verify=False, params={'filename': quote(artifact_name)})
        return self._process_requst(data)

    def get_user_data(self) -> Dict[str, Any]:
        resp = requests.get(self.auth_user_url, headers=self.headers, verify=False)
        if resp.ok:
            return resp.json()
        logger.error(f'Failed to fetch user data: {resp.status_code} - {resp.text}')
        raise ApiDetailsRequestError(f'Failed to fetch user data with status code {resp.status_code}.')
