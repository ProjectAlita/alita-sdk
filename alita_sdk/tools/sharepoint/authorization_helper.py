from datetime import datetime, timezone
from urllib.parse import urlparse

import jwt
import requests

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


    def generate_token_and_site_id(self, site_url: str) -> tuple[str, str]:
        try:
            parsed = urlparse(site_url)
            domain = parsed.hostname
            site_path = parsed.path.strip('/')
            if not domain or not site_path:
                raise ValueError(f"site_url missing domain or site path: {site_url}")
            #
            app_name = domain.split('.')[0]
            openid_config_url = f"https://login.microsoftonline.com/{app_name}.onmicrosoft.com/v2.0/.well-known/openid-configuration"
            response = requests.get(openid_config_url)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to get OpenID config: {response.status_code} {response.text}")
            token_url = response.json().get("token_endpoint")
            if not token_url:
                raise KeyError("'token_endpoint' missing in OpenID config response")
            #
            token_data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default"
            }
            token_response = requests.post(token_url, data=token_data)
            if token_response.status_code != 200:
                raise RuntimeError(f"Failed to get access token: {token_response.status_code} {token_response.text}")
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise KeyError("'access_token' missing in token response")
            #
            graph_site_url = f"https://graph.microsoft.com/v1.0/sites/{domain}:/{site_path}"
            headers = {"Authorization": f"Bearer {access_token}"}
            site_response = requests.get(graph_site_url, headers=headers)
            if site_response.status_code != 200:
                raise RuntimeError(f"Failed to get site info: {site_response.status_code} {site_response.text}")
            site_id = site_response.json().get("id")
            if not site_id:
                raise KeyError("'id' missing in site response")
            #
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
            if drives_response.status_code != 200:
                raise RuntimeError(f"Failed to get drives: {drives_response.status_code} {drives_response.text}")
            drives_json = drives_response.json()
            if "value" not in drives_json or not drives_json["value"]:
                raise KeyError("'value' missing or empty in drives response")
            drive_id = drives_json["value"][0].get("id")
            if not drive_id:
                raise KeyError("'id' missing in drive object")
            #
            # Build the correct endpoint for folder or root
            if folder_name:
                # Validate folder_name for safe URL usage
                if any(c in folder_name for c in ['..', '//', '\\']):
                    raise ValueError(f"Unsafe folder_name: {folder_name}")
                url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{folder_name}:/children?$top={limit_files}"
            else:
                url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root/children?$top={limit_files}"
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to get files list: {response.status_code} {response.text}")
            files_json = response.json()
            if "value" not in files_json:
                raise KeyError("'value' missing in files response")
            #
            result = []
            for file in files_json["value"]:
                temp_props = {
                    'Name': file.get('name'),
                    'Path': file.get('webUrl'),
                    'Created': file.get('createdDateTime'),
                    'Modified': file.get('lastModifiedDateTime'),
                    'Link': file.get('webUrl'),
                    'id': file.get('id')
                }
                if not all([temp_props['Name'], temp_props['Path'], temp_props['id']]):
                    raise KeyError(f"Missing required file fields in: {file}")
                result.append(temp_props)
            # If API doesn't respect $top, slice in Python
            if limit_files is not None:
                result = result[:limit_files]
            return result
        except Exception as e:
            raise RuntimeError(f"Error in get_files_list: {e}")
