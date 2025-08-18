from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class RallyConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Rally",
                "icon_url": "rally.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Password",
                                "fields": ["username", "password"]
                            },
                            {
                                "name": "API Key",
                                "fields": ["api_key"]
                            }
                        ]
                    }
                },
                "section": "credentials",
                "type": "rally",
                "categories": ["project management"],
                "extra_categories": ["agile management", "test management", "scrum", "kanban"]
            }
        }
    )

    server: str = Field(description="Rally server url")
    api_key: Optional[SecretStr] = Field(default=None, description="User's API key", json_schema_extra={'secret': True})
    username: Optional[str] = Field(default=None, description="Username")
    password: Optional[SecretStr] = Field(default=None, description="User's password",
                                          json_schema_extra={'secret': True})
