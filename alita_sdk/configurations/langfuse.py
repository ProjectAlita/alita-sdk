from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LangfuseConfiguration(BaseModel):
    """Configuration for Langfuse tracing integration"""
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Langfuse",
                "icon_url": None,
                "section": "credentials",
                "type": "langfuse",
                "categories": ["tracing"],
                "extra_categories": ["langfuse", "observability", "llm tracing", "monitoring"],
            }
        }
    )

    base_url: str = Field(
        description="Langfuse base URL (e.g., https://cloud.langfuse.com)",
        json_schema_extra={"title": "Base URL"}
    )
    public_key: str = Field(
        description="Langfuse public API key",
        json_schema_extra={"title": "Public Key"}
    )
    secret_key: SecretStr = Field(
        description="Langfuse secret API key",
        json_schema_extra={"title": "Secret Key", "format": "password"}
    )

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check connection to Langfuse using the provided credentials.
        Returns None if successful, error message otherwise.
        """
        import requests

        base_url = settings.get('base_url', '').rstrip('/')
        public_key = settings.get('public_key', '')
        secret_key = settings.get('secret_key', '')

        if not all([base_url, public_key, secret_key]):
            return "Missing required credentials: base_url, public_key, and secret_key are required"

        try:
            # Test connection by calling Langfuse projects endpoint (requires authentication)
            # Note: /api/public/health is unauthenticated and always returns 200,
            # so we use /api/public/projects which properly validates credentials
            response = requests.get(
                f"{base_url}/api/public/projects",
                auth=(public_key, secret_key),
                timeout=10
            )
            if response.status_code == 200:
                return None  # Success
            elif response.status_code == 401:
                return "Authentication failed: Invalid public_key or secret_key"
            elif response.status_code == 403:
                return "Access forbidden: Check your API key permissions"
            else:
                return f"Langfuse returned status {response.status_code}"
        except requests.exceptions.ConnectionError:
            return f"Connection error: Unable to reach Langfuse at {base_url}"
        except requests.exceptions.Timeout:
            return "Connection timeout: Langfuse did not respond in time"
        except requests.exceptions.RequestException as e:
            return f"Connection error: {str(e)}"
