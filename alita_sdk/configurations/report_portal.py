from urllib.parse import quote, urlparse, urlunparse

import requests
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ReportPortalConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Report Portal",
                "icon_url": "report_portal.svg",
                "section": "credentials",
                "type": "report_portal",
                "categories": ["testing"],
                "extra_categories": ["report portal", "testing", "automation", "reports"],
            }
        }
    )
    project: str = Field(description="Report Portal Project Name")
    endpoint: str = Field(description="Report Portal Endpoint URL")
    api_key: SecretStr = Field(description="Report Portal API Key")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """Check the connection to ReportPortal.

        Validates:
        - endpoint URL format and reachability
        - API key (token) via an auth-required endpoint
        - project access (because most ReportPortal APIs are scoped to a project)

        Returns:
            None if connection successful, error message string otherwise
        """
        endpoint_in = settings.get("endpoint")
        endpoint = endpoint_in.strip() if isinstance(endpoint_in, str) else ""
        if not endpoint:
            return "Endpoint is required"

        if not endpoint.startswith(("http://", "https://")):
            return "Endpoint must start with http:// or https://"

        # Normalize: remove query/fragment and trailing slash.
        parsed = urlparse(endpoint)
        endpoint = urlunparse(parsed._replace(query="", fragment="")).rstrip("/")

        # If user pasted an API URL, normalize back to base endpoint.
        # Common pastes: .../api/v1 or .../api/v1/<project>
        # lowered = endpoint.lower()
        # for suffix in ("/api/v1", "/api"):
        #     if lowered.endswith(suffix):
        #         endpoint = endpoint[: -len(suffix)].rstrip("/")
        #         lowered = endpoint.lower()
        #         break

        project_in = settings.get("project")
        project = project_in.strip() if isinstance(project_in, str) else ""
        if not project:
            return "Project is required"

        api_key = settings.get("api_key")
        if api_key is None:
            return "API key is required"
        api_key_value = api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else str(api_key)
        if not api_key_value or not api_key_value.strip():
            return "API key cannot be empty"

        # Auth-required endpoint for verification.
        # /user endpoint validates the token and project context.
        project_encoded = quote(project, safe="")
        test_url = f"{endpoint}/api/v1/project/{project_encoded}"

        try:
            resp = requests.get(
                test_url,
                headers={"Authorization": f"Bearer {api_key_value}"},
                timeout=10,
            )

            if resp.status_code == 200:
                return None
            if resp.status_code == 401:
                return "Invalid API key"
            if resp.status_code == 403:
                return "Access forbidden - API key has no access to this project"
            if resp.status_code == 404:
                return "API endpoint not found (404) - verify endpoint URL and project name"
            if resp.status_code == 429:
                return "Rate limited (429) - please try again later"
            if 500 <= resp.status_code <= 599:
                return f"ReportPortal service error (HTTP {resp.status_code})"
            return f"Connection failed (HTTP {resp.status_code})"

        except requests.exceptions.Timeout:
            return "Connection timeout - ReportPortal did not respond within 10 seconds"
        except requests.exceptions.SSLError as e:
            if "Hostname mismatch" in str(e):
                return "API endpoint not found - verify endpoint URL and project name"
            return "SSL error - certificate verification failed"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach ReportPortal. Check endpoint URL and network."
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception:
            return "Unexpected error during ReportPortal connection check"

if __name__ == '__main__':
    settings = {
        "endpoint": "https://reportportal.epam.com",
        "project": "epm-alta",
        "api_key": "my-api-key_U1kF0zFvToqcweG3x552cI8pnYkMqszgtht_LHGZhpxwrxDl5nXlmrSf_JLEE8jy",
    }

    print(ReportPortalConfiguration.check_connection(settings))
