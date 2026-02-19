import logging
import re
from pathlib import Path
from typing import Dict, Optional, Any, Union
from urllib.parse import quote

import requests
import chardet

logger = logging.getLogger(__name__)

# Use only the first 10 KB for chardet so it doesn't scan the whole file (slow for large files).
_CHARDET_SAMPLE_SIZE = 10 * 1024


class ApiDetailsRequestError(Exception):
    ...


class SandboxArtifact:
    def __init__(self, client: Any, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        if not self.client.bucket_exists(bucket_name):
            self.client.create_bucket(bucket_name)

    def create(self, artifact_name: str, artifact_data: Any, bucket_name: str = None, check_if_exists: bool = False) -> dict:
        """Create or overwrite a file. Returns dict with filepath, file_existed (tri-state), operation_type, or error.

        Args:
            artifact_name: Target file name/key.
            artifact_data: File content (str or bytes).
            bucket_name: Bucket to write into (uses default if None).
            check_if_exists: When True, performs a HEAD request before upload to determine whether
                the file already existed. file_existed will be True or False.
                When False (default), skips the HEAD request; file_existed will be None.
        """
        try:
            if not bucket_name:
                bucket_name = self.bucket_name

            if check_if_exists:
                head_result = self.client.head_artifact_s3(bucket_name, artifact_name)
                file_existed: bool | None = head_result.get('exists', False)
            else:
                file_existed = None

            operation_type = "modify" if file_existed else "create"

            # Use S3 API for upload
            result = self.client.upload_artifact_s3(bucket_name, artifact_name, artifact_data)
            if 'error' in result:
                return {"error": result['error']}
            sanitized_name = result['sanitized_name']
            return {
                "message": f"File '{sanitized_name}' {'updated' if file_existed else 'created'} successfully",
                "filepath": result['filepath'],
                "sanitized_name": sanitized_name,
                "was_sanitized": result['was_sanitized'],
                "file_existed": file_existed,
                "operation_type": operation_type,
            }
        except Exception as e:
            logger.error(f'Error: {e}')
            return {"error": str(e)}

    def get(self,
            artifact_name: str,
            bucket_name: str = None,
            is_capture_image: bool = False,
            page_number: int = None,
            sheet_name: str = None,
            excel_by_sheets: bool = False,
            llm=None):
        """Get file content as decoded string."""
        if not bucket_name:
            bucket_name = self.bucket_name
        # Use S3 API for downloading
        data = self.client.download_artifact_s3(bucket_name, artifact_name)
        if isinstance(data, dict) and 'error' in data:
            return f"{data['error']}. {data.get('content', '')}"
        if len(data) == 0:
            # empty file might be created
            return ''
        # Use only first 10KB for chardet detection (performance optimization)
        detected = chardet.detect(data[:_CHARDET_SAMPLE_SIZE])
        if detected['encoding'] is not None:
            try:
                return data.decode(detected['encoding'])
            except Exception:
                logger.error("Error while decoding with detected encoding")
                return data.decode('utf-8', errors='replace')
        else:
            # Fallback to utf-8 with error replacement
            return data.decode('utf-8', errors='replace')

    def delete(self, artifact_name: str, bucket_name: str = None) -> dict:
        """Delete a file. Returns dict with message or error."""
        if not bucket_name:
            bucket_name = self.bucket_name
        # Use S3 API for delete
        result = self.client.delete_artifact_s3(bucket_name, artifact_name)
        if 'error' in result:
            return {"error": result['error']}
        return {"message": f"File '{artifact_name}' deleted successfully"}

    def list(self, bucket_name: str = None, prefix: str = '', delimiter: str = '/', return_as_string: bool = True) -> Union[str, dict]:
        """List files in bucket with folder/subfolder parsing.

        Returns dict (or str if return_as_string=True) with 'total' and 'rows'. Each row has:
        - name: display name (relative to prefix)
        - size: file size in bytes (0 for folders)
        - modified: last modified timestamp (empty for folders)
        - type: 'file' or 'folder'
        - key: full S3 key (only for files)
        """
        if not bucket_name:
            bucket_name = self.bucket_name
        # Use S3 API for listing
        result = self.client.list_artifacts_s3(bucket_name, prefix=prefix, delimiter=delimiter)
        if 'error' in result:
            error_result = {"error": result['error'], "total": 0, "rows": []}
            return str(error_result) if return_as_string else error_result

        files = []

        # Process files at this level (contents)
        for item in result.get('contents', []):
            key = item.get('key', '')
            # Get display name by stripping the prefix
            display_name = key[len(prefix):] if prefix and key.startswith(prefix) else key
            # Skip the folder itself (prefix entry) or empty names
            if not display_name:
                continue
            files.append({
                'name': display_name,
                'size': item.get('size', 0),
                'modified': item.get('lastModified', ''),
                'type': 'file',
                'key': key  # Full key for download link generation
            })

        # Process subfolders (commonPrefixes)
        for prefix_entry in result.get('commonPrefixes', []):
            prefix_str = prefix_entry.get('prefix', '') if isinstance(prefix_entry, dict) else prefix_entry
            # Get display name by stripping the prefix
            subfolder_full = prefix_str.rstrip('/')
            subfolder_name = subfolder_full[len(prefix):] if prefix and subfolder_full.startswith(prefix) else subfolder_full
            if subfolder_name:
                files.append({
                    'name': subfolder_name + '/',
                    'size': 0,
                    'modified': '',
                    'type': 'folder'
                })

        artifacts = {"total": len(files), "rows": files}
        return str(artifacts) if return_as_string else artifacts

    def append(self, artifact_name: str, additional_data: Any, bucket_name: str = None, create_if_missing: bool = True) -> dict:
        """Append data to existing file or create new. Returns dict with filepath or error."""
        if not bucket_name:
            bucket_name = self.bucket_name

        # Use S3 API to check if file exists and get content
        raw_data = self.client.download_artifact_s3(bucket_name, artifact_name)

        # If download returns an error dict, the file doesn't exist or there's an access issue
        if isinstance(raw_data, dict) and raw_data.get('error'):
            # Check if we should create the file if it doesn't exist
            if create_if_missing:
                return self.create(artifact_name, additional_data, bucket_name)
            else:
                return {"error": f"Cannot append to file '{artifact_name}'. {raw_data['error']}"}

        # Get the parsed content
        data = self.get(artifact_name, bucket_name)
        if data == "Could not detect encoding":
            return {"error": data}

        # Append the new data
        data += f'\n{additional_data}' if len(data) > 0 else additional_data
        result = self.client.upload_artifact_s3(bucket_name, artifact_name, data)
        if 'error' in result:
            return {"error": result['error']}
        return {
            "message": "Data appended successfully",
            "filepath": result['filepath'],
            "sanitized_name": result['sanitized_name'],
            "was_sanitized": result['was_sanitized']
        }

    def get_content_bytes(self,
                          artifact_name: str,
                          bucket_name: str = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        # Use S3 API for download
        return self.client.download_artifact_s3(bucket_name, artifact_name)


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
        self.s3_url = f'{self.base_url}/artifacts/s3'  # S3 API endpoint (same as AlitaClient)
        self.configurations_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=configurations&unsecret=true'
        self.ai_section_url = f'{self.base_url}{self.api_path}/integrations/integrations/default/{self.project_id}?section=ai'
        self.auth_user_url = f'{self.base_url}{self.api_path}/auth/user'
        self.configurations: list = configurations or []
        self.model_timeout = kwargs.get('model_timeout', 120)

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

    # =========================================================================
    # S3-Compatible API Methods (aligned with AlitaClient)
    # =========================================================================

    # S3 error code to user-friendly message mapping
    S3_ERROR_MESSAGES = {
        'NoSuchBucket': "Bucket '{bucket}' does not exist",
        'NoSuchKey': "File '{key}' not found",
        'AccessDenied': "Permission denied for '{resource}'",
        'BucketNotEmpty': "Bucket '{bucket}' is not empty",
        'InvalidBucketName': "Invalid bucket name '{bucket}'",
        'BucketAlreadyExists': "Bucket '{bucket}' already exists",
        'InvalidArgument': "Invalid argument provided",
    }

    def _s3_params(self, **extra) -> dict:
        """Build common S3 query parameters with project_id and JSON format."""
        params = {"project_id": self.project_id, "format": "json"}
        params.update(extra)
        return params

    def _handle_s3_error(self, response: requests.Response, bucket: str = None, key: str = None) -> dict:
        """Convert S3 error response to user-friendly error dict."""
        try:
            error_data = response.json()
            error_code = error_data.get('error', {}).get('code', 'Unknown')
        except (ValueError, TypeError):
            error_code = f"HTTP_{response.status_code}"

        template = self.S3_ERROR_MESSAGES.get(error_code, f"S3 error: {error_code}")
        resource = key or bucket or 'unknown'
        message = template.format(bucket=bucket or 'unknown', key=key or 'unknown', resource=resource)
        return {"error": message, "code": error_code}

    @staticmethod
    def _sanitize_artifact_name(filename: str) -> tuple:
        """Sanitize filename AND all folder path components for safe storage.

        SECURITY: Blocks path traversal attempts and sanitizes each path component.
        Inline version for Pyodide compatibility (no SDK imports).

        Example: 'my folder!/../../file (1).txt' -> 'myfolder/file-1.txt'

        Returns:
            tuple: (sanitized_name, was_modified)
        """
        if not filename or not filename.strip():
            return "unnamed_file", True

        original = filename

        # Block path traversal attempts
        if '..' in filename:
            # Remove all .. components
            filename = '/'.join(part for part in filename.split('/') if part != '..')

        path_obj = Path(filename)
        parts = list(path_obj.parts)

        sanitized_parts = []
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)

            if is_last:
                # Last part: separate name and extension
                name = Path(part).stem
                extension = Path(part).suffix
            else:
                # Folder part: treat entire part as name
                name = part
                extension = ''

            # Whitelist: alphanumeric, underscore, hyphen, space, Unicode letters/digits
            sanitized_name = re.sub(r'[^\w\s-]', '', name, flags=re.UNICODE)
            sanitized_name = re.sub(r'[-\s]+', '-', sanitized_name)
            sanitized_name = sanitized_name.strip('-').strip()

            if not sanitized_name:
                sanitized_name = "file" if is_last else "folder"

            if extension:
                extension = re.sub(r'[^\w.-]', '', extension, flags=re.UNICODE)

            sanitized_parts.append(f"{sanitized_name}{extension}")

        sanitized = '/'.join(sanitized_parts)
        return sanitized, (sanitized != original)

    def list_artifacts_s3(self, bucket_name: str, prefix: str = None, delimiter: str = '/') -> dict:
        """List artifacts via S3 API with optional prefix filtering.

        Args:
            bucket_name: S3 bucket name
            prefix: Filter by key prefix (folder path). If provided, lists only files
                   with keys starting with this prefix.
            delimiter: Character to group common prefixes (default '/' for folder listing).
                      Set to None for recursive listing of all files.

        Returns:
            dict: Response with 'contents' (files) and 'commonPrefixes' (subfolders)
                  or 'error' key if failed.
        """
        url = f"{self.s3_url}/{bucket_name.lower()}"
        params = self._s3_params(**{"list-type": "2"})
        if prefix:
            # Ensure prefix ends with / for folder listing
            params["prefix"] = prefix if prefix.endswith('/') else f"{prefix}/"
        if delimiter:
            params["delimiter"] = delimiter

        response = requests.get(url, headers=self.headers, params=params, verify=False)

        if response.status_code >= 400:
            return self._handle_s3_error(response, bucket=bucket_name)

        try:
            return response.json()
        except (ValueError, TypeError):
            return {"error": "Invalid response from S3 API", "content": response.text}

    def upload_artifact_s3(self, bucket_name: str, key: str, data: bytes, content_type: str = None) -> dict:
        """Upload artifact via S3 PUT.

        Sanitizes the key (filename) before upload to prevent regex errors during indexing.

        Args:
            bucket_name: S3 bucket name
            key: Full object key including folder path (e.g., 'folder/subfolder/file.txt')
            data: File content as bytes
            content_type: Optional MIME type.

        Returns:
            dict: Response with 'filepath', 'bucket', 'filename', 'sanitized_name', 'was_sanitized' keys or 'error' key.
        """
        # Sanitize filename to prevent regex errors during indexing
        sanitized_key, was_modified = self._sanitize_artifact_name(key)
        if was_modified:
            logger.warning(f"Artifact filename sanitized: '{key}' -> '{sanitized_key}'")

        url = f"{self.s3_url}/{bucket_name.lower()}/{quote(sanitized_key, safe='/')}"
        headers = dict(self.headers)
        if content_type:
            headers['Content-Type'] = content_type

        response = requests.put(url, headers=headers, data=data,
                               params=self._s3_params(), verify=False)

        if response.status_code >= 400:
            return self._handle_s3_error(response, bucket=bucket_name, key=sanitized_key)

        return {
            "filepath": f"/{bucket_name}/{sanitized_key}",
            "bucket": bucket_name,
            "filename": sanitized_key,
            "size": len(data) if data else 0,
            "sanitized_name": sanitized_key,
            "was_sanitized": was_modified
        }

    def download_artifact_s3(self, bucket_name: str, key: str) -> Union[bytes, dict]:
        """Download artifact via S3 GET.

        Args:
            bucket_name: S3 bucket name
            key: Full object key including folder path

        Returns:
            bytes: File content if successful
            dict: Error dict with 'error' key if failed
        """
        url = f"{self.s3_url}/{bucket_name.lower()}/{quote(key, safe='/')}"

        response = requests.get(url, headers=self.headers,
                               params=self._s3_params(), verify=False)

        if response.status_code >= 400:
            return self._handle_s3_error(response, bucket=bucket_name, key=key)

        return response.content

    def delete_artifact_s3(self, bucket_name: str, key: str) -> dict:
        """Delete artifact via S3 DELETE.

        Args:
            bucket_name: S3 bucket name
            key: Full object key including folder path

        Returns:
            dict: Response with 'success' True or 'error' key.
        """
        url = f"{self.s3_url}/{bucket_name.lower()}/{quote(key, safe='/')}"

        response = requests.delete(url, headers=self.headers,
                                  params=self._s3_params(), verify=False)

        if response.status_code >= 400:
            return self._handle_s3_error(response, bucket=bucket_name, key=key)

        return {"success": True, "message": f"File '{key}' deleted successfully"}

    def head_artifact_s3(self, bucket_name: str, key: str) -> dict:
        """Check if artifact exists and get metadata via S3 HEAD.

        Args:
            bucket_name: S3 bucket name
            key: Full object key including folder path

        Returns:
            dict: Response with 'exists', 'size', 'lastModified', 'contentType' keys
                  or 'error' key if failed.
        """
        url = f"{self.s3_url}/{bucket_name.lower()}/{quote(key, safe='/')}"

        response = requests.head(url, headers=self.headers,
                                params=self._s3_params(), verify=False)

        if response.status_code == 404:
            return {"exists": False}

        if response.status_code >= 400:
            return self._handle_s3_error(response, bucket=bucket_name, key=key)

        return {
            "exists": True,
            "size": int(response.headers.get('Content-Length', 0)),
            "lastModified": response.headers.get('Last-Modified', ''),
            "contentType": response.headers.get('Content-Type', ''),
            "etag": response.headers.get('ETag', '').strip('"')
        }

    def get_user_data(self) -> Dict[str, Any]:
        resp = requests.get(self.auth_user_url, headers=self.headers, verify=False)
        if resp.ok:
            return resp.json()
        logger.error(f'Failed to fetch user data: {resp.status_code} - {resp.text}')
        raise ApiDetailsRequestError(f'Failed to fetch user data with status code {resp.status_code}.')

    def _get_real_user_id(self):
        """Get real user ID from auth API for MCP calls."""
        try:
            user_data = self.get_user_data()
            return user_data.get("id")
        except Exception as e:
            logger.debug(f"Error: Could not determine user ID for MCP tool: {e}")
            return None
