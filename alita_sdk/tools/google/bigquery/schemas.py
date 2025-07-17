from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import Field, create_model


class ArgsSchema(Enum):
    NoInput = create_model("NoInput")
    GetDocuments = create_model(
        "GetDocuments",
        ids=(
            Optional[List[str]],
            Field(default=None, description="List of document IDs to retrieve."),
        ),
        filter=(
            Optional[Union[Dict[str, Any], str]],
            Field(default=None, description="Filter as dict or SQL WHERE clause."),
        ),
    )
    SimilaritySearch = create_model(
        "SimilaritySearch",
        query=(str, Field(description="Text query to search for similar documents.")),
        k=(int, Field(default=5, description="Number of top results to return.")),
        filter=(
            Optional[Union[Dict[str, Any], str]],
            Field(default=None, description="Filter as dict or SQL WHERE clause."),
        ),
    )
    BatchSearch = create_model(
        "BatchSearch",
        queries=(
            Optional[List[str]],
            Field(default=None, description="List of text queries."),
        ),
        embeddings=(
            Optional[List[List[float]]],
            Field(default=None, description="List of embedding vectors."),
        ),
        k=(int, Field(default=5, description="Number of top results to return.")),
        filter=(
            Optional[Union[Dict[str, Any], str]],
            Field(default=None, description="Filter as dict or SQL WHERE clause."),
        ),
    )
    JobStatsArgs = create_model(
        "JobStatsArgs", job_id=(str, Field(description="BigQuery job ID."))
    )
    SimilaritySearchByVectorArgs = create_model(
        "SimilaritySearchByVectorArgs",
        embedding=(List[float], Field(description="Embedding vector.")),
        k=(int, Field(default=5, description="Number of top results to return.")),
    )
    SimilaritySearchByVectorWithScoreArgs = create_model(
        "SimilaritySearchByVectorWithScoreArgs",
        embedding=(List[float], Field(description="Embedding vector.")),
        filter=(
            Optional[Union[Dict[str, Any], str]],
            Field(default=None, description="Filter as dict or SQL WHERE clause."),
        ),
        k=(int, Field(default=5, description="Number of top results to return.")),
    )
    SimilaritySearchWithScoreArgs = create_model(
        "SimilaritySearchWithScoreArgs",
        query=(str, Field(description="Text query.")),
        filter=(
            Optional[Union[Dict[str, Any], str]],
            Field(default=None, description="Filter as dict or SQL WHERE clause."),
        ),
        k=(int, Field(default=5, description="Number of top results to return.")),
    )
    SimilaritySearchByVectorsArgs = create_model(
        "SimilaritySearchByVectorsArgs",
        embeddings=(List[List[float]], Field(description="List of embedding vectors.")),
        filter=(
            Optional[Union[Dict[str, Any], str]],
            Field(default=None, description="Filter as dict or SQL WHERE clause."),
        ),
        k=(int, Field(default=5, description="Number of top results to return.")),
        with_scores=(bool, Field(default=False)),
        with_embeddings=(bool, Field(default=False)),
    )
    ExecuteArgs = create_model(
        "ExecuteArgs",
        method=(str, Field(description="Name of the BigQuery client method to call.")),
        args=(
            Optional[List[Any]],
            Field(default=None, description="Positional arguments for the method."),
        ),
        kwargs=(
            Optional[Dict[str, Any]],
            Field(default=None, description="Keyword arguments for the method."),
        ),
    )
    CreateDeltaLakeTable = create_model(
        "CreateDeltaLakeTable",
        table_name=(str, Field(description="Name of the Delta Lake table to create in BigQuery.")),
        dataset=(Optional[str], Field(default=None, description="BigQuery dataset to contain the table (defaults to self.dataset).")),
        connection_id=(str, Field(description="Fully qualified connection ID (project.region.connection_id).")),
        source_uris=(list, Field(description="List of GCS URIs (prefixes) for the Delta Lake table.")),
        autodetect=(bool, Field(default=True, description="Whether to autodetect schema (default: True).")),
        project=(Optional[str], Field(default=None, description="GCP project ID (defaults to self.project).")),
    )