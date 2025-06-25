from typing import Optional, Type

from pydantic import BaseModel, field_validator, Field

from .api_wrapper import PostmanApiWrapper
from ..base.tool import BaseAction


class PostmanAction(BaseAction):
    """Tool for interacting with the Postman API."""

    api_wrapper: PostmanApiWrapper = Field(default_factory=PostmanApiWrapper)
    name: str
    mode: str = ""
    description: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return v.replace(' ', '')
