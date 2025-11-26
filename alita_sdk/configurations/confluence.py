from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ConfluenceConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Confluence",
                "icon_url": "confluence.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Basic",
                                "fields": ["username", "api_key"]
                            },
                            {
                                "name": "Bearer",
                                "fields": ["token"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "confluence",
                "categories": ["documentation"],
                "extra_categories": ["confluence", "wiki", "documentation", "knowledge base"],
            }
        }
    )
    base_url: str = Field(description="Confluence URL")
    username: Optional[str] = Field(description="Confluence Username", default=None)
    api_key: Optional[SecretStr] = Field(description="Confluence API Key", default=None)
    token: Optional[SecretStr] = Field(description="Confluence Token", default=None)

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check the connection to Confluence.
        
        Args:
            settings: Dictionary containing Confluence configuration
                - base_url: Confluence instance URL (required)
                - username: Username for Basic Auth (optional)
                - api_key: API key/password for Basic Auth (optional)
                - token: Bearer token for authentication (optional)
        
        Returns:
            None if connection successful, error message string if failed
        """
        import requests
        from requests.auth import HTTPBasicAuth
        
        # Validate base_url
        base_url = settings.get("base_url", "").strip()
        if not base_url:
            return "Confluence URL is required"
        
        # Normalize URL - remove trailing slashes
        base_url = base_url.rstrip("/")
        
        # Basic URL validation
        if not base_url.startswith(("http://", "https://")):
            return "Confluence URL must start with http:// or https://"
        
        # Check authentication credentials
        username = settings.get("username")
        api_key = settings.get("api_key")
        token = settings.get("token")

        # Validate authentication - at least one method must be provided
        has_basic_auth = bool(username and api_key)
        has_token = bool(token and str(token).strip())
        
        # Determine authentication method
        auth_headers = {}
        auth = None
        
        if has_token:
            # Bearer token authentication
            token_value = token.get_secret_value() if hasattr(token, 'get_secret_value') else token
            auth_headers["Authorization"] = f"Bearer {token_value}"
        elif has_basic_auth:
            # Basic authentication
            api_key_value = api_key.get_secret_value() if hasattr(api_key, 'get_secret_value') else api_key
            auth = HTTPBasicAuth(username, api_key_value)
        else:
            return "Authentication required: provide either token or both username and api_key"
        
        # Test connection using /rest/api/user/current endpoint
        # This endpoint returns current user info and validates authentication
        test_url = f"{base_url}/rest/api/user/current"
        
        try:
            response = requests.get(
                test_url,
                auth=auth,
                headers=auth_headers,
                timeout=10
            )
            
            # Check response status
            if response.status_code == 200:
                # Successfully connected and authenticated
                return None
            elif response.status_code == 401:
                # Authentication failed
                if has_token:
                    return "Authentication failed: Invalid token"
                else:
                    return "Authentication failed: Invalid username or API key"
            elif response.status_code == 403:
                return """Access forbidden: check permissions and verify the credentials you provided.
Most probably you provided incorrect credentials (user name and api key or token)"""
            elif response.status_code == 404:
                return "Confluence API endpoint not found: verify the Confluence URL"
            else:
                return f"Confluence API returned status code {response.status_code}"

        except requests.exceptions.SSLError as e:
            return f"SSL certificate verification failed: {str(e)}"
        except requests.exceptions.ConnectionError:
            return f"Cannot connect to Confluence at {base_url}: connection refused"
        except requests.exceptions.Timeout:
            return f"Connection to Confluence at {base_url} timed out"
        except requests.exceptions.RequestException as e:
            return f"Error connecting to Confluence: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
