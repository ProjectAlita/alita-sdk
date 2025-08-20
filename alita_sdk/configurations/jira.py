from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class JiraConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Jira",
                "icon_url": "jira.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Basic",
                                "fields": ["username", "api_key"]
                            },
                            {
                                "name": "Bearer",
                                "fields": ["token"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "jira",
                "categories": ["project management"],
                "extra_categories": ["jira", "issue tracking", "project management", "agile"],
            }
        }
    )
    base_url: str = Field(description="Jira URL")
    username: Optional[str] = Field(description="Jira Username", default=None)
    api_key: Optional[SecretStr] = Field(description="Jira API Key", default=None)
    token: Optional[SecretStr] = Field(description="Jira Token", default=None)
