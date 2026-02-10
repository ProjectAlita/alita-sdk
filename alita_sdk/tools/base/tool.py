
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
        # Strip None values — LLM sends explicit nulls for optional params
        # (Pydantic schemas show "default": null), which can cause failures
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        # Strip numeric suffix added for deduplication (_2, _3, etc.)
        # to get the original tool name that exists in the wrapper
        import re
        tool_name = re.sub(r'_\d+$', '', self.name)
        return self.api_wrapper.run(tool_name, *args, **kwargs)
