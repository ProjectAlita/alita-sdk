import logging
from typing import Optional

from langchain_core.tools import ToolException
from pydantic import create_model, SecretStr, model_validator
from pydantic.fields import PrivateAttr, Field
from sqlalchemy import create_engine, text, inspect, Engine
from sqlalchemy.orm import sessionmaker

from .models import SQLConfig, SQLDialect
from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

ExecuteSQLModel = create_model(
    "ExecuteSQLModel",
    sql_query=(str, Field(description="The SQL query to execute."))
)

SQLNoInput = create_model(
    "ListTablesAndColumnsModel"
)

class SQLApiWrapper(BaseToolApiWrapper):
    dialect: str
    host: str
    port: str
    username: str
    password: SecretStr
    database_name: str
    _client: Optional[Engine] = PrivateAttr(default=None)

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        for field in SQLConfig.model_fields:
            if field not in values or not values[field]:
                raise ValueError(f"{field} is a required field and must be provided.")
        return values

    def _mask_password_in_error(self, error_message: str) -> str:
        """Mask password in error messages, showing only last 4 characters."""
        password_str = self.password.get_secret_value()
        if len(password_str) <= 4:
            masked_password = "****"
        else:
            masked_password = "****" + password_str[-4:]

        # Replace all occurrences of the password, and any substring of the password that may appear in the error message
        for part in [password_str, password_str.replace('@', ''), password_str.split('@')[-1]]:
            if part and part in error_message:
                error_message = error_message.replace(part, masked_password)
        return error_message

    @property
    def client(self) -> Engine:
        """Lazy property to create and return database engine with error handling."""
        if self._client is None:
            try:
                dialect = self.dialect
                host = self.host
                username = self.username
                password = self.password.get_secret_value()
                database_name = self.database_name
                port = self.port

                if dialect == SQLDialect.POSTGRES:
                    connection_string = f'postgresql+psycopg2://{username}:{password}@{host}:{port}/{database_name}'
                elif dialect == SQLDialect.MYSQL:
                    connection_string = f'mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}'
                else:
                    raise ValueError(f"Unsupported database type. Supported types are: {[e.value for e in SQLDialect]}")

                self._client = create_engine(connection_string)

                # Test the connection
                with self._client.connect() as conn:
                    conn.execute(text("SELECT 1"))

            except Exception as e:
                error_message = str(e)
                masked_error = self._mask_password_in_error(error_message)
                logger.error(f"Database connection failed: {masked_error}")
                raise ValueError(f"Database connection failed: {masked_error}")

        return self._client

    def _handle_database_errors(func):
        """Decorator to catch exceptions and mask passwords in error messages."""

        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                error_message = str(e)
                masked_error = self._mask_password_in_error(error_message)
                logger.error(f"Database operation failed in {func.__name__}: {masked_error}")
                raise ToolException(masked_error)

        return wrapper

    @_handle_database_errors
    def execute_sql(self, sql_query: str):
        """Executes the provided SQL query on the configured database."""
        engine = self.client
        maker_session = sessionmaker(bind=engine)
        session = maker_session()
        try:
            result = session.execute(text(sql_query))
            session.commit()

            if result.returns_rows:
                columns = result.keys()
                data = [dict(zip(columns, row)) for row in result.fetchall()]
                return data
            else:
                return f"Query {sql_query} executed successfully"

        except Exception as e:
            session.rollback()
            raise e

        finally:
            session.close()

    @_handle_database_errors
    def list_tables_and_columns(self):
        """Lists all tables and their columns in the configured database."""
        inspector = inspect(self.client)
        data = {}
        tables = inspector.get_table_names()
        for table in tables:
            columns = inspector.get_columns(table)
            columns_list = []
            for column in columns:
                columns_list.append({
                    'name': column['name'],
                    'type': column['type']
                })
            data[table] = {
                'table_name': table,
                'table_columns': columns_list
            }
        return data

    def get_available_tools(self):
        return [
            {
                "name": "execute_sql",
                "ref": self.execute_sql,
                "description": self.execute_sql.__doc__,
                "args_schema": ExecuteSQLModel,
            },
            {
                "name": "list_tables_and_columns",
                "ref": self.list_tables_and_columns,
                "description": self.list_tables_and_columns.__doc__,
                "args_schema": SQLNoInput,
            }
        ]
