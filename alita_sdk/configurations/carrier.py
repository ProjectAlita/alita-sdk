from pydantic import BaseModel, ConfigDict, Field, SecretStr


class CarrierConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Carrier",
                "icon_url": "carrier.svg",
                "section": "credentials",
                "type": "carrier",
                "categories": ["testing"],
                "extra_categories": ["carrier", "security", "testing", "vulnerability"],
            }
        }
    )
    organization: str = Field(description="Carrier Organization")
    url: str = Field(description="Carrier URL")
    private_token: SecretStr = Field(description="Carrier Private Token")
