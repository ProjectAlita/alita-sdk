from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ZephyrConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Zephyr Scale",
                "icon_url": "zephyr.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Token",
                                "fields": ["token"]
                            },
                            {
                                "name": "Username & Password",
                                "fields": ["username", "password"]
                            },
                            {
                                "name": "Cookies",
                                "fields": ["cookies"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "zephyr",
                "categories": ["test management"],
                "extra_categories": ["zephyr", "test automation", "test case management", "test planning"],
            }
        }
    )
    base_url: str = Field(description="Zephyr base URL")
    token: Optional[SecretStr] = Field(description="API token", default=None)
    username: Optional[str] = Field(description="Username", default=None)
    password: Optional[SecretStr] = Field(description="Password", default=None)
    cookies: Optional[str] = Field(description="Cookies", default=None)
