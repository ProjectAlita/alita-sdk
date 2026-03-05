
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

    def invoke(self, input, config=None, **kwargs):
        """Inject BaseTool.metadata into the LangGraph run config before invocation.

        LangChain's BaseTool.run() only passes {"name": ..., "description": ...} to
        on_tool_start callbacks — it never forwards BaseTool.metadata.  By merging
        self.metadata into config["metadata"] here, fields injected by
        _inject_display_metadata (display_name, toolkit_type, toolkit_name) reach
        AlitaCallback.on_tool_start via kwargs["metadata"] and appear in the
        Socket.IO chip event.
        """
        if self.metadata:
            if config is None:
                config = {}
            if 'metadata' not in config:
                config['metadata'] = {}
            for key, value in self.metadata.items():
                if key not in config['metadata']:
                    config['metadata'][key] = value
        return super().invoke(input, config=config, **kwargs)

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
