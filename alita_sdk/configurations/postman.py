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
                        "required": False,
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
                "categories": ["api testing"],
                "extra_categories": ["postman", "api", "testing", "collection"],
            }
        }
    )
    api_key: Optional[SecretStr] = Field(description="Postman API Key", default=None)
