from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ZephyrEssentialConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Zephyr Essential",
                "icon_url": "zephyr.svg",
                "section": "credentials",
                "type": "zephyr_essential",
                "categories": ["test management"],
                "extra_categories": ["zephyr", "test automation", "test case management", "test planning"],
            }
        }
    )
    base_url: str = Field(description="Zephyr Essential Base URL")
    token: SecretStr = Field(description="Zephyr Essential API Token")
