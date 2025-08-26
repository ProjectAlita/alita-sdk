from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class DeltaLakeConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "AWS Delta Lake",
                "icon_url": "delta-lake.svg",
                "hidden": True,
                "section": "credentials",
                "type": "delta_lake",
                "categories": ["other"],
                "extra_categories": ["aws", "data lake", "analytics", "storage"],
            }
        }
    )
    aws_access_key_id: Optional[SecretStr] = Field(description="AWS access key ID")
    aws_secret_access_key: Optional[SecretStr] = Field(description="AWS secret access key")
    aws_session_token: Optional[SecretStr] = Field(description="AWS session token (optional)")
    aws_region: Optional[str] = Field(description="AWS region for Delta Lake storage")
    s3_path: Optional[str] = Field(description="S3 path to Delta Lake data (e.g., s3://bucket/path)")
    table_path: Optional[str] = Field(description="Delta Lake table path (if not using s3_path)")
