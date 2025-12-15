import re
from typing import Optional
from urllib.parse import quote

import requests
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AdoConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Ado",
                "icon_url": None,
                "section": "credentials",
                "type": "ado",
                "categories": ["project management"],
            }
        }
    )
    organization_url: str = Field(description="Base API URL")
    project: str = Field(description="ADO project")
    token: Optional[SecretStr] = Field(description="ADO Token")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Test the connection to Azure DevOps API.

        Args:
            settings: Dictionary containing 'organization_url', 'project', and optionally 'token'

        Returns:
            None if connection is successful, error message string otherwise
        """
        organization_url = settings.get("organization_url")
        if organization_url is None or organization_url == "":
            if organization_url == "":
                return "Organization URL cannot be empty"
            return "Organization URL is required"

        # Validate organization URL format
        if not isinstance(organization_url, str):
            return "Organization URL must be a string"

        organization_url = organization_url.strip()
        if not organization_url:
            return "Organization URL cannot be empty"

        if not organization_url.startswith(("http://", "https://")):
            return "Organization URL must start with http:// or https://"

        # Remove trailing slash for consistency
        organization_url = organization_url.rstrip("/")

        project = settings.get("project")
        if project is None or project == "":
            if project == "":
                return "Project cannot be empty"
            return "Project is required"

        # Validate project format
        if not isinstance(project, str):
            return "Project must be a string"

        project = project.strip()
        if not project:
            return "Project cannot be empty"

        token = settings.get("token")

        # Extract secret value if it's a SecretStr
        if token is not None and hasattr(token, "get_secret_value"):
            token = token.get_secret_value()

        # Validate token if provided
        if token is not None and (not token or not token.strip()):
            return "Token cannot be empty if provided"

        # NOTE on verification strategy:
        # - Project endpoints can work anonymously for public projects.
        #   That makes them a weak signal for detecting a bad/expired token.
        # - If a token is provided, first validate it against a profile endpoint
        #   that requires authentication, then check project access.

        # Strictly require a canonical organization URL so we can build reliable API URLs.
        # Supported formats:
        # - https://dev.azure.com/<org>
        # - https://<org>.visualstudio.com
        org_name: str | None = None
        org_url_kind: str | None = None  # 'dev.azure.com' | '*.visualstudio.com'
        m = re.match(r"^https?://dev\.azure\.com/(?P<org>[^/]+)$", organization_url, flags=re.IGNORECASE)
        if m:
            org_name = m.group('org')
            org_url_kind = 'dev.azure.com'
        else:
            m = re.match(r"^https?://(?P<org>[^/.]+)\.visualstudio\.com$", organization_url, flags=re.IGNORECASE)
            if m:
                org_name = m.group('org')
                org_url_kind = '*.visualstudio.com'

        if org_name is None:
            return (
                "Organization URL format is invalid. Use 'https://dev.azure.com/<org>' "
                "(recommended) or 'https://<org>.visualstudio.com'."
            )

        project_encoded = quote(project, safe="")
        project_url = f"{organization_url}/_apis/projects/{project_encoded}?api-version=7.0"
        # Auth-required endpoint to validate PAT (works regardless of project visibility)
        if org_url_kind == 'dev.azure.com':
            profile_url = f"https://vssps.dev.azure.com/{org_name}/_apis/profile/profiles/me?api-version=7.1-preview.3"
        else:
            # For legacy org URLs, use the matching vssps host
            profile_url = f"https://{org_name}.vssps.visualstudio.com/_apis/profile/profiles/me?api-version=7.1-preview.3"

        try:
            headers = {}
            if token:
                # Use Basic Auth with PAT token (username can be empty)
                from requests.auth import HTTPBasicAuth
                auth = HTTPBasicAuth("", token)

                # 1) Validate token first (strong signal)
                profile_resp = requests.get(profile_url, auth=auth, timeout=10)
                if profile_resp.status_code == 200:
                    pass
                elif profile_resp.status_code == 401:
                    return "Invalid or expired token (PAT). Please generate a new token and try again."
                elif profile_resp.status_code == 403:
                    return "Token is valid but lacks permission to access profile. Check PAT scopes/permissions."
                elif profile_resp.status_code == 404:
                    return "Organization not found. Verify the Organization URL."
                else:
                    return f"Token validation failed (HTTP {profile_resp.status_code})."

                # 2) Validate project access
                response = requests.get(project_url, auth=auth, timeout=10)
            else:
                # Try without authentication (works for public projects)
                response = requests.get(project_url, headers=headers, timeout=10)

            if response.status_code == 200:
                return None  # Connection successful
            elif response.status_code == 401:
                if token:
                    return "Not authorized. Token may be invalid for this organization or expired."
                else:
                    return "Authentication required - project may be private"
            elif response.status_code == 403:
                return "Access forbidden - token may lack required permissions for this project"
            elif response.status_code == 404:
                return f"Project '{project}' not found or not accessible. Check project name and organization URL."
            else:
                return f"Connection failed (HTTP {response.status_code})."

        except requests.exceptions.Timeout:
            return "Connection timeout - Azure DevOps did not respond within 10 seconds"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach Azure DevOps. Check the Organization URL and your network."
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception:
            return "Unexpected error during Azure DevOps connection check"


class AdoReposConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "ADO repos",
                "icon_url": "ado-repos-icon.svg",
                "section": "credentials",
                "type": "ado_repos",
                "categories": ["code repositories"],
            }
        }
    )
    repository_id: str = Field(description="ADO repository ID")

    ado_configuration: AdoConfiguration = Field(
        default_factory=AdoConfiguration,
        description="ADO configuration",
        json_schema_extra={
            'configuration_types': ['ado']
        }
    )
