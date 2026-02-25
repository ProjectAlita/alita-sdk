import requests
import logging
from typing import Optional, List, Tuple, Dict
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

log = logging.getLogger(__name__)


class SharepointConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "SharePoint",
                "icon_url": "sharepoint.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "App-only",
                                "fields": []
                            },
                            {
                                "name": "Delegated",
                                "fields": ["oauth_discovery_endpoint", "scopes"]
                            }
                        ]
                    }
                },
                "section": "credentials",
                "type": "sharepoint",
                "categories": ["office"],
                "extra_categories": ["sharepoint", "microsoft", "documents", "collaboration"],
            }
        }
    )
    # Client credentials (shared by both app_auth and delegated flows)
    client_id: Optional[str] = Field(default=None, description="SharePoint Client ID")
    client_secret: Optional[SecretStr] = Field(default=None, description="SharePoint Client Secret")
    site_url: Optional[str] = Field(default=None, description="SharePoint Site URL")

    # Additional fields for delegated/OAuth flows
    oauth_discovery_endpoint: Optional[str] = Field(default=None, description="OAuth Discovery Endpoint. Usually in format: https://login.microsoftonline.com/{tenant_id}")
    scopes: Optional[List[str]] = Field(default=None, description="OAuth Scopes")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Test the connection to SharePoint API.

        Two authentication flows are supported:

        **Delegated flow** (when ``oauth_discovery_endpoint`` is present):
            An ``access_token`` must be supplied in *settings*.  If it is absent,
            ``McpAuthorizationRequired`` is raised so the caller can trigger the
            OAuth authorization dance and retry with the obtained token.
            The health-check uses the Microsoft Graph API
            (``graph.microsoft.com/v1.0/sites/{host}:{path}``) because delegated
            tokens issued by Azure AD are Graph tokens and are **not** accepted by
            the SharePoint REST ``/_api/web`` endpoint.

        **App-auth / client-credentials flow** (when ``oauth_discovery_endpoint`` is absent):
            ``client_id``, ``client_secret``, and ``site_url`` are used to obtain a
            token from the SharePoint legacy ACS endpoint, which is then verified
            against the SharePoint REST ``/_api/web`` endpoint.

        Args:
            settings: Dictionary that may contain:
                - site_url (required for both flows)
                - oauth_discovery_endpoint: activates the delegated flow
                - access_token: pre-obtained OAuth bearer token (delegated flow only)
                - client_id / client_secret: app credentials (client-credentials flow only)

        Returns:
            None if connection is successful, error message string otherwise.

        Raises:
            McpAuthorizationRequired: when the delegated flow is required but no
                ``access_token`` has been provided yet, or when the provided token
                is invalid / expired.
        """
        oauth_discovery_endpoint = settings.get("oauth_discovery_endpoint")
        if oauth_discovery_endpoint:
            log.debug(f"Testing SharePoint connection with oauth flow")
            return SharepointConfiguration._check_connection_delegated(settings, oauth_discovery_endpoint)
        log.debug(f'Testing SharePoint connection with App-Only flow")')
        return SharepointConfiguration._check_connection_client_credentials(settings)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_site_url(settings: dict) -> Tuple[Optional[str], Optional[str]]:
        """Validate and normalise ``site_url`` from settings.

        Returns:
            ``(site_url, None)`` on success or ``(None, error_message)`` on failure.
        """
        site_url = settings.get("site_url")
        if site_url is None or site_url == "":
            return None, ("Site URL cannot be empty" if site_url == "" else "Site URL is required")
        if not isinstance(site_url, str):
            return None, "Site URL must be a string"
        site_url = site_url.strip()
        if not site_url:
            return None, "Site URL cannot be empty"
        if not site_url.startswith(("http://", "https://")):
            return None, "Site URL must start with http:// or https://"
        return site_url.rstrip("/"), None

    @staticmethod
    def _extract_api_error_message(response) -> str:
        """Extract a human-readable error message from a SharePoint / Graph API error response.

        SharePoint can return the error in two shapes:
            ``{'code': '...', 'message': '...', 'innerError': {...}}``
            ``{'error': {'code': '...', 'message': '...', 'innerError': {...}}}``
        Falls back to the raw response text when the body cannot be parsed.
        """
        try:
            body = response.json()
            # Graph-style: top-level 'error' wrapper
            if "error" in body and isinstance(body["error"], dict):
                return body["error"].get("message") or str(body["error"])
            # SharePoint-style: 'message' at top level
            if "message" in body:
                return body["message"]
            return str(body)
        except Exception:
            return response.text or "unknown error"

    @staticmethod
    def _build_mcp_authorization_required(
        message: str,
        site_url: str,
        oauth_discovery_endpoint: str,
        scopes: Optional[List[str]],
        status: Optional[int] = None,
    ) -> "McpAuthorizationRequired":
        """Build a ``McpAuthorizationRequired`` exception with the same rich metadata
        shape that the MCP OAuth flow produces, so upstream handlers can treat
        SharePoint delegated auth identically to MCP server auth.

        Delegates discovery to ``fetch_oauth_authorization_server_metadata`` from
        ``mcp_oauth.py``, passing the Azure AD v2.0 URL as an ``extra_endpoint``
        so it is tried first before the standard candidates — no duplicated fetch
        logic in this file.
        """
        log.debug(f"build_mcp_authorization_request for {message}, site_url={site_url}, oauth_discovery_endpoint={oauth_discovery_endpoint}, scopes={scopes}")
        from ..runtime.utils.mcp_oauth import (
            McpAuthorizationRequired,
            fetch_oauth_authorization_server_metadata,
        )

        base_discovery = oauth_discovery_endpoint.rstrip("/")
        # Azure AD v2.0 well-known URL — injected as an extra candidate so the
        # shared helper tries it first, then falls back to the standard ones.
        azure_v2_endpoint = f"{base_discovery}/v2.0/.well-known/openid-configuration"

        openid_meta = fetch_oauth_authorization_server_metadata(
            base_discovery,
            extra_endpoints=[azure_v2_endpoint],
        )

        # resource_metadata_url points to whichever endpoint actually responded,
        # or to the v2.0 URL as a sensible default when discovery fails.
        resource_metadata_url = azure_v2_endpoint
        log.debug(f"Fetched OpenID metadata for SharePoint OAuth discovery: {openid_meta}")

        authorization_endpoint = (openid_meta or {}).get(
            "authorization_endpoint",
            f"{base_discovery}/v2.0/oauth2/authorize",
        )
        token_endpoint = (openid_meta or {}).get(
            "token_endpoint",
            f"{base_discovery}/v2.0/oauth2/token",
        )
        jwks_uri = (openid_meta or {}).get("jwks_uri")
        issuer = (openid_meta or {}).get("issuer", base_discovery)
        scopes_supported = list((openid_meta or {}).get("scopes_supported") or [])
        if scopes:
            for s in scopes:
                if s not in scopes_supported:
                    scopes_supported.append(s)

        www_authenticate = (
            f'Bearer error="unauthorized_client", '
            f'error_description="No access token was provided in this request", '
            f'resource_metadata="{resource_metadata_url}", '
            f'authorization_uri="{authorization_endpoint}"'
        )

        oauth_authorization_server: Dict = {
            "issuer": issuer,
            "authorization_endpoint": authorization_endpoint,
            "token_endpoint": token_endpoint,
        }
        if jwks_uri:
            oauth_authorization_server["jwks_uri"] = jwks_uri
        if scopes_supported:
            oauth_authorization_server["scopes_supported"] = scopes_supported
        if openid_meta:
            for key in ("response_types_supported", "claims_supported",
                        "id_token_signing_alg_values_supported"):
                if key in openid_meta:
                    oauth_authorization_server[key] = openid_meta[key]

        resource_metadata: Dict = {
            "resource_name": "SharePoint",
            "resource": site_url,
            "authorization_servers": [base_discovery],
            "bearer_methods_supported": ["header"],
            "oauth_authorization_server": oauth_authorization_server,
        }
        if scopes:
            resource_metadata["scopes_supported"] = scopes
        log.debug(f"SharePoint resource_metadata: {resource_metadata}")
        return McpAuthorizationRequired(
            message=message,
            server_url=site_url,
            resource_metadata_url=resource_metadata_url,
            www_authenticate=www_authenticate,
            resource_metadata=resource_metadata,
            status=status,
            tool_name=site_url,
        )

    @staticmethod
    def _call_graph_api(site_url: str, access_token: str, oauth_discovery_endpoint: str, scopes: Optional[List[str]] = None) -> str | None:
        """Health-check a delegated access token using the Microsoft Graph API.

        Delegated (Azure AD) tokens are Graph tokens and are rejected by the
        SharePoint REST ``/_api/web`` endpoint.  The correct probe is
        ``GET https://graph.microsoft.com/v1.0/sites/{hostname}:{path}``
        which returns the site metadata when the token is valid.

        On HTTP 401 the response body is parsed and ``McpAuthorizationRequired``
        is raised with the full OAuth re-authorization context — same rich shape
        as MCP server auth — so the upstream handler can restart the flow.

        Args:
            site_url: Normalised SharePoint site URL.
            access_token: Delegated OAuth bearer token.
            oauth_discovery_endpoint: Azure AD base URL (e.g.
                ``https://login.microsoftonline.com/{tenant_id}``).
            scopes: Configured OAuth scopes, forwarded into resource_metadata.

        Returns:
            ``None`` on success, error message string otherwise.

        Raises:
            McpAuthorizationRequired: when the token is invalid or expired (401).
        """
        from ..runtime.utils.mcp_oauth import McpAuthorizationRequired
        try:
            parsed = urlparse(site_url)
            hostname = parsed.netloc
            path = parsed.path or "/"

            graph_url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:{path}"
            resp = requests.get(
                graph_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )

            if resp.status_code == 200:
                return None
            elif resp.status_code == 401:
                api_message = SharepointConfiguration._extract_api_error_message(resp)
                raise SharepointConfiguration._build_mcp_authorization_required(
                    message=(
                        f"SharePoint delegated access token is invalid or expired: {api_message}. "
                        "Please re-authorize to obtain a fresh access token."
                    ),
                    site_url=site_url,
                    oauth_discovery_endpoint=oauth_discovery_endpoint,
                    scopes=scopes,
                    status=401,
                )
            elif resp.status_code == 403:
                return "Access forbidden - token lacks required Microsoft Graph permissions for this site"
            elif resp.status_code == 404:
                return f"Site not found in Microsoft Graph: {site_url}"
            else:
                return f"Microsoft Graph API request failed with status {resp.status_code}"

        except McpAuthorizationRequired:
            raise
        except requests.exceptions.Timeout:
            return "Connection timeout - Microsoft Graph is not responding"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach Microsoft Graph"
        except requests.exceptions.RequestException as exc:
            return f"Request failed: {str(exc)}"
        except Exception as exc:
            log.error(f"Error calling Microsoft Graph API: {exc}")
            return f"Unexpected error: {str(exc)}"

    @staticmethod
    def _call_sharepoint_api(site_url: str, access_token: str) -> str | None:
        """Call ``<site_url>/_api/web`` with *access_token*.

        Used exclusively by the **client-credentials flow**.  ACS tokens obtained
        via the legacy client-credentials grant are SharePoint tokens (not Graph
        tokens) and must be verified against the SharePoint REST endpoint.

        On HTTP 401 the response body is parsed and ``McpAuthorizationRequired``
        is raised so the caller is notified of the invalid token.
        """
        from ..runtime.utils.mcp_oauth import McpAuthorizationRequired

        try:
            resp = requests.get(
                f"{site_url}/_api/web",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return None
            elif resp.status_code == 401:
                api_message = SharepointConfiguration._extract_api_error_message(resp)
                raise McpAuthorizationRequired(
                    message=(
                        f"SharePoint access token is invalid or expired: {api_message}. "
                        "Please re-authorize to obtain a fresh access token."
                    ),
                    server_url=site_url,
                    status=401,
                )
            elif resp.status_code == 403:
                return "Access forbidden - client may lack required permissions for this site"
            elif resp.status_code == 404:
                return f"Site not found or not accessible: {site_url}"
            else:
                return f"SharePoint API request failed with status {resp.status_code}"
        except McpAuthorizationRequired:
            raise
        except requests.exceptions.Timeout:
            return "Connection timeout - SharePoint is not responding"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach SharePoint"
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"

    @staticmethod
    def _check_connection_delegated(settings: dict, oauth_discovery_endpoint: str) -> str | None:
        """Delegated flow.

        Uses the ``access_token`` from *settings* to probe the site via the
        Microsoft Graph API (the correct endpoint for Azure AD delegated tokens).

        Raises ``McpAuthorizationRequired`` when:
        - no ``access_token`` is present (authorization dance not yet started), or
        - the token is invalid / expired (401 from Graph API).

        In both cases the exception carries the same rich metadata shape as a
        real MCP OAuth challenge, including ``resource_metadata``,
        ``www_authenticate``, and ``resource_metadata_url``, so upstream
        handlers need no special-casing for SharePoint.
        """
        site_url, err = SharepointConfiguration._validate_site_url(settings)
        if err:
            return err

        scopes = settings.get("scopes")
        access_token = settings.get("access_token")
        if not access_token:
            raise SharepointConfiguration._build_mcp_authorization_required(
                message=(
                    f"SharePoint site {site_url} requires OAuth authorization. "
                    "Please complete the OAuth flow to obtain an access token."
                ),
                site_url=site_url,
                oauth_discovery_endpoint=oauth_discovery_endpoint,
                scopes=scopes,
            )

        # Use Graph API for health-check — delegated tokens are Graph tokens
        return SharepointConfiguration._call_graph_api(site_url, access_token, oauth_discovery_endpoint, scopes)

    @staticmethod
    def _check_connection_client_credentials(settings: dict) -> str | None:
        """App-auth / client-credentials flow (original behaviour)."""
        # Validate client_id
        client_id = settings.get("client_id")
        if client_id is None or client_id == "":
            return "Client ID cannot be empty" if client_id == "" else "Client ID is required"
        if not isinstance(client_id, str):
            return "Client ID must be a string"
        client_id = client_id.strip()
        if not client_id:
            return "Client ID cannot be empty"

        # Validate client_secret
        client_secret = settings.get("client_secret")
        if client_secret is None:
            return "Client secret is required"
        if hasattr(client_secret, "get_secret_value"):
            client_secret = client_secret.get_secret_value()
        if not client_secret or not client_secret.strip():
            return "Client secret cannot be empty"

        # Validate site_url
        site_url, err = SharepointConfiguration._validate_site_url(settings)
        if err:
            return err

        # Parse tenant from site URL and build ACS token endpoint
        try:
            if ".sharepoint.com" not in site_url:
                return "Site URL must be a valid SharePoint URL (*.sharepoint.com)"
            parts = site_url.split("//")[1].split(".")
            if len(parts) < 3:
                return "Invalid SharePoint URL format"
            tenant = parts[0]
            token_url = f"https://accounts.accesscontrol.windows.net/{tenant}.onmicrosoft.com/tokens/OAuth/2"
        except Exception:
            return "Failed to parse SharePoint URL - ensure it's in format: https://<tenant>.sharepoint.com/sites/<site>"

        try:
            # Step 1: obtain access token via client credentials
            token_response = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": f"{client_id}@{tenant}.onmicrosoft.com",
                    "client_secret": client_secret,
                    "resource": (
                        f"00000003-0000-0ff1-ce00-000000000000"
                        f"/{site_url.split('//')[1].split('/')[0]}"
                        f"@{tenant}.onmicrosoft.com"
                    ),
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

            try:
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    return "No access token received from SharePoint"
            except Exception:
                return "Failed to parse token response"

            # Step 2: verify the token against the SharePoint REST API
            return SharepointConfiguration._call_sharepoint_api(site_url, access_token)

        except requests.exceptions.Timeout:
            return "Connection timeout - SharePoint is not responding"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach SharePoint"
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception as e:
            from ..runtime.utils.mcp_oauth import McpAuthorizationRequired
            if isinstance(e, McpAuthorizationRequired):
                raise
            return f"Unexpected error: {str(e)}"
