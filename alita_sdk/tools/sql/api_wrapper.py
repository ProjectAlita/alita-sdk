import logging
from typing import Optional, Any

from pydantic import BaseModel, create_model, model_validator, Field, SecretStr
from pydantic.fields import PrivateAttr
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
    _client: Optional[Engine] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        for field in SQLConfig.model_fields:
            if field not in values or not values[field]:
                raise ValueError(f"{field} is a required field and must be provided.")

        dialect = values['dialect']
        host = values['host']
        username = values['username']
        password = values['password']
        database_name = values['database_name']
        port = values['port']

        if dialect == SQLDialect.POSTGRES:
            connection_string = f'postgresql+psycopg2://{username}:{password}@{host}:{port}/{database_name}'
        elif dialect == SQLDialect.MYSQL:
            connection_string = f'mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}'
        else:
            raise ValueError(f"Unsupported database type. Supported types are: {[e.value for e in SQLDialect]}")

        cls._client = create_engine(connection_string)
        return values

    def execute_sql(self, sql_query: str):
        """Executes the provided SQL query on the configured database."""
        engine = self._client
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

    def list_tables_and_columns(self):
        """Lists all tables and their columns in the configured database."""
        inspector = inspect(self._client)
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