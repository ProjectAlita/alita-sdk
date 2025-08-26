from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AdoConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Ado",
                "icon_url": None,
                "section": "credentials",
                "type": "ado",
                "categories": ["project management"],
            }
        }
    )
    organization_url: str = Field(description="Base API URL")
    project: str = Field(description="ADO project")
    token: Optional[SecretStr] = Field(description="ADO Token")


class AdoReposConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "ADO repos",
                "icon_url": "ado-repos-icon.svg",
                "section": "credentials",
                "type": "ado_repos",
                "categories": ["code repositories"],
            }
        }
    )
    repository_id: str = Field(description="ADO repository ID")

    ado_configuration: AdoConfiguration = Field(
        default_factory=AdoConfiguration,
        description="ADO configuration",
        json_schema_extra={
            'configuration_types': ['ado']
        }
    )
