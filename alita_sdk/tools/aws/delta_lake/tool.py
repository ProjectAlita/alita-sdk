
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
            # Strip numeric suffix added for deduplication (_2, _3, etc.)
            # to get the original tool name that exists in the wrapper
            import re
            tool_name = re.sub(r'_\d+$', '', self.name)
            # Use the tool name to dispatch to the correct API wrapper method
            return self.api_wrapper.run(tool_name, *args, **kwargs)
        except Exception as e:
            return f"Error: {format_exc()}"