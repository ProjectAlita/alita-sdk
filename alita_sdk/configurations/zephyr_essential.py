from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ZephyrEssentialConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Zephyr Essential",
                "icon_url": "zephyr.svg",
                "section": "credentials",
                "type": "zephyr_essential",
                "categories": ["test management"],
                "extra_categories": ["zephyr", "test automation", "test case management", "test planning"],
            }
        }
    )
    base_url: Optional[str] = Field(description="Zephyr Essential API Base URL", default=None)
    token: SecretStr = Field(description="Zephyr Essential API Token")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check the connection to Zephyr Essential (Zephyr Scale).
        
        Args:
            settings: Dictionary containing Zephyr Essential configuration
                - base_url: Zephyr Essential API Base URL (optional, defaults to Zephyr Scale Cloud API)
                - token: Zephyr Essential API Token (required)
        
        Returns:
            None if connection successful, error message string if failed
        """
        import requests
        
        # Get base_url or use default
        base_url = settings.get("base_url")
        if base_url:
            base_url = base_url.strip().rstrip("/")
            # Validate URL format if provided
            if not base_url.startswith(("http://", "https://")):
                return "Zephyr Essential URL must start with http:// or https://"
        else:
            # Default to Zephyr Scale Cloud API
            base_url = "https://api.zephyrscale.smartbear.com/v2"
        
        # Validate token
        token = settings.get("token")
        if not token:
            return "Zephyr Essential API token is required"
        
        # Extract token value if it's a SecretStr
        token_value = token.get_secret_value() if hasattr(token, 'get_secret_value') else token
        
        if not token_value or not str(token_value).strip():
            return "Zephyr Essential API token cannot be empty"
        
        # Test connection using /projects endpoint (requires authentication)
        test_url = f"{base_url}/projects"
        
        headers = {
            "Authorization": f"Bearer {str(token_value).strip()}"
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
                return "Authentication failed: invalid API token"
            elif response.status_code == 403:
                return "Access forbidden: token lacks required permissions"
            elif response.status_code == 404:
                return "Zephyr Essential API endpoint not found: verify the API URL"
            else:
                return f"Zephyr Essential API returned status code {response.status_code}"

        except requests.exceptions.SSLError as e:
            return f"SSL certificate verification failed: {str(e)}"
        except requests.exceptions.ConnectionError:
            return f"Cannot connect to Zephyr Essential at {base_url}: connection refused"
        except requests.exceptions.Timeout:
            return f"Connection to Zephyr Essential at {base_url} timed out"
        except requests.exceptions.RequestException as e:
            return f"Error connecting to Zephyr Essential: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
