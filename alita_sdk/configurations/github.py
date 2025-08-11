from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class GithubConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "GitHub",
                "icon_url": None,
                "sections": {
                    "auth": {
                        "required": False,
                        "subsections": [
                            {
                                "name": "Token",
                                "fields": ["access_token"]
                            },
                            {
                                "name": "Password",
                                "fields": ["username", "password"]
                            },
                            {
                                "name": "App private key",
                                "fields": ["app_id", "app_private_key"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "github",
                "categories": ["code repositories"],
                "extra_categories": ["github", "git", "repository", "code", "version control"],
            }
        }
    )
    base_url: Optional[str] = Field(description="Base API URL", default="https://api.github.com")
    app_id: Optional[str] = Field(description="Github APP ID", default=None)
    app_private_key: Optional[SecretStr] = Field(description="Github APP private key", default=None)

    access_token: Optional[SecretStr] = Field(description="Github Access Token", default=None)

    username: Optional[str] = Field(description="Github Username", default=None)
    password: Optional[SecretStr] = Field(description="Github Password", default=None)
