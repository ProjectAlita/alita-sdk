from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class XrayConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Xray Cloud",
                "icon_url": "xray.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Client Credentials",
                                "fields": ["client_id", "client_secret"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "xray",
                "categories": ["test management"],
                "extra_categories": ["xray", "test automation", "test case management", "test planning"],
            }
        }
    )
    base_url: str = Field(description="Xray URL")
    client_id: Optional[str] = Field(description="Client ID")
    client_secret: Optional[SecretStr] = Field(description="Client secret")
