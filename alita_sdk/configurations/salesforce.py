from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SalesforceConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Salesforce",
                "icon_url": "salesforce.svg",
                "section": "credentials",
                "type": "salesforce",
                "categories": ["other"],
                "extra_categories": ["salesforce", "crm", "sales", "customer"],
            }
        }
    )
    client_id: str = Field(description="Salesforce Client ID")
    client_secret: SecretStr = Field(description="Salesforce Client Secret")
    base_url: str = Field(description="Salesforce Base URL")
