from pydantic import BaseModel, ConfigDict, Field, SecretStr


class EmbeddingConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Embedding Configuration",
                "icon_url": None,
                "section": "embedding",
                "type": "embedding_model"
            }
        }
    )
    embedding_model: str = Field(description="Embedding model: i.e. 'HuggingFaceEmbeddings', etc.",
                                 default="HuggingFaceEmbeddings")
    embedding_model_params: dict = Field(
        description="Embedding model parameters: i.e. `{'model_name': 'sentence-transformers/all-MiniLM-L6-v2'}",
        default={"model_name": "sentence-transformers/all-MiniLM-L6-v2"})
