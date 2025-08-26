from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AzureSearchConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Azure Search",
                "icon_url": "azure-search.svg",
                "hidden": True,
                "section": "credentials",
                "type": "azure_search",
                "categories": ["other"],
                "extra_categories": ["azure", "cognitive search", "vector database", "knowledge base"],
            }
        }
    )
    endpoint: Optional[str] = Field(description="Azure Search endpoint")
    api_base: Optional[str] = Field(description="Azure Search API base")
    api_key: Optional[SecretStr] = Field(description="API key")
