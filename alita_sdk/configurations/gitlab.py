from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class GitlabConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "GitLab",
                "icon_url": None,
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "GitLab private token",
                                "fields": ["private_token"]
                            }
                        ]
                    }
                },
                "section": "credentials",
                "type": "gitlab",
                "categories": ["code repositories"],
                "extra_categories": ["gitlab", "git", "repository", "code", "version control"],
            }
        }
    )
    url: str = Field(description="GitLab URL")
    private_token: SecretStr = Field(description="GitLab private token")
