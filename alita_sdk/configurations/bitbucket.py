from typing import Optional

from atlassian import Bitbucket
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class BitbucketConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Bitbucket",
                "icon_url": "bitbucket-icon.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Username & Password",
                                "fields": ["username", "password"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "bitbucket",
                "categories": ["code repositories"],
                "extra_categories": ["bitbucket", "git", "repository", "code", "version control"],
            }
        }
    )
    url: str = Field(description="Bitbucket URL")
    username: str = Field(description="Bitbucket Username")
    password: SecretStr = Field(description="Bitbucket Password/App Password")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check the connection to Bitbucket.
        
        Args:
            settings: Dictionary containing Bitbucket configuration
                - url: Bitbucket instance URL (required)
                - username: Bitbucket username (required)
                - password: Password or App Password (required)
        
        Returns:
            None if connection successful, error message string if failed
        """
        import requests
        from requests.auth import HTTPBasicAuth
        
        # Validate url
        url = settings.get("url", "").strip()
        if not url:
            return "Bitbucket URL is required"
        
        # Normalize URL - remove trailing slashes
        url = url.rstrip("/")
        
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return "Bitbucket URL must start with http:// or https://"
        
        # Validate username
        username = settings.get("username", "").strip()
        if not username:
            return "Bitbucket username is required"
        
        # Validate password
        password = settings.get("password")
        if not password:
            return "Bitbucket password is required"
        
        # Extract password value if it's a SecretStr
        password_value = password.get_secret_value() if hasattr(password, 'get_secret_value') else password
        
        if not password_value or not str(password_value).strip():
            return "Bitbucket password cannot be empty"
        
        # Detect if this is Bitbucket Cloud or Server/Data Center
        is_cloud = "bitbucket.org" in url.lower() or "api.bitbucket.org" in url.lower()
        is_correct_bitbucket_domain = "bitbucket" in url.lower()
        
        if is_cloud:
            # Bitbucket Cloud: Use API v2.0
            # Endpoint: /2.0/user - returns current authenticated user
            test_url = f"{url}/2.0/user"
        else:
            # Bitbucket Server/Data Center: Use API v1.0
            # Endpoint: /rest/api/1.0/users/{username}
            test_url = f"{url}/rest/api/1.0/users/{username}"
        
        try:
            response = requests.get(
                test_url,
                auth=HTTPBasicAuth(username, str(password_value).strip()),
                timeout=10
            )
            
            # Check response status
            if response.status_code == 200:
                # Successfully connected and authenticated
                return None
            elif response.status_code == 401:
                return "Authentication failed: invalid username or password"
            elif response.status_code == 403:
                return "Access forbidden: check user permissions"
            elif response.status_code == 404:
                if not is_correct_bitbucket_domain:
                    return f"Url you provided is incorrect. Please provide correct server or cloud bitbucket url."
                if is_cloud:
                    return "Bitbucket API endpoint not found: please provide the correct bitbucket cloud URL"
                else:
                    return "Bitbucket API endpoint not found: please provide the correct bitbucket server URL"
            else:
                return f"Bitbucket API returned status code {response.status_code}"

        except requests.exceptions.SSLError as e:
            return f"SSL certificate verification failed: {str(e)}"
        except requests.exceptions.ConnectionError:
            return f"Cannot connect to Bitbucket at {url if not is_cloud else 'api.bitbucket.org'}: connection refused"
        except requests.exceptions.Timeout:
            return f"Connection to Bitbucket at {url if not is_cloud else 'api.bitbucket.org'} timed out"
        except requests.exceptions.RequestException as e:
            return f"Error connecting to Bitbucket: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
