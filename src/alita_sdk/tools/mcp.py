from logging import getLogger
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel

logger = getLogger(__name__)

class McpTool(BaseTool):
    name: str
    description: str
    # Whether it's already established?
    socket_client: Any
    args_schema: Type[BaseModel] = None
    return_type: str = "str"
    
    def _run(self, *args, **kwargs):
        # socket connection?????
        # send event to socket per contract
        # socket_client.send_event(event=kwargs.get('event'), data=kwargs.get('data'))
        # wait for response
        return f"Calling tool: \n{self.name} \n with kwargs: {kwargs}"
