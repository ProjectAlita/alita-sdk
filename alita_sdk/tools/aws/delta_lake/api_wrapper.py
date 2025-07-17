import functools
import json
import logging
from typing import Any, List, Optional

from deltalake import DeltaTable
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


class DeltaLakeApiWrapper(BaseToolApiWrapper):
    """
    API Wrapper for AWS Delta Lake. Handles authentication, querying, and utility methods.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    aws_access_key_id: Optional[SecretStr] = Field(default=None, json_schema_extra={"env_key": "AWS_ACCESS_KEY_ID"})
    aws_secret_access_key: Optional[SecretStr] = Field(default=None, json_schema_extra={"env_key": "AWS_SECRET_ACCESS_KEY"})
    aws_session_token: Optional[SecretStr] = Field(default=None, json_schema_extra={"env_key": "AWS_SESSION_TOKEN"})
    aws_region: Optional[str] = Field(default=None, json_schema_extra={"env_key": "AWS_REGION"})
    s3_path: Optional[str] = Field(default=None, json_schema_extra={"env_key": "DELTA_LAKE_S3_PATH"})
    table_path: Optional[str] = Field(default=None, json_schema_extra={"env_key": "DELTA_LAKE_TABLE_PATH"})
    _delta_table: Optional[DeltaTable] = PrivateAttr(default=None)

    @classmethod
    def model_construct(cls, *args, **kwargs):
        klass = super().model_construct(*args, **kwargs)
        klass._delta_table = None
        return klass

    @field_validator(
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "aws_region",
        "s3_path",
        "table_path",
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
    def validate_auth(self) -> "DeltaLakeApiWrapper":
        if not (self.aws_access_key_id and self.aws_secret_access_key and self.aws_region):
            raise ValueError("You must provide AWS credentials and region.")
        if not (self.s3_path or self.table_path):
            raise ValueError("You must provide either s3_path or table_path.")
        return self

    @property
    def delta_table(self) -> DeltaTable:
        if not self._delta_table:
            path = self.table_path or self.s3_path
            if not path:
                raise ToolException("Delta Lake table path (table_path or s3_path) must be specified.")
            try:
                storage_options = {
                    "AWS_ACCESS_KEY_ID": self.aws_access_key_id.get_secret_value() if self.aws_access_key_id else None,
                    "AWS_SECRET_ACCESS_KEY": self.aws_secret_access_key.get_secret_value() if self.aws_secret_access_key else None,
                    "AWS_REGION": self.aws_region,
                }
                if self.aws_session_token:
                    storage_options["AWS_SESSION_TOKEN"] = self.aws_session_token.get_secret_value()
                storage_options = {k: v for k, v in storage_options.items() if v is not None}
                self._delta_table = DeltaTable(path, storage_options=storage_options)
            except Exception as e:
                raise ToolException(f"Error initializing DeltaTable: {e}")
        return self._delta_table

    @process_output
    def query_table(self, query: Optional[str] = None, columns: Optional[List[str]] = None, filters: Optional[dict] = None) -> List[dict]:
        """
        Query Delta Lake table. Supports pandas-like filtering, column selection, and SQL-like queries (via pandas.DataFrame.query).
        Args:
            query: SQL-like query string (pandas.DataFrame.query syntax)
            columns: List of columns to select
            filters: Dict of column:value pairs for pandas-like filtering
        Returns:
            List of dicts representing rows
        """
        dt = self.delta_table
        df = dt.to_pandas()
        if filters:
            for col, val in filters.items():
                df = df[df[col] == val]
        if query:
            try:
                df = df.query(query)
            except Exception as e:
                raise ToolException(f"Error in query param: {e}")
        if columns:
            df = df[columns]
        return df.to_dict(orient="records")

    @process_output
    def vector_search(self, embedding: List[float], k: int = 5, embedding_column: str = "embedding") -> List[dict]:
        """
        Perform a vector similarity search on the Delta Lake table.
        Args:
            embedding: Query embedding vector.
            k: Number of top results to return.
            embedding_column: Name of the column containing embeddings.
        Returns:
            List of dicts for top k most similar rows.
        """
        import numpy as np

        dt = self.delta_table
        df = dt.to_pandas()
        if embedding_column not in df.columns:
            raise ToolException(f"Embedding column '{embedding_column}' not found in table.")

        # Filter out rows with missing embeddings
        df = df[df[embedding_column].notnull()]
        if df.empty:
            return []
        # Convert embeddings to numpy arrays
        emb_matrix = np.array(df[embedding_column].tolist())
        query_vec = np.array(embedding)

        # Normalize for cosine similarity
        emb_matrix_norm = emb_matrix / np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        query_vec_norm = query_vec / np.linalg.norm(query_vec)
        similarities = np.dot(emb_matrix_norm, query_vec_norm)

        # Get top k indices
        top_k_idx = np.argsort(similarities)[-k:][::-1]
        top_rows = df.iloc[top_k_idx]
        return top_rows.to_dict(orient="records")

    @process_output
    def get_table_schema(self) -> str:
        dt = self.delta_table
        return dt.schema().to_pyarrow().to_string()

    def get_available_tools(self) -> List[dict]:
        return [
            {
                "name": "query_table",
                "description": self.query_table.__doc__,
                "args_schema": ArgsSchema.QueryTableArgs.value,
                "ref": self.query_table,
            },
            {
                "name": "vector_search",
                "description": self.vector_search.__doc__,
                "args_schema": ArgsSchema.VectorSearchArgs.value,
                "ref": self.vector_search,
            },
            {
                "name": "get_table_schema",
                "description": self.get_table_schema.__doc__,
                "args_schema": ArgsSchema.NoInput.value,
                "ref": self.get_table_schema,
            },
        ]

    def run(self, name: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == name:
                if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                    kwargs = args[0]
                    args = ()
                try:
                    return tool["ref"](*args, **kwargs)
                except TypeError as e:
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