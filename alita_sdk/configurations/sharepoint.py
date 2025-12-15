import requests
from office365.onedrive.sharepoint_settings import SharepointSettings
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SharepointConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "SharePoint",
                "icon_url": "sharepoint.svg",
                "section": "credentials",
                "type": "sharepoint",
                "categories": ["office"],
                "extra_categories": ["sharepoint", "microsoft", "documents", "collaboration"],
            }
        }
    )
    client_id: str = Field(description="SharePoint Client ID")
    client_secret: SecretStr = Field(description="SharePoint Client Secret")
    site_url: str = Field(description="SharePoint Site URL")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Test the connection to SharePoint API using OAuth2 client credentials.

        Args:
            settings: Dictionary containing 'client_id', 'client_secret', and 'site_url' (all required)

        Returns:
            None if connection is successful, error message string otherwise
        """
        # Validate client_id
        client_id = settings.get("client_id")
        if client_id is None or client_id == "":
            if client_id == "":
                return "Client ID cannot be empty"
            return "Client ID is required"

        if not isinstance(client_id, str):
            return "Client ID must be a string"

        client_id = client_id.strip()
        if not client_id:
            return "Client ID cannot be empty"

        # Validate client_secret
        client_secret = settings.get("client_secret")
        if client_secret is None:
            return "Client secret is required"

        # Extract secret value if it's a SecretStr
        if hasattr(client_secret, "get_secret_value"):
            client_secret = client_secret.get_secret_value()

        if not client_secret or not client_secret.strip():
            return "Client secret cannot be empty"

        # Validate site_url
        site_url = settings.get("site_url")
        if site_url is None or site_url == "":
            if site_url == "":
                return "Site URL cannot be empty"
            return "Site URL is required"

        if not isinstance(site_url, str):
            return "Site URL must be a string"

        site_url = site_url.strip()
        if not site_url:
            return "Site URL cannot be empty"

        if not site_url.startswith(("http://", "https://")):
            return "Site URL must start with http:// or https://"

        # Remove trailing slash for consistency
        site_url = site_url.rstrip("/")

        # Extract tenant and resource from site URL
        # Expected format: https://<tenant>.sharepoint.com/sites/<site>
        try:
            if ".sharepoint.com" not in site_url:
                return "Site URL must be a valid SharePoint URL (*.sharepoint.com)"

            # Extract tenant (e.g., "contoso" from "contoso.sharepoint.com")
            parts = site_url.split("//")[1].split(".")
            if len(parts) < 3:
                return "Invalid SharePoint URL format"
            tenant = parts[0]

            # Build token endpoint
            token_url = f"https://accounts.accesscontrol.windows.net/{tenant}.onmicrosoft.com/tokens/OAuth/2"

            # Build resource (the site URL with /_api appended)
            resource = f"{site_url.split('/sites/')[0]}@{site_url.split('//')[1].split('/')[0].split('.')[0]}"

        except Exception:
            return "Failed to parse SharePoint URL - ensure it's in format: https://<tenant>.sharepoint.com/sites/<site>"

        try:
            # Step 1: Get OAuth2 access token using client credentials
            token_response = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": f"{client_id}@{tenant}.onmicrosoft.com",
                    "client_secret": client_secret,
                    "resource": f"00000003-0000-0ff1-ce00-000000000000/{site_url.split('//')[1].split('/')[0]}@{tenant}.onmicrosoft.com"
                },
                timeout=10,
            )

            if token_response.status_code == 400:
                try:
                    error_data = token_response.json()
                    error_desc = error_data.get("error_description", "")
                    if "not found in the directory" in error_desc.lower():
                        return "Invalid client ID. Please check if you provide a correct client ID and try again."
                    elif "client_secret" in error_desc.lower():
                        return "Invalid client secret"
                    else:
                        return f"OAuth2 authentication failed: {error_desc}"
                except Exception:
                    return "Invalid client credentials"

            elif token_response.status_code == 401:
                return "Invalid client secret provided. Please check if you provide a correct client secret and try again."
            elif token_response.status_code != 200:
                return f"Failed to obtain access token (status {token_response.status_code})"

            # Extract access token
            try:
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    return "No access token received from SharePoint"
            except Exception:
                return "Failed to parse token response"

            # Step 2: Test the access token by calling SharePoint API
            api_url = f"{site_url}/_api/web"
            api_response = requests.get(
                api_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )

            if api_response.status_code == 200:
                return None  # Connection successful
            elif api_response.status_code == 401:
                return "Access token is invalid or expired"
            elif api_response.status_code == 403:
                return "Access forbidden - client may lack required permissions for this site"
            elif api_response.status_code == 404:
                return f"Site not found or not accessible: {site_url}"
            else:
                return f"SharePoint API request failed with status {api_response.status_code}"

        except requests.exceptions.Timeout:
            return "Connection timeout - SharePoint is not responding"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach SharePoint"
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
