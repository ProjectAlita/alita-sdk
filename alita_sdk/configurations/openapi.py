from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class OpenApiConfiguration(BaseModel):
    model_config = ConfigDict(
        extra='allow',
        json_schema_extra={
            "metadata": {
                "label": "OpenAPI",
                "icon_url": "openapi.svg",
                "categories": ["integrations"],
                "type": "openapi",
                "extra_categories": ["api", "openapi", "swagger"],
                "sections": {
                    "auth": {
                        "required": False,
                        "subsections": [
                            {
                                "name": "API Key",
                                "fields": ["api_key", "auth_type", "custom_header_name"],
                            },
                            {
                                "name": "OAuth",
                                "fields": [
                                    "client_id",
                                    "client_secret",
                                    "auth_url",
                                    "token_url",
                                    "scope",
                                    "method",
                                ],
                            },
                        ],
                    },
                },
                "section": "credentials",
            }
        }
    )

    api_key: Optional[SecretStr] = Field(
        default=None,
        description=(
            "API key value (stored as a secret). Used when selecting 'API Key' authentication subsection."
        ),
    )
    auth_type: Optional[Literal['Basic', 'Bearer', 'custom']] = Field(
        default='Bearer',
        description=(
            "How to apply the API key. "
            "- 'Bearer': sets 'Authorization: Bearer <api_key>' "
            "- 'Basic': sets 'Authorization: Basic <api_key>' "
            "- 'custom': sets '<custom_header_name>: <api_key>'"
        ),
    )
    custom_header_name: Optional[str] = Field(
        default=None,
        description="Custom header name to use when auth_type='custom' (e.g. 'X-Api-Key').",
    )

    client_id: Optional[str] = Field(default=None, description='OAuth client ID')
    client_secret: Optional[SecretStr] = Field(default=None, description='OAuth client secret (stored as a secret)')
    auth_url: Optional[str] = Field(default=None, description='OAuth authorization URL')
    token_url: Optional[str] = Field(default=None, description='OAuth token URL')
    scope: Optional[str] = Field(default=None, description='OAuth scope(s)')
    method: Optional[Literal['default', 'Basic']] = Field(
        default='default',
        description=(
            "Token exchange method. 'default' uses standard POST body; 'Basic' uses a Basic authorization header."
        ),
    )

    @model_validator(mode='before')
    @classmethod
    def _validate_auth_consistency(cls, values):
        if not isinstance(values, dict):
            return values

        # OAuth: if any OAuth field is provided, require the key ones.
        has_any_oauth = any(
            (values.get('client_id'), values.get('client_secret'), values.get('auth_url'), values.get('token_url'))
        )
        if has_any_oauth:
            missing = []
            if not values.get('client_id'):
                missing.append('client_id')
            if not values.get('client_secret'):
                missing.append('client_secret')
            if not values.get('token_url'):
                missing.append('token_url')
            if missing:
                raise ValueError(f"OAuth is misconfigured; missing: {', '.join(missing)}")

        # API key: if auth_type is custom, custom_header_name must be present.
        auth_type = values.get('auth_type')
        if isinstance(auth_type, str) and auth_type.strip().lower() == 'custom' and values.get('api_key'):
            if not values.get('custom_header_name'):
                raise ValueError("custom_header_name is required when auth_type='custom'")

        return values

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """Best-effort validation for OpenAPI credentials.

        This model is intended to store reusable credentials only.
        Spec/base_url validation happens at toolkit configuration level.
        """
        return None
