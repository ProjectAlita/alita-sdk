from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class BigQueryConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Google BigQuery",
                "icon_url": "google.svg",
                "hidden": True,
                "section": "credentials",
                "type": "bigquery",
                "categories": ["other"],
                "extra_categories": ["google", "gcp", "data warehouse", "analytics"],
            }
        }
    )
    api_key: Optional[SecretStr] = Field(description="GCP API key")
    project: Optional[str] = Field(description="BigQuery project ID")
    location: Optional[str] = Field(description="BigQuery location")
    dataset: Optional[str] = Field(description="BigQuery dataset name")
    table: Optional[str] = Field(description="BigQuery table name")
