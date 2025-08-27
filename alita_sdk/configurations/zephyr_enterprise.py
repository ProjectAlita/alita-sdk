from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ZephyrEnterpriseConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Zephyr Enterprise",
                "icon_url": "zephyr.svg",
                "section": "credentials",
                "type": "zephyr_enterprise",
                "categories": ["test management"],
                "extra_categories": ["zephyr", "test automation", "test case management", "test planning"],
            }
        }
    )
    base_url: str = Field(description="Zephyr base URL")
    token: Optional[SecretStr] = Field(description="API token")
