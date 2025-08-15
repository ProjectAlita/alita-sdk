from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class BitbucketConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Bitbucket",
                "icon_url": "bitbucket-icon.svg",
                "sections": {
                    "auth": {
                        "required": False,
                        "subsections": [
                            {
                                "name": "Username & Password",
                                "fields": ["username", "password"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "bitbucket",
                "categories": ["code repositories"],
                "extra_categories": ["bitbucket", "git", "repository", "code", "version control"],
            }
        }
    )
    url: str = Field(description="Bitbucket URL")
    username: Optional[str] = Field(description="Bitbucket Username", default=None)
    password: Optional[SecretStr] = Field(description="Bitbucket Password/App Password", default=None)
