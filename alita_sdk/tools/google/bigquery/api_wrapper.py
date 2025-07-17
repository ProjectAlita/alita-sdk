import functools
import json
import logging
from typing import Any, Dict, List, Optional, Union

from google.cloud import bigquery
from langchain_core.tools import ToolException
from pydantic import (
    ConfigDict,
    Field,
    PrivateAttr,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_core.core_schema import ValidationInfo

from ...elitea_base import BaseToolApiWrapper
from .schemas import ArgsSchema


def process_output(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
            if isinstance(result, Exception):
                return ToolException(str(result))
            if isinstance(result, (dict, list)):
                return json.dumps(result, default=str)
            return str(result)
        except Exception as e:
            logging.error(f"Error in '{func.__name__}': {str(e)}")
            return ToolException(str(e))

    return wrapper


class BigQueryApiWrapper(BaseToolApiWrapper):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    api_key: Optional[SecretStr] = Field(
        default=None, json_schema_extra={"env_key": "BIGQUERY_API_KEY"}
    )
    project: Optional[str] = Field(
        default=None, json_schema_extra={"env_key": "BIGQUERY_PROJECT"}
    )
    location: Optional[str] = Field(
        default=None, json_schema_extra={"env_key": "BIGQUERY_LOCATION"}
    )
    dataset: Optional[str] = Field(
        default=None, json_schema_extra={"env_key": "BIGQUERY_DATASET"}
    )
    table: Optional[str] = Field(
        default=None, json_schema_extra={"env_key": "BIGQUERY_TABLE"}
    )
    embedding: Optional[Any] = None
    _client: Optional[bigquery.Client] = PrivateAttr(default=None)

    @classmethod
    def model_construct(cls, *args, **kwargs):
        klass = super().model_construct(*args, **kwargs)
        klass._client = None
        return klass

    @field_validator(
        "api_key",
        "project",
        "location",
        "dataset",
        "table",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def set_from_values_or_env(cls, value, info: ValidationInfo):
        if value is None:
            if json_schema_extra := cls.model_fields[info.field_name].json_schema_extra:
                if env_key := json_schema_extra.get("env_key"):
                    try:
                        from langchain_core.utils import get_from_env

                        return get_from_env(
                            key=info.field_name,
                            env_key=env_key,
                            default=cls.model_fields[info.field_name].default,
                        )
                    except Exception:
                        return None
        return value

    @model_validator(mode="after")
    def validate_auth(self) -> "BigQueryApiWrapper":
        if not self.api_key:
            raise ValueError("You must provide a BigQuery API key.")
        return self

    @property
    def bigquery_client(self) -> bigquery.Client:
        if not self._client:
            api_key = self.api_key.get_secret_value() if self.api_key else None
            if not api_key:
                raise ToolException("BigQuery API key is not set.")
            try:
                api_key_dict = json.loads(api_key)
                credentials = bigquery.Client.from_service_account_info(
                    api_key_dict
                )._credentials
                self._client = bigquery.Client(
                    credentials=credentials,
                    project=self.project,
                    location=self.location,
                )
            except Exception as e:
                raise ToolException(f"Error initializing GCP credentials: {str(e)}")
        return self._client

    def _get_table_id(self):
        if not (self.project and self.dataset and self.table):
            raise ToolException("Project, dataset, and table must be specified.")
        return f"{self.project}.{self.dataset}.{self.table}"

    def _create_filters(
        self, filter: Optional[Union[Dict[str, Any], str]] = None
    ) -> str:
        if filter:
            if isinstance(filter, dict):
                filter_expressions = []
                for k, v in filter.items():
                    if isinstance(v, (int, float)):
                        filter_expressions.append(f"{k} = {v}")
                    else:
                        filter_expressions.append(f"{k} = '{v}'")
                return " AND ".join(filter_expressions)
            else:
                return filter
        return "TRUE"

    def job_stats(self, job_id: str) -> Dict:
        return self.bigquery_client.get_job(job_id)._properties.get("statistics", {})

    def create_vector_index(self):
        table_id = self._get_table_id()
        index_name = f"{self.table}_langchain_index"
        sql = f"""
        CREATE VECTOR INDEX IF NOT EXISTS
        `{index_name}`
        ON `{table_id}`
        (embedding)
        OPTIONS(distance_type="EUCLIDEAN", index_type="IVF")
        """
        try:
            self.bigquery_client.query(sql).result()
            return f"Vector index '{index_name}' created or already exists."
        except Exception as ex:
            logging.error(f"Vector index creation failed: {ex}")
            return ToolException(f"Vector index creation failed: {ex}")

    @process_output
    def get_documents(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[Union[Dict[str, Any], str]] = None,
    ):
        table_id = self._get_table_id()
        job_config = None
        id_expr = "TRUE"
        if ids:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", ids)]
            )
            id_expr = "doc_id IN UNNEST(@ids)"
        where_filter_expr = self._create_filters(filter)
        query = f"SELECT * FROM `{table_id}` WHERE {id_expr} AND {where_filter_expr}"
        job = self.bigquery_client.query(query, job_config=job_config)
        return [dict(row) for row in job]

    @process_output
    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Union[Dict[str, Any], str]] = None,
    ):
        """Search for top `k` docs most similar to input query using vector similarity search."""
        if not hasattr(self, "embedding") or self.embedding is None:
            raise ToolException("Embedding model is not set on the wrapper.")
        embedding_vector = self.embedding.embed_query(query)
        # Prepare the vector search query
        table_id = self._get_table_id()
        where_filter_expr = "TRUE"
        if filter:
            if isinstance(filter, dict):
                filter_expressions = [f"{k} = '{v}'" for k, v in filter.items()]
                where_filter_expr = " AND ".join(filter_expressions)
            else:
                where_filter_expr = filter
        # BigQuery vector search SQL (using VECTOR_SEARCH if available)
        sql = f"""
        SELECT *,
            VECTOR_DISTANCE(embedding, @query_embedding) AS score
        FROM `{table_id}`
        WHERE {where_filter_expr}
        ORDER BY score ASC
        LIMIT {k}
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter(
                    "query_embedding", "FLOAT64", embedding_vector
                )
            ]
        )
        job = self.bigquery_client.query(sql, job_config=job_config)
        return [dict(row) for row in job]

    @process_output
    def batch_search(
        self,
        queries: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
        k: int = 5,
        filter: Optional[Union[Dict[str, Any], str]] = None,
    ):
        """Batch vector similarity search. Accepts either queries (to embed) or embeddings."""
        if queries is not None and embeddings is not None:
            raise ToolException("Provide only one of 'queries' or 'embeddings'.")
        if queries is not None:
            if not hasattr(self, "embedding") or self.embedding is None:
                raise ToolException("Embedding model is not set on the wrapper.")
            embeddings = [self.embedding.embed_query(q) for q in queries]
        if not embeddings:
            raise ToolException("No embeddings or queries provided.")
        table_id = self._get_table_id()
        where_filter_expr = "TRUE"
        if filter:
            if isinstance(filter, dict):
                filter_expressions = [f"{k} = '{v}'" for k, v in filter.items()]
                where_filter_expr = " AND ".join(filter_expressions)
            else:
                where_filter_expr = filter
        results = []
        for emb in embeddings:
            sql = f"""
            SELECT *,
                VECTOR_DISTANCE(embedding, @query_embedding) AS score
            FROM `{table_id}`
            WHERE {where_filter_expr}
            ORDER BY score ASC
            LIMIT {k}
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("query_embedding", "FLOAT64", emb)
                ]
            )
            job = self.bigquery_client.query(sql, job_config=job_config)
            results.append([dict(row) for row in job])
        return results

    def similarity_search_by_vector(
        self, embedding: List[float], k: int = 5, **kwargs
    ) -> List[Dict]:
        """Return docs most similar to embedding vector."""
        table_id = self._get_table_id()
        sql = f"""
        SELECT *, VECTOR_DISTANCE(embedding, @query_embedding) AS score
        FROM `{table_id}`
        ORDER BY score ASC
        LIMIT {k}
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("query_embedding", "FLOAT64", embedding)
            ]
        )
        job = self.bigquery_client.query(sql, job_config=job_config)
        return [self._row_to_document(row) for row in job]

    def similarity_search_by_vector_with_score(
        self,
        embedding: List[float],
        filter: Optional[Union[Dict[str, Any], str]] = None,
        k: int = 5,
        **kwargs,
    ) -> List[Dict]:
        """Return docs most similar to embedding vector with scores."""
        table_id = self._get_table_id()
        where_filter_expr = self._create_filters(filter)
        sql = f"""
        SELECT *, VECTOR_DISTANCE(embedding, @query_embedding) AS score
        FROM `{table_id}`
        WHERE {where_filter_expr}
        ORDER BY score ASC
        LIMIT {k}
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("query_embedding", "FLOAT64", embedding)
            ]
        )
        job = self.bigquery_client.query(sql, job_config=job_config)
        return [self._row_to_document(row) for row in job]

    def similarity_search_with_score(
        self,
        query: str,
        filter: Optional[Union[Dict[str, Any], str]] = None,
        k: int = 5,
        **kwargs,
    ) -> List[Dict]:
        """Search for top `k` docs most similar to input query, returns both docs and scores."""
        embedding = self.embedding.embed_query(query)
        return self.similarity_search_by_vector_with_score(
            embedding, filter=filter, k=k, **kwargs
        )

    def similarity_search_by_vectors(
        self,
        embeddings: List[List[float]],
        filter: Optional[Union[Dict[str, Any], str]] = None,
        k: int = 5,
        with_scores: bool = False,
        with_embeddings: bool = False,
        **kwargs,
    ) -> Any:
        """Core similarity search function. Handles a list of embedding vectors, optionally returning scores and embeddings."""
        results = []
        for emb in embeddings:
            docs = self.similarity_search_by_vector_with_score(
                emb, filter=filter, k=k, **kwargs
            )
            if not with_scores and not with_embeddings:
                docs = [d for d in docs]
            elif not with_embeddings:
                docs = [{**d, "score": d.get("score")} for d in docs]
            elif not with_scores:
                docs = [{**d, "embedding": emb} for d in docs]
            results.append(docs)
        return results

    def execute(self, method: str, *args, **kwargs):
        """
        Universal method to call any method from google.cloud.bigquery.Client.
        Args:
            method: Name of the method to call on the BigQuery client.
            *args: Positional arguments for the method.
            **kwargs: Keyword arguments for the method.
        Returns:
            The result of the called method.
        Raises:
            ToolException: If the client is not initialized or method does not exist.
        """
        if not self._client:
            raise ToolException("BigQuery client is not initialized.")
        if not hasattr(self._client, method):
            raise ToolException(f"BigQuery client has no method '{method}'")
        func = getattr(self._client, method)
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            logging.error(f"Error executing '{method}': {e}")
            raise ToolException(f"Error executing '{method}': {e}")

    @process_output
    def create_delta_lake_table(
        self,
        table_name: str,
        dataset: Optional[str] = None,
        connection_id: str = None,
        source_uris: list = None,
        autodetect: bool = True,
        project: Optional[str] = None,
        **kwargs,
    ):
        """
        Create a Delta Lake external table in BigQuery using the google.cloud.bigquery library.
        Args:
            table_name: Name of the Delta Lake table to create in BigQuery.
            dataset: BigQuery dataset to contain the table (defaults to self.dataset).
            connection_id: Fully qualified connection ID (project.region.connection_id).
            source_uris: List of GCS URIs (prefixes) for the Delta Lake table.
            autodetect: Whether to autodetect schema (default: True).
            project: GCP project ID (defaults to self.project).
        Returns:
            API response as dict.
        """
        dataset = dataset or self.dataset
        project = project or self.project
        if not (project and dataset and table_name and connection_id and source_uris):
            raise ToolException("project, dataset, table_name, connection_id, and source_uris are required.")
        client = self.bigquery_client
        table_ref = bigquery.TableReference(
            bigquery.DatasetReference(project, dataset), table_name
        )
        external_config = bigquery.ExternalConfig("DELTA_LAKE")
        external_config.autodetect = autodetect
        external_config.source_uris = source_uris
        external_config.connection_id = connection_id
        table = bigquery.Table(table_ref)
        table.external_data_configuration = external_config
        try:
            created_table = client.create_table(table, exists_ok=True)
            return created_table.to_api_repr()
        except Exception as e:
            raise ToolException(f"Failed to create Delta Lake table: {e}")

    def get_available_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_documents",
                "description": self.get_documents.__doc__,
                "args_schema": ArgsSchema.GetDocuments.value,
                "ref": self.get_documents,
            },
            {
                "name": "similarity_search",
                "description": self.similarity_search.__doc__,
                "args_schema": ArgsSchema.SimilaritySearch.value,
                "ref": self.similarity_search,
            },
            {
                "name": "batch_search",
                "description": self.batch_search.__doc__,
                "args_schema": ArgsSchema.BatchSearch.value,
                "ref": self.batch_search,
            },
            {
                "name": "create_vector_index",
                "description": self.create_vector_index.__doc__,
                "args_schema": ArgsSchema.NoInput.value,
                "ref": self.create_vector_index,
            },
            {
                "name": "job_stats",
                "description": self.job_stats.__doc__,
                "args_schema": ArgsSchema.JobStatsArgs.value,
                "ref": self.job_stats,
            },
            {
                "name": "similarity_search_by_vector",
                "description": self.similarity_search_by_vector.__doc__,
                "args_schema": ArgsSchema.SimilaritySearchByVectorArgs.value,
                "ref": self.similarity_search_by_vector,
            },
            {
                "name": "similarity_search_by_vector_with_score",
                "description": self.similarity_search_by_vector_with_score.__doc__,
                "args_schema": ArgsSchema.SimilaritySearchByVectorWithScoreArgs.value,
                "ref": self.similarity_search_by_vector_with_score,
            },
            {
                "name": "similarity_search_with_score",
                "description": self.similarity_search_with_score.__doc__,
                "args_schema": ArgsSchema.SimilaritySearchWithScoreArgs.value,
                "ref": self.similarity_search_with_score,
            },
            {
                "name": "similarity_search_by_vectors",
                "description": self.similarity_search_by_vectors.__doc__,
                "args_schema": ArgsSchema.SimilaritySearchByVectorsArgs.value,
                "ref": self.similarity_search_by_vectors,
            },
            {
                "name": "execute",
                "description": self.execute.__doc__,
                "args_schema": ArgsSchema.ExecuteArgs.value,
                "ref": self.execute,
            },
            {
                "name": "create_delta_lake_table",
                "description": self.create_delta_lake_table.__doc__,
                "args_schema": ArgsSchema.CreateDeltaLakeTable.value,
                "ref": self.create_delta_lake_table,
            },
        ]

    def run(self, name: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == name:
                # Handle potential dictionary input for args when only one dict is passed
                if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                    kwargs = args[0]
                    args = ()  # Clear args
                try:
                    return tool["ref"](*args, **kwargs)
                except TypeError as e:
                    # Attempt to call with kwargs only if args fail and kwargs exist
                    if kwargs and not args:
                        try:
                            return tool["ref"](**kwargs)
                        except TypeError:
                            raise ValueError(
                                f"Argument mismatch for tool '{name}'. Error: {e}"
                            ) from e
                    else:
                        raise ValueError(
                            f"Argument mismatch for tool '{name}'. Error: {e}"
                        ) from e
        else:
            raise ValueError(f"Unknown tool name: {name}")