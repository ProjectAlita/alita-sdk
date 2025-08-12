from pydantic import BaseModel, ConfigDict, Field, SecretStr


class PgVectorConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "PgVector",
                "icon_url": None,
                "section": "vectorstorage",
                "type": "pgvector"
            }
        }
    )
    connection_string: SecretStr = Field(
        description="Connection string for PgVector database",
        default=None
    )
