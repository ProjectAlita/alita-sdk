from enum import Enum
from typing import Dict, Any

from pydantic import BaseModel, model_validator


class SQLDialect(str, Enum):
    MYSQL = "mysql"
    POSTGRES = "postgres"


class SQLConfig(BaseModel):
    dialect: str
    host: str
    port: str
    username: str
    password: str
    database_name: str

    @classmethod
    @model_validator(mode='before')
    def validate_config(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        for field in cls.model_fields:
            if field not in values or not values[field]:
                raise ValueError(f"{field} is a required field and must be provided.")
        return values