import requests
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class TestIOConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "TestIO",
                "icon_url": "testio.svg",
                "section": "credentials",
                "type": "testio",
                "categories": ["testing"],
                "extra_categories": ["testio", "testing", "crowd testing", "qa"],
            }
        }
    )
    endpoint: str = Field(description="TestIO endpoint")
    api_key: SecretStr = Field(description="TestIO API Key")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Test the connection to TestIO API.

        Args:
            settings: Dictionary containing 'endpoint' and 'api_key' (both required)

        Returns:
            None if connection is successful, error message string otherwise
        """
        endpoint = settings.get("endpoint")
        if endpoint is None or endpoint == "":
            if endpoint == "":
                return "Endpoint cannot be empty"
            return "Endpoint is required"

        # Validate endpoint format
        if not isinstance(endpoint, str):
            return "Endpoint must be a string"
        
        endpoint = endpoint.strip()
        if not endpoint:
            return "Endpoint cannot be empty"
        if not endpoint.startswith(("http://", "https://")):
            return "Endpoint must start with http:// or https://"

        # Remove trailing slash for consistency
        endpoint = endpoint.rstrip("/")

        api_key = settings.get("api_key")
        if api_key is None:
            return "API key is required"

        # Extract secret value if it's a SecretStr
        if hasattr(api_key, "get_secret_value"):
            api_key = api_key.get_secret_value()

        # Validate API key is not empty
        if not api_key or not api_key.strip():
            return "API key cannot be empty"

        # Verification strategy:
        # Use an auth-required endpoint and a single, explicit auth scheme:
        #   Authorization: Token <token>
        url = f"{endpoint}/customer/v2/products"

        try:
            resp = TestIOConfiguration._get_with_token(url, api_key)

            if resp.status_code == 200:
                return None  # Connection successful
            if resp.status_code == 401:
                return "Invalid token"
            if resp.status_code == 403:
                return "Access forbidden - token has no access to /customer/v2/products"
            if resp.status_code == 404:
                return "Invalid endpoint. Verify TestIO base endpoint."
            if resp.status_code == 429:
                return "Rate limited - please try again later"
            if 500 <= resp.status_code <= 599:
                return f"TestIO service error (HTTP {resp.status_code})"
            return f"Connection failed (HTTP {resp.status_code})"

        except requests.exceptions.Timeout:
            return "Connection timeout - TestIO did not respond within 10 seconds"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach TestIO. Check endpoint URL and network."
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception:
            return "Unexpected error during TestIO connection check"

    @staticmethod
    def _get_with_token(url: str, token: str) -> requests.Response:
        """Perform an authenticated GET using `Authorization: Token <token>`."""
        return requests.get(
            url,
            headers={"Authorization": f"Token {token}"},
            timeout=10,
        )
