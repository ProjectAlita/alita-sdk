from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class JiraConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Jira",
                "icon_url": "jira.svg",
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
                "type": "jira",
                "categories": ["project management"],
                "extra_categories": ["jira", "issue tracking", "project management", "agile"],
            }
        }
    )
    base_url: str = Field(description="Jira URL")
    username: Optional[str] = Field(description="Jira Username", default=None)
    api_key: Optional[SecretStr] = Field(description="Jira API Key", default=None)
    token: Optional[SecretStr] = Field(description="Jira Token", default=None)

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check Jira connection using provided settings.
        Returns None if connection is successful, error message otherwise.
        
        Tests authentication by calling the /rest/api/latest/myself endpoint,
        which returns information about the currently authenticated user.
        """
        import requests
        from requests.auth import HTTPBasicAuth

        # Extract and validate settings
        base_url = settings.get('base_url', '').rstrip('/')
        username = settings.get('username')
        api_key = settings.get('api_key')
        token = settings.get('token')

        # Validate base URL
        if not base_url:
            return "Base URL is required"
        
        if not base_url.startswith(('http://', 'https://')):
            return "Base URL must start with http:// or https://"

        # Validate authentication - at least one method must be provided
        has_basic_auth = bool(username and api_key)
        has_token = bool(token and str(token).strip())

        if not (has_basic_auth or has_token):
            return "Authentication required: Provide either username + API key, or bearer token"

        # Setup authentication headers
        headers = {'Accept': 'application/json'}
        auth = None

        if has_token:
            # Bearer token authentication
            token_value = token.get_secret_value() if hasattr(token, 'get_secret_value') else token
            headers['Authorization'] = f'Bearer {token_value}'
        elif has_basic_auth:
            # Basic authentication
            api_key_value = api_key.get_secret_value() if hasattr(api_key, 'get_secret_value') else api_key
            auth = HTTPBasicAuth(username, api_key_value)

        # Build API endpoint - using 'latest' for version independence
        api_endpoint = f"{base_url}/rest/api/latest/myself"

        try:
            # Make authenticated request to verify credentials
            response = requests.get(
                api_endpoint,
                headers=headers,
                auth=auth,
                timeout=10
            )

            # Handle different response codes
            if response.status_code == 200:
                return None  # Success - credentials are valid
            
            elif response.status_code == 401:
                # Authentication failed
                if has_token:
                    return "Authentication failed: Invalid bearer token"
                else:
                    return "Authentication failed: Invalid username or API key"
            
            elif response.status_code == 403:
                # Authenticated but insufficient permissions
                return "Access forbidden: Your account has insufficient permissions to access Jira API"
            
            elif response.status_code == 404:
                # API endpoint not found - likely wrong URL
                return "Jira API endpoint not found: Verify your base URL (e.g., 'https://yourinstance.atlassian.net')"
            
            else:
                # Other HTTP errors - try to extract Jira error messages
                error_detail = ""
                try:
                    error_json = response.json()
                    if 'errorMessages' in error_json and error_json['errorMessages']:
                        error_detail = ": " + ", ".join(error_json['errorMessages'])
                    elif 'message' in error_json:
                        error_detail = f": {error_json['message']}"
                except:
                    pass
                
                return f"Connection failed with status {response.status_code}{error_detail}"

        except requests.exceptions.SSLError:
            return "SSL certificate verification failed: Check your Jira URL or network settings"
        except requests.exceptions.ConnectionError:
            return "Connection error: Unable to reach Jira server - check URL and network connectivity"
        except requests.exceptions.Timeout:
            return "Connection timeout: Jira server did not respond within 10 seconds"
        except requests.exceptions.MissingSchema:
            return "Invalid URL format: URL must include protocol (http:// or https://)"
        except requests.exceptions.InvalidURL:
            return "Invalid URL format: Please check your Jira base URL"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
