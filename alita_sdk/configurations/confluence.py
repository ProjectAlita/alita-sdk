from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ConfluenceConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Confluence",
                "icon_url": "confluence.svg",
                "sections": {
                    "auth": {
                        "required": False,
                        "subsections": [
                            {
                                "name": "API Key",
                                "fields": ["username", "api_key"]
                            },
                            {
                                "name": "Token",
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
    username: Optional[str] = Field(description="Confluence Username", default=None)
    api_key: Optional[SecretStr] = Field(description="Confluence API Key", default=None)
    token: Optional[SecretStr] = Field(description="Confluence Token", default=None)
