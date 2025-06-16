from typing import Optional, Type

from pydantic import BaseModel, field_validator, Field

from .api_wrapper import QtestApiWrapper
from ..base.tool import BaseAction


class QtestAction(BaseAction):
    """Tool for interacting with the Qtest API."""

    api_wrapper: QtestApiWrapper = Field(default_factory=QtestApiWrapper)
    name: str
    mode: str = ""
    description: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return v.replace(' ', '')
