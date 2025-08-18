from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class FigmaConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Figma",
                "icon_url": "figma-icon.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Token",
                                "fields": ["token"]
                            },
                            {
                                "name": "Oath2",
                                "fields": ["oauth2"]
                            }
                        ]
                    }
                },
                "section": "credentials",
                "type": "figma",
                "categories": ["other"],
                "extra_categories": ["figma", "design", "ui/ux", "prototyping", "collaboration"],
            }
        }
    )
    token: Optional[SecretStr] = Field(description="Figma Token", json_schema_extra={"secret": True}, default=None)
    oauth2: Optional[SecretStr] = Field(description="OAuth2 Token", json_schema_extra={"secret": True}, default=None)
