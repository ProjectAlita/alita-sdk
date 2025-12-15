import re

import requests
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class QtestConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "QTest",
                "icon_url": "qtest.svg",
                "categories": ["test management"],
                "section": "credentials",
                "type": "qtest",
                "extra_categories": ["quality assurance", "test case management", "test planning"]
            }
        }
    )
    base_url: str = Field(description="QTest base URL")
    qtest_api_token: SecretStr = Field(description="QTest API token")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """Check connectivity and credentials for qTest.

        Strategy:
        - Validate token against an auth-required endpoint (so an incorrect token is detected).

        Returns:
            None if successful, otherwise a short actionable error message.
        """
        base_url_input = settings.get("base_url")
        base_url = base_url_input.strip() if isinstance(base_url_input, str) else ""
        if not base_url:
            return "QTest base URL is required"

        if not base_url.startswith(("http://", "https://")):
            return "QTest base URL must start with http:// or https://"

        base_url = base_url.rstrip("/")
        # If user pasted /api/v3 (or similar), strip it so we can build canonical API URLs.
        base_url = re.sub(r"/api/v\d+/?$", "", base_url, flags=re.IGNORECASE)

        token = settings.get("qtest_api_token")
        if token is None:
            return "QTest API token is required"
        token_value = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token)
        if not token_value or not token_value.strip():
            return "QTest API token cannot be empty"

        headers = {
            "Authorization": f"Bearer {token_value}",
            "Content-Type": "application/json",
        }

        # Auth-required endpoint to validate the token.
        # /projects works on v3 and requires auth in typical qTest deployments.
        token_check_url = f"{base_url}/api/v3/projects?pageSize=1&page=1"

        try:
            resp = requests.get(token_check_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return None
            elif resp.status_code == 401:
                return "Invalid or expired QTest API token"
            elif resp.status_code == 403:
                return "Access forbidden - token lacks required permissions"
            elif resp.status_code == 404:
                return "QTest API not found (404) - verify base URL (do not include /api/v3)"
            elif resp.status_code == 429:
                return "Rate limited (429) - please try again later"
            elif 500 <= resp.status_code <= 599:
                return f"QTest service error (HTTP {resp.status_code})"
            else:
                return f"QTest connection failed (HTTP {resp.status_code})"

        except requests.exceptions.Timeout:
            return "Connection timeout - qTest did not respond within 10 seconds"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach qTest. Check base URL and network."
        except requests.exceptions.SSLError:
            return "SSL error - certificate verification failed"
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception:
            return "Unexpected error during qTest connection check"



