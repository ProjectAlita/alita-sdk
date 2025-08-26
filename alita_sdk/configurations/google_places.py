from pydantic import BaseModel, ConfigDict, Field, SecretStr


class GooglePlacesConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Google Places",
                "icon_url": "google.svg",
                "section": "credentials",
                "type": "google_places",
                "categories": ["other"],
                "extra_categories": ["google", "places", "maps", "location", "geocoding"],
            }
        }
    )
    api_key: SecretStr = Field(description="Google Places API Key")
