from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class XrayConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Xray Cloud",
                "icon_url": "xray.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Client Credentials",
                                "fields": ["client_id", "client_secret"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "xray",
                "categories": ["test management"],
                "extra_categories": ["xray", "test automation", "test case management", "test planning"],
            }
        }
    )
    base_url: str = Field(description="Xray URL")
    client_id: Optional[str] = Field(description="Client ID")
    client_secret: Optional[SecretStr] = Field(description="Client secret")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check the connection to Xray Cloud.
        
        Args:
            settings: Dictionary containing Xray configuration
                - base_url: Xray Cloud URL (required)
                - client_id: OAuth2 Client ID (required)
                - client_secret: OAuth2 Client Secret (required)
        
        Returns:
            None if connection successful, error message string if failed
        """
        import requests
        
        # Validate base_url
        base_url = settings.get("base_url", "").strip()
        if not base_url:
            return "Xray URL is required"
        
        # Normalize URL - remove trailing slashes
        base_url = base_url.rstrip("/")
        
        # Basic URL validation
        if not base_url.startswith(("http://", "https://")):
            return "Xray URL must start with http:// or https://"
        
        # Validate client_id
        client_id = settings.get("client_id", "").strip() if settings.get("client_id") else ""
        if not client_id:
            return "Xray client ID is required"
        
        # Validate client_secret
        client_secret = settings.get("client_secret")
        if not client_secret:
            return "Xray client secret is required"
        
        # Extract client_secret value if it's a SecretStr
        client_secret_value = client_secret.get_secret_value() if hasattr(client_secret, 'get_secret_value') else client_secret
        
        if not client_secret_value or not str(client_secret_value).strip():
            return "Xray client secret cannot be empty"
        
        # Test connection using /api/v2/authenticate endpoint
        # This is the OAuth2 token generation endpoint for Xray Cloud
        auth_url = f"{base_url}/api/v2/authenticate"
        
        auth_payload = {
            "client_id": client_id,
            "client_secret": str(client_secret_value).strip()
        }
        
        try:
            response = requests.post(
                auth_url,
                json=auth_payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            # Check response status
            if response.status_code == 200:
                # Successfully authenticated and got token
                return None
            elif response.status_code == 401:
                return "Authentication failed: invalid client ID or secret"
            elif response.status_code == 403:
                return "Access forbidden: check client credentials"
            elif response.status_code == 400:
                # Bad request - could be invalid format
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", "Bad request")
                    return f"Bad request: {error_msg}"
                except:
                    return "Bad request: check client ID and secret format"
            elif response.status_code == 404:
                return "Xray API endpoint not found: verify the Xray URL"
            else:
                return f"Xray API returned status code {response.status_code}"

        except requests.exceptions.SSLError as e:
            return f"SSL certificate verification failed: {str(e)}"
        except requests.exceptions.ConnectionError:
            return f"Cannot connect to Xray at {base_url}: connection refused"
        except requests.exceptions.Timeout:
            return f"Connection to Xray at {base_url} timed out"
        except requests.exceptions.RequestException as e:
            return f"Error connecting to Xray: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
