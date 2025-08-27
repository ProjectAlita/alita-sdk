from pydantic import BaseModel, ConfigDict, Field, SecretStr


class QtestConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "QTest",
                "icon_url": "qtest.svg",
                "categories": ["test management"],
                "section": "credentials",
                "type": "qtest",
                "extra_categories": ["quality assurance", "test case management", "test planning"]
            }
        }
    )
    base_url: str = Field(description="QTest base url")
    qtest_api_token: SecretStr = Field(description="QTest API token")

