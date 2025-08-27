from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SqlConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "SQL",
                "icon_url": "sql.svg",
                "section": "credentials",
                "type": "sql",
                "categories": ["development"],
                "extra_categories": ["sql", "database", "data", "query"],
            }
        }
    )
    host: str = Field(description="Database host")
    port: int = Field(description="Database port", default=None)
    username: str = Field(description="Database username")
    password: SecretStr = Field(description="Database password", json_schema_extra={'secret': True})
