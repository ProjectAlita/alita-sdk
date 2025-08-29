from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class GithubConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "GitHub",
                "icon_url": None,
                "sections": {
                    "auth": {
                        "required": False,
                        "subsections": [
                            {
                                "name": "Token",
                                "fields": ["access_token"]
                            },
                            {
                                "name": "Password",
                                "fields": ["username", "password"]
                            },
                            {
                                "name": "App private key",
                                "fields": ["app_id", "app_private_key"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "github",
                "categories": ["code repositories"],
                "extra_categories": ["github", "git", "repository", "code", "version control"],
            }
        }
    )

    base_url: Optional[str] = Field(description="Base API URL", default="https://api.github.com")
    app_id: Optional[str] = Field(description="Github APP ID", default=None)
    app_private_key: Optional[SecretStr] = Field(description="Github APP private key", default=None)

    access_token: Optional[SecretStr] = Field(description="Github Access Token", default=None)

    username: Optional[str] = Field(description="Github Username", default=None)
    password: Optional[SecretStr] = Field(description="Github Password", default=None)

    @model_validator(mode='before')
    @classmethod
    def validate_auth_sections(cls, data):
        if not isinstance(data, dict):
            return data

        has_token = bool(data.get('access_token') and str(data.get('access_token')).strip())
        has_password = bool(
            data.get('username') and str(data.get('username')).strip() and
            data.get('password') and str(data.get('password')).strip()
        )
        has_app_key = bool(
            data.get('app_id') and str(data.get('app_id')).strip() and
            data.get('app_private_key') and str(data.get('app_private_key')).strip()
        )

        # If any method is partially configured, raise exception
        if (
                (data.get('username') and not data.get('password')) or
                (data.get('password') and not data.get('username')) or
                (data.get('app_id') and not data.get('app_private_key')) or
                (data.get('app_private_key') and not data.get('app_id'))
        ):
            raise ValueError(
                "Authentication is misconfigured: both username and password, or both app_id and app_private_key, must be provided together."
            )

        # If all are missing, allow anonymous
        if not (has_token or has_password or has_app_key):
            return data

        # If any method is fully configured
        if has_token or has_password or has_app_key:
            return data

        raise ValueError(
            "Authentication is misconfigured: provide either Token (access_token), "
            "Password (username + password), App private key (app_id + app_private_key), "
            "or leave all blank for anonymous access."
        )

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check GitHub connection using provided settings.
        Returns None if connection is successful, error message otherwise.
        """
        import requests
        from requests.auth import HTTPBasicAuth
        import jwt
        import time

        base_url = settings.get('base_url', 'https://api.github.com')
        access_token = settings.get('access_token')
        username = settings.get('username')
        password = settings.get('password')
        app_id = settings.get('app_id')
        app_private_key = settings.get('app_private_key')

        # if all auth methods are None or empty, allow anonymous access
        if not any([access_token, (username and password), (app_id and app_private_key)]):
            return None

        headers = {'Accept': 'application/vnd.github.v3+json'}
        auth = None

        try:
            # Determine authentication method
            if access_token:
                headers['Authorization'] = f'token {access_token}'
            elif username and password:
                auth = HTTPBasicAuth(username, password)
            elif app_id and app_private_key:
                # Generate JWT for GitHub App authentication
                payload = {
                    'iat': int(time.time()),
                    'exp': int(time.time()) + 600,  # 10 minutes
                    'iss': app_id
                }
                jwt_token = jwt.encode(payload, app_private_key, algorithm='RS256')
                headers['Authorization'] = f'Bearer {jwt_token}'

            # Test connection with user endpoint
            response = requests.get(f'{base_url}/user', headers=headers, auth=auth, timeout=10)

            if response.status_code == 200:
                return None
            elif response.status_code == 401:
                return "Authentication failed: Invalid credentials"
            elif response.status_code == 403:
                return "Access forbidden: Check your permissions"
            elif response.status_code == 404:
                return "GitHub API endpoint not found"
            else:
                return f"Connection failed with status {response.status_code}: {response.text}"

        except requests.exceptions.ConnectionError:
            return "Connection error: Unable to reach GitHub API"
        except requests.exceptions.Timeout:
            return "Connection timeout: GitHub API did not respond in time"
        except jwt.InvalidKeyError:
            return "Invalid private key format for GitHub App authentication"
        except Exception as e:
            return f"Unexpected error: {str(e)}"