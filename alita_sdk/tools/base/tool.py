
from typing import Optional, Type, Any

from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel
from pydantic import Field
from langchain_core.tools import BaseTool, ToolException


class BaseAction(BaseTool):
    """Tool for interacting with the Confluence API."""

    api_wrapper: BaseModel = Field(default_factory=BaseModel)
    name: str = ""
    description: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    def _run(
        self,
        *args: Any,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> ToolException | str:
        """Use the Confluence API to run an operation."""
        try:
            return self.api_wrapper.run(self.name, *args, **kwargs)
        except Exception as e:
            return ToolException(f"An exception occurred: {e}")
