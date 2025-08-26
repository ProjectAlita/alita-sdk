from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SharepointConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "SharePoint",
                "icon_url": "sharepoint.svg",
                "section": "credentials",
                "type": "sharepoint",
                "categories": ["office"],
                "extra_categories": ["sharepoint", "microsoft", "documents", "collaboration"],
            }
        }
    )
    client_id: str = Field(description="SharePoint Client ID")
    client_secret: SecretStr = Field(description="SharePoint Client Secret")
    site_url: str = Field(description="SharePoint Site URL")
