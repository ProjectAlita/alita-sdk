from datetime import datetime, timezone
from urllib.parse import unquote, urlparse, quote

import jwt
import requests
from botocore.response import get_response


class SharepointAuthorizationHelper:

    def __init__(self, tenant, client_id, client_secret, scope, token_json):
        self.tenant = tenant
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.auth_code = None
        self.access_token = None
        self.token_json = token_json
        self.state = "12345"  # Static state for this example
        self.redirect_url = None

    def refresh_access_token(self) -> str:
        url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.token_json,
            'scope': self.scope
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None

    def get_access_token(self) -> str:
        if (self.is_token_valid(self.token_json)):
            return self.token_json['access_token']
        else:
            return self.refresh_access_token()


    def is_token_valid(self, access_token) -> bool:
        try:
            decoded_token = jwt.decode(access_token, options={"verify_signature": False})
            exp_timestamp = decoded_token.get("exp")
            if exp_timestamp is None:
                return False
            expiration_time = datetime.fromtimestamp(exp_timestamp, timezone.utc)
            return expiration_time > datetime.now(timezone.utc)
        except jwt.ExpiredSignatureError:
            return False
        except jwt.InvalidTokenError:
            return False

    def _validate_response(self, response, required_field, error_prefix=None):
        if response.status_code != 200:
            raise RuntimeError(f"{error_prefix or 'Request'} failed: {response.status_code} {response.text}")
        json_data = response.json()
        if required_field not in json_data:
            raise KeyError(f"'{required_field}' missing in response")
        return json_data[required_field]

    def generate_token_and_site_id(self, site_url: str) -> tuple[str, str]:
        try:
            parsed = urlparse(site_url)
            domain = parsed.hostname
            site_path = parsed.path.strip('/')
            if not domain or not site_path:
                raise ValueError(f"site_url missing domain or site path: {site_url}")
            app_name = domain.split('.')[0]
            openid_config_url = f"https://login.microsoftonline.com/{app_name}.onmicrosoft.com/v2.0/.well-known/openid-configuration"
            response = requests.get(openid_config_url)
            token_url = self._validate_response(response, required_field="token_endpoint", error_prefix="OpenID config")
            token_data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default"
            }
            token_response = requests.post(token_url, data=token_data)
            access_token = self._validate_response(token_response, required_field="access_token", error_prefix="Token request")
            graph_site_url = f"https://graph.microsoft.com/v1.0/sites/{domain}:/{site_path}"
            headers = {"Authorization": f"Bearer {access_token}"}
            site_response = requests.get(graph_site_url, headers=headers)
            site_id = self._validate_response(site_response, required_field="id", error_prefix="Site info")
            return access_token, site_id
        except Exception as e:
            raise RuntimeError(f"Error while obtaining access_token and site_id: {e}")

    def get_files_list(self, site_url: str, folder_name: str = None, limit_files: int = 100):
        if not site_url or not site_url.startswith("https://"):
            raise ValueError(f"Invalid site_url format: {site_url}")
        if limit_files is not None and (not isinstance(limit_files, int) or limit_files <= 0):
            raise ValueError(f"limit_files must be a positive integer, got: {limit_files}")
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
            drives_response = requests.get(drives_url, headers=headers)
            drives = self._validate_response(drives_response, required_field="value", error_prefix="Drives request")
            result = []
            def _recurse_drive(drive_id, drive_path, parent_folder, limit_files):
                # Escape folder_name for URL safety if present
                if parent_folder:
                    safe_folder_name = quote(parent_folder.strip('/'), safe="/")
                    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{safe_folder_name}:/children?$top={limit_files}"
                else:
                    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root/children?$top={limit_files}"
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    return []
                files_json = response.json()
                if "value" not in files_json:
                    return []
                files = []
                for file in files_json["value"]:
                    file_name = file.get('name', '')
                    # Build full path reflecting nested folders
                    if parent_folder:
                        full_path = '/' + '/'.join([drive_path.strip('/'), parent_folder.strip('/'), file_name.strip('/')])
                    else:
                        full_path = '/' + '/'.join([drive_path.strip('/'), file_name.strip('/')])
                    temp_props = {
                        'Name': file_name,
                        'Path': full_path,
                        'Created': file.get('createdDateTime'),
                        'Modified': file.get('lastModifiedDateTime'),
                        'Link': file.get('webUrl'),
                        'id': file.get('id')
                    }
                    if not all([temp_props['Name'], temp_props['Path'], temp_props['id']]):
                        continue  # skip files with missing required fields
                    if 'folder' in file:
                        # Recursively extract files from this folder
                        inner_folder = parent_folder + '/' + file_name if parent_folder else file_name
                        inner_files = _recurse_drive(drive_id, drive_path, inner_folder, limit_files)
                        files.extend(inner_files)
                    else:
                        files.append(temp_props)
                    if limit_files is not None and len(result) + len(files) >= limit_files:
                        return files[:limit_files - len(result)]
                return files
            for drive in drives:
                drive_id = drive.get("id")
                drive_path = unquote(urlparse(drive.get("webUrl")).path) if drive.get("webUrl") else ""
                if not drive_id:
                    continue  # skip drives without id
                files = _recurse_drive(drive_id, drive_path, folder_name, limit_files)
                result.extend(files)
                if limit_files is not None and len(result) >= limit_files:
                    return result[:limit_files]
            return result
        except Exception as e:
            raise RuntimeError(f"Error in get_files_list: {e}")

    def get_file_content(self, site_url: str, path: str):
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
            drives_response = requests.get(drives_url, headers=headers)
            drives = self._validate_response(drives_response, required_field="value", error_prefix="Drives request")
            path = path.strip('/')
            #
            for drive in drives:
                drive_path = unquote(urlparse(drive.get("webUrl")).path).strip('/')
                if not drive_path or not path.startswith(drive_path):
                    continue
                drive_id = drive.get("id")
                if not drive_id:
                    continue
                path = path.replace(drive_path, '').strip('/')
                safe_path = quote(path, safe="")
                url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{safe_path}:/content"
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    return response.content
            raise RuntimeError(f"File '{path}' not found in any private or shared documents.")
        except Exception as e:
            raise RuntimeError(f"Error in get_file_content: {e}")

    def get_list_items(self, site_url: str, list_title: str, limit: int = 1000):
        """Fallback Graph API method to read SharePoint list items by list title.

        Returns a list of dictionaries representing list item fields.
        """
        if not site_url or not site_url.startswith("https://"):
            raise ValueError(f"Invalid site_url format: {site_url}")
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            lists_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
            response = requests.get(lists_url, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"Lists request failed: {response.status_code} {response.text}")
            lists_json = response.json()
            lists = lists_json.get("value", [])
            target_list = None
            normalized_title = list_title.strip().lower()
            for lst in lists:
                # displayName is the user-visible title. name can differ (internal name)
                display_name = (lst.get("displayName") or lst.get("name") or '').strip().lower()
                if display_name == normalized_title:
                    target_list = lst
                    break
            if not target_list:
                raise RuntimeError(f"List '{list_title}' not found via Graph API.")
            list_id = target_list.get('id')
            if not list_id:
                raise RuntimeError(f"List '{list_title}' missing id field.")
            items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields&$top={limit}"
            items_response = requests.get(items_url, headers=headers)
            if items_response.status_code != 200:
                raise RuntimeError(f"List items request failed: {items_response.status_code} {items_response.text}")
            items_json = items_response.json()
            values = items_json.get('value', [])
            result = []
            for item in values:
                fields = item.get('fields', {})
                if fields:
                    result.append(fields)
            return result
        except Exception as e:
            raise RuntimeError(f"Error in get_list_items: {e}")
