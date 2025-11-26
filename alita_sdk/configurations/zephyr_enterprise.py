from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ZephyrEnterpriseConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Zephyr Enterprise",
                "icon_url": "zephyr.svg",
                "section": "credentials",
                "type": "zephyr_enterprise",
                "categories": ["test management"],
                "extra_categories": ["zephyr", "test automation", "test case management", "test planning"],
            }
        }
    )
    base_url: str = Field(description="Zephyr base URL")
    token: Optional[SecretStr] = Field(description="API token")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check the connection to Zephyr Enterprise.
        
        Args:
            settings: Dictionary containing Zephyr Enterprise configuration
                - base_url: Zephyr Enterprise instance URL (required)
                - token: API token for authentication (optional, anonymous access possible)
        
        Returns:
            None if connection successful, error message string if failed
        """
        import requests
        
        # Validate base_url
        base_url = settings.get("base_url", "").strip()
        if not base_url:
            return "Zephyr Enterprise URL is required"
        
        # Normalize URL - remove trailing slashes
        base_url = base_url.rstrip("/")
        
        # Basic URL validation
        if not base_url.startswith(("http://", "https://")):
            return "Zephyr Enterprise URL must start with http:// or https://"
        
        # Get token (optional)
        token = settings.get("token")
        
        # Prepare headers
        headers = {}
        has_token = False
        if token:
            # Extract token value if it's a SecretStr
            token_value = token.get_secret_value() if hasattr(token, 'get_secret_value') else token
            if token_value and str(token_value).strip():
                headers["Authorization"] = f"Bearer {str(token_value).strip()}"
                has_token = True
        
        # Use different endpoints based on whether authentication is provided
        # Note: /healthcheck may allow anonymous access, so we use authenticated endpoints when token is provided
        if has_token:
            # Test with an endpoint that requires authentication: /flex/services/rest/latest/project
            # This endpoint lists projects and requires proper authentication
            test_url = f"{base_url}/flex/services/rest/latest/user/current"
        else:
            # Without token, test basic connectivity with healthcheck
            test_url = f"{base_url}/flex/services/rest/latest/healthcheck"
        
        try:
            response = requests.get(
                test_url,
                headers=headers,
                timeout=10
            )
            
            # Check response status
            if response.status_code == 200:
                # Successfully connected
                return None
            elif response.status_code == 401:
                if has_token:
                    return "Authentication failed: invalid API token"
                else:
                    return "Authentication required: provide API token"
            elif response.status_code == 403:
                return "Access forbidden: check token permissions"
            elif response.status_code == 404:
                # If user endpoint not found, try healthcheck as fallback
                if has_token:
                    try:
                        fallback_url = f"{base_url}/flex/services/rest/latest/healthcheck"
                        fallback_response = requests.get(fallback_url, headers=headers, timeout=10)
                        if fallback_response.status_code == 200:
                            return None
                    except:
                        pass
                return "Zephyr Enterprise API endpoint not found: verify the Zephyr URL"
            else:
                return f"Zephyr Enterprise API returned status code {response.status_code}"

        except requests.exceptions.SSLError as e:
            return f"SSL certificate verification failed: {str(e)}"
        except requests.exceptions.ConnectionError:
            return f"Cannot connect to Zephyr Enterprise at {base_url}: connection refused"
        except requests.exceptions.Timeout:
            return f"Connection to Zephyr Enterprise at {base_url} timed out"
        except requests.exceptions.RequestException as e:
            return f"Error connecting to Zephyr Enterprise: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
