from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ServiceNowConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "ServiceNow",
                "icon_url": "servicenow.svg",
                "section": "credentials",
                "type": "service_now",
                "categories": ["other"],
                "extra_categories": ["servicenow", "itsm", "service management", "incident"],
            }
        }
    )
    base_url: str = Field(description="ServiceNow URL")
    username: Optional[str] = Field(description="ServiceNow Username", default=None)
    password: Optional[SecretStr] = Field(description="ServiceNow Password", default=None)
