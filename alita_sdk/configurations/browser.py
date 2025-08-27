from pydantic import BaseModel, ConfigDict, Field, SecretStr


class BrowserConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Browser",
                "icon_url": "browser.svg",
                "section": "credentials",
                "type": "browser",
                "categories": ["testing"],
                "extra_categories": ["browser", "google", "search", "web"],
            }
        }
    )
    google_cse_id: str = Field(description="Google CSE id", default=None)
    google_api_key: SecretStr = Field(description="Google API key", json_schema_extra={'secret': True})
