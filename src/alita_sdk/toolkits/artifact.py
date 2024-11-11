from typing import List, Any
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel
from pydantic.fields import FieldInfo
from ..tools.artifact import (
    __all__ as artifact_tools
)


class ArtifactToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "artifact",
            client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
            bucket = (str, FieldInfo(description="Bucket name")),
            selected_tools = (list, FieldInfo(description="List of selected tools", default=[list(tool.keys())[0] for tool in artifact_tools]))
        )
    
    @classmethod
    def get_toolkit(cls, client: Any, bucket: str, selected_tools: list[str] = []):
        if selected_tools is None:
            selected_tools = []
        artifact = client.artifact(bucket)
        tools = []
        for tool in artifact_tools:
            if selected_tools:
                if tool['name'] not in selected_tools:
                    continue
            tools.append(tool['tool'](artifact=artifact))
        return cls(tools=tools)
    
    def get_tools(self):
        return self.tools