from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class TestRailConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "TestRail",
                "icon_url": "testrail.svg",
                "section": "credentials",
                "type": "testrail",
                "categories": ["test management"],
                "extra_categories": ["testrail", "test management", "quality assurance", "testing"],
            }
        }
    )
    email: Optional[str] = Field(description="TestRail Email", default=None)
    password: Optional[SecretStr] = Field(description="TestRail Password", default=None)
