from typing import Optional, Type

from pydantic import BaseModel, Field, field_validator

from ..base.tool import BaseAction
from .api_wrapper import OpenApiApiWrapper


class OpenApiAction(BaseAction):
    """Tool for executing a single OpenAPI operation."""

    api_wrapper: OpenApiApiWrapper = Field(default_factory=OpenApiApiWrapper)
    name: str
    description: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v: str) -> str:
        return v.replace(' ', '')
