
from enum import Enum
from typing import List, Optional

from pydantic import Field, create_model

class ArgsSchema(Enum):
    NoInput = create_model("NoInput")
    QueryTableArgs = create_model(
        "QueryTableArgs",
        query=(Optional[str], Field(default=None, description="SQL query to execute on Delta Lake table. If None, returns all data.")),
        columns=(Optional[List[str]], Field(default=None, description="List of columns to select.")),
        filters=(Optional[dict], Field(default=None, description="Dict of column:value pairs for pandas-like filtering.")),
    )
    VectorSearchArgs = create_model(
        "VectorSearchArgs",
        embedding=(List[float], Field(description="Embedding vector for similarity search.")),
        k=(int, Field(default=5, description="Number of top results to return.")),
        embedding_column=(Optional[str], Field(default="embedding", description="Name of the column containing embeddings.")),
    )
