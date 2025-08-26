from pydantic import BaseModel, ConfigDict, Field, SecretStr


class TestIOConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "TestIO",
                "icon_url": "testio.svg",
                "section": "credentials",
                "type": "testio",
                "categories": ["testing"],
                "extra_categories": ["testio", "testing", "crowd testing", "qa"],
            }
        }
    )
    endpoint: str = Field(description="TestIO endpoint")
    api_key: SecretStr = Field(description="TestIO API Key")
