from typing import Any, Type
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel
from pydantic.fields import FieldInfo

echo_tool = create_model("input", text = (str, FieldInfo(description="message to echo")))

class EchoTool(BaseTool):
    name: str = "echo"
    description: str = "NEVER USE: echo_tool, as it is only to correct format of output."
    args_schema: Type[BaseModel] = echo_tool
    
    def _run(self, text):
        return text
    
