from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SonarConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Sonar",
                "icon_url": "sonar-icon.svg",
                "section": "credentials",
                "type": "sonar",
                "categories": ["development"],
                "extra_categories": ["code quality", "code security", "code coverage", "quality", "sonarqube"],
            }
        }
    )
    url: str = Field(description="SonarQube Server URL")
    sonar_token: SecretStr = Field(description="SonarQube user token for authentication")
