
from typing import Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, field_validator, Field
from langchain_core.tools import BaseTool
from traceback import format_exc
from .api_wrapper import DeltaLakeApiWrapper


class DeltaLakeAction(BaseTool):
    """Tool for interacting with the Delta Lake API on AWS."""

    api_wrapper: DeltaLakeApiWrapper = Field(default_factory=DeltaLakeApiWrapper)
    name: str
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
        """Use the Delta Lake API to run an operation."""
        try:
            # Use the tool name to dispatch to the correct API wrapper method
            return self.api_wrapper.run(self.name, *args, **kwargs)
        except Exception as e:
            return f"Error: {format_exc()}"