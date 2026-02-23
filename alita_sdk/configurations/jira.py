from typing import Optional
from urllib.parse import urlparse

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
        base_url = settings.get('base_url', '').strip().rstrip('/')
        username = settings.get('username')
        api_key = settings.get('api_key')
        token = settings.get('token')

        # Validate base URL
        if not base_url:
            return "Base URL is required"
        
        if not base_url.startswith(('http://', 'https://')):
            return "Base URL must start with http:// or https://"

        parsed = urlparse(base_url)
        if not parsed.netloc:
            return "Jira URL is invalid"

        host = (parsed.hostname or '').lower()
        path = (parsed.path or '').rstrip('/')

        # Normalised base URL: exactly what the user typed, minus trailing slash
        base_url = f"{parsed.scheme}://{parsed.netloc}{path}" if path and path != '/' \
            else f"{parsed.scheme}://{parsed.netloc}"

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

        # ── Validate against the Jira REST API ──
        # We try the URL *exactly as entered* by the user.
        # If it 404s we probe shorter prefixes to discover where the API
        # actually lives, but we still return an error — we never silently
        # "fix" the URL on the user's behalf.

        try:
            api_endpoint = f"{base_url}/rest/api/latest/myself"
            response = requests.get(
                api_endpoint,
                headers=headers,
                auth=auth,
                timeout=10,
            )

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    return (
                        "Invalid Jira base URL: server returned a non-JSON response. "
                        "Please use the base URL (e.g. 'https://yourinstance.atlassian.net') "
                        "without any extra path."
                    )
                return None  # Success — the URL is correct

            if response.status_code == 401:
                if has_token:
                    return "Authentication failed: Invalid bearer token"
                return "Authentication failed: Invalid username or API key"

            if response.status_code == 403:
                return "Access forbidden: Your account has insufficient permissions to access Jira API"

            if response.status_code == 404:
                # The exact URL didn't work.  Try to discover the correct
                # base URL so we can give the user a helpful suggestion.
                suggested = JiraConfiguration._discover_jira_base_url(
                    parsed, host, path, headers, auth,
                )
                if suggested:
                    return (
                        f"Jira API not found at the URL you entered. "
                        f"Did you mean '{suggested}'?"
                    )
                return (
                    "Jira API endpoint not found (404): Verify your base URL "
                    "(e.g. 'https://yourinstance.atlassian.net' or "
                    "'https://company.com/jira')."
                )

            # Any other status code — extract detail and report
            error_detail = ""
            try:
                error_json = response.json()
                if 'errorMessages' in error_json and error_json['errorMessages']:
                    error_detail = ": " + ", ".join(error_json['errorMessages'])
                elif 'message' in error_json:
                    error_detail = f": {error_json['message']}"
            except Exception:
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

    # ------------------------------------------------------------------ #
    #  Helper: probe shorter URL prefixes to suggest the correct base URL #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _discover_jira_base_url(parsed, host, path, headers, auth):
        """Try progressively shorter path prefixes to find a working Jira
        REST API root.  Returns the discovered base URL string, or *None*
        if nothing works.

        For Cloud hosts (*.atlassian.net) the API always lives at the root,
        so we only need to check there.
        For Server/DC, the API may sit behind a context path such as ``/jira``.
        """
        import requests

        candidates: list[str] = []

        if host.endswith('.atlassian.net'):
            candidates.append(f"{parsed.scheme}://{parsed.netloc}")
        else:
            if path and path != '/':
                segments = [s for s in path.split('/') if s]
                # Trim one segment at a time (skip the full path — we already
                # tried that in the caller)
                for i in range(len(segments) - 1, 0, -1):
                    candidates.append(
                        f"{parsed.scheme}://{parsed.netloc}/{'/'.join(segments[:i])}"
                    )
            candidates.append(f"{parsed.scheme}://{parsed.netloc}")

        # De-duplicate while preserving order
        candidates = list(dict.fromkeys(candidates))

        for candidate in candidates:
            try:
                resp = requests.get(
                    f"{candidate}/rest/api/latest/myself",
                    headers=headers,
                    auth=auth,
                    timeout=10,
                )
                if resp.status_code == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        return candidate
            except requests.exceptions.RequestException:
                continue

        return None
