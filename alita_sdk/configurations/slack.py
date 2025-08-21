from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SlackConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Slack",
                "icon_url": "slack.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Slack Token",
                                "fields": ["slack_token"]
                            }
                        ]
                    },
                },
                "section": "credentials",
                "type": "slack",
                "categories": ["communication"],
                "extra_categories": ["slack", "chat", "messaging", "collaboration"],
            }
        }
    )
    name: Optional[str] = Field(description="Slack name")
    slack_token: Optional[SecretStr] = Field(description="Slack Token like XOXB-*****-*****-*****-*****")
    channel_id:Optional[str] = Field(description="Channel ID")
