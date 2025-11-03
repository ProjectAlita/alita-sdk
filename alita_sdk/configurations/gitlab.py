from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class GitlabConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "GitLab",
                "icon_url": None,
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "GitLab private token",
                                "fields": ["private_token"]
                            }
                        ]
                    }
                },
                "section": "credentials",
                "type": "gitlab",
                "categories": ["code repositories"],
                "extra_categories": ["gitlab", "git", "repository", "code", "version control"],
            }
        }
    )
    url: str = Field(description="GitLab URL")
    private_token: SecretStr = Field(description="GitLab private token")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check the connection to GitLab.
        
        Args:
            settings: Dictionary containing GitLab configuration
                - url: GitLab instance URL (required)
                - private_token: GitLab private token for authentication (required)
        
        Returns:
            None if connection successful, error message string if failed
        """
        import requests
        
        # Validate url
        url = settings.get("url", "").strip()
        if not url:
            return "GitLab URL is required"
        
        # Normalize URL - remove trailing slashes
        url = url.rstrip("/")
        
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return "GitLab URL must start with http:// or https://"
        
        # Validate private_token
        private_token = settings.get("private_token")
        if not private_token:
            return "GitLab private token is required"
        
        # Extract token value if it's a SecretStr
        token_value = private_token.get_secret_value() if hasattr(private_token, 'get_secret_value') else private_token
        
        if not token_value or not str(token_value).strip():
            return "GitLab private token cannot be empty"
        
        # Test connection using /api/v4/user endpoint
        # This endpoint returns current authenticated user info
        test_url = f"{url}/api/v4/user"
        
        # GitLab supports both PRIVATE-TOKEN header and Authorization Bearer
        # Using PRIVATE-TOKEN is GitLab-specific and more explicit
        headers = {
            "PRIVATE-TOKEN": str(token_value).strip()
        }
        
        try:
            response = requests.get(
                test_url,
                headers=headers,
                timeout=10
            )
            
            # Check response status
            if response.status_code == 200:
                # Successfully connected and authenticated
                return None
            elif response.status_code == 401:
                return "Authentication failed: invalid private token"
            elif response.status_code == 403:
                return "Access forbidden: token lacks required permissions"
            elif response.status_code == 404:
                return "GitLab API endpoint not found: verify the GitLab URL"
            else:
                return f"GitLab API returned status code {response.status_code}"

        except requests.exceptions.SSLError as e:
            return f"SSL certificate verification failed: {str(e)}"
        except requests.exceptions.ConnectionError:
            return f"Cannot connect to GitLab at {url}: connection refused"
        except requests.exceptions.Timeout:
            return f"Connection to GitLab at {url} timed out"
        except requests.exceptions.RequestException as e:
            return f"Error connecting to GitLab: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
