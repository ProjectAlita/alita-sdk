from typing import Optional
from urllib.parse import urlparse, urlunparse

from atlassian import Confluence
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
        base_url_input = settings.get("base_url", "")
        base_url = base_url_input.strip() if isinstance(base_url_input, str) else ""
        if not base_url:
            return "Confluence URL is required"
        
        # Basic URL validation
        if not base_url.startswith(("http://", "https://")):
            return "Confluence URL must start with http:// or https://"

        # Normalize URL - remove trailing slashes
        base_url = base_url.rstrip("/")

        # Build candidate base URLs.
        # Confluence Cloud REST API is typically under /wiki. Users often paste
        # https://<site>.atlassian.net and shouldn't be forced to know about /wiki.
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""

        def with_wiki_path(url: str) -> str:
            p = urlparse(url)
            # Keep existing path if it already starts with /wiki
            if (p.path or "").startswith("/wiki"):
                return url
            # Append /wiki, preserving any existing path (rare but safe)
            new_path = (p.path or "") + "/wiki"
            return urlunparse(p._replace(path=new_path.rstrip("/")))

        candidate_base_urls: list[str] = []
        if host.endswith(".atlassian.net"):
            # For Atlassian Cloud, prefer the /wiki variant first
            candidate_base_urls.append(with_wiki_path(base_url))
        candidate_base_urls.append(base_url)
        # De-duplicate while preserving order
        candidate_base_urls = list(dict.fromkeys(candidate_base_urls))
        
        # Check authentication credentials
        username = settings.get("username")
        api_key = settings.get("api_key")
        token = settings.get("token")

        api_key_value = api_key.get_secret_value() if hasattr(api_key, 'get_secret_value') else api_key
        token_value = token.get_secret_value() if hasattr(token, 'get_secret_value') else token

        # Validate authentication - at least one method must be provided
        has_basic_auth = bool(username and api_key_value and str(api_key_value).strip())
        has_token = bool(token_value and str(token_value).strip())
        
        # Determine authentication method
        auth_headers = {}
        auth = None
        
        if has_token:
            # Bearer token authentication
            auth_headers["Authorization"] = f"Bearer {token_value}"
        elif has_basic_auth:
            # Basic authentication
            auth = HTTPBasicAuth(username, api_key_value)
        else:
            return "Authentication required: provide either token or both username and api_key"
        
        try:
            # Test connection using /rest/api/user/current endpoint
            # This endpoint returns current user info and validates authentication
            last_status = None
            for candidate_base in candidate_base_urls:
                test_url = f"{candidate_base}/rest/api/user/current"
                response = requests.get(
                    test_url,
                    auth=auth,
                    headers=auth_headers,
                    timeout=10
                )
                last_status = response.status_code

                if response.status_code == 200:
                    return None

                # If we get 404 on the first candidate, try the next one
                if response.status_code == 404:
                    continue

                if response.status_code == 401:
                    return "Invalid credentials (401) - check token or username/api_key"
                if response.status_code == 403:
                    return "Access forbidden (403) - credentials lack Confluence permissions"
                if response.status_code == 429:
                    return "Rate limited (429) - please try again later"
                if 500 <= response.status_code <= 599:
                    return f"Confluence service error (HTTP {response.status_code})"
                return f"Confluence request failed (HTTP {response.status_code})"

            # All candidates returned 404
            return "Confluence API endpoint not found (404) - verify the Confluence URL"

        except requests.exceptions.SSLError as e:
            if 'Hostname mismatch' in str(e):
                return "SSL error - hostname mismatch. Verify the Confluence URL"
            return "SSL error - certificate verification failed"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach Confluence. Check URL and network."
        except requests.exceptions.Timeout:
            return "Connection timeout - Confluence did not respond within 10 seconds. Check URL and network."
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception:
            return "Unexpected error during Confluence connection check"
