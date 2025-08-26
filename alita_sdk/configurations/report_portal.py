from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ReportPortalConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Report Portal",
                "icon_url": "report_portal.svg",
                "section": "credentials",
                "type": "report_portal",
                "categories": ["testing"],
                "extra_categories": ["report portal", "testing", "automation", "reports"],
            }
        }
    )
    project: str = Field(description="Report Portal Project Name")
    endpoint: str = Field(description="Report Portal Endpoint URL")
    api_key: SecretStr = Field(description="Report Portal API Key")
