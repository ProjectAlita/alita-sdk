from typing import Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, field_validator, Field
from langchain_core.tools import BaseTool
from traceback import format_exc
from .api_wrapper import BigQueryApiWrapper


class BigQueryAction(BaseTool):
    """Tool for interacting with the BigQuery API."""

    api_wrapper: BigQueryApiWrapper = Field(default_factory=BigQueryApiWrapper)
    name: str
    mode: str = ""
    description: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return v.replace(' ', '')

    def _run(
        self,
        *args,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs,
    ) -> str:
        """Use the GitHub API to run an operation."""
        try:
            return self.api_wrapper.run(self.mode, *args, **kwargs)
        except Exception as e:
            return f"Error: {format_exc()}"