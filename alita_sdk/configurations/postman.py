from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class PostmanConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Postman",
                "icon_url": "postman.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "API Key",
                                "fields": ["api_key"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "postman",
                "categories": ["other"],
                "extra_categories": ["postman", "api", "testing", "collection"],
            }
        }
    )
    base_url: str = Field(description="Postman API base URL")
    workspace_id: str = Field(description="Default workspace ID")
    api_key: Optional[SecretStr] = Field(description="Postman API Key", default=None)
