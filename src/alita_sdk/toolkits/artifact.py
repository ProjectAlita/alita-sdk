from typing import List, Any
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool

from ..tools.artifact import (
    __all__ as artifact_tools
)


class ArtifactToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @classmethod
    def get_toolkit(cls, client: Any, bucket: str, selected_tools: list[str] = []):
        if selected_tools is None:
            selected_tools = []
        artifact = client.client.artifact(bucket)
        tools = []
        for tool in artifact_tools:
            if selected_tools:
                if tool['name'] not in selected_tools:
                    continue
            tools.append(tool['tool'](artifact=artifact))
        return cls(tools=tools)
    
    def get_tools(self):
        return self.tools