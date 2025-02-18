from typing import List, Any, Literal
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo
from ..tools.artifact import ArtifactWrapper
from alita_tools.base.tool import BaseAction


class ArtifactToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ArtifactWrapper.model_construct().get_available_tools()}
        return create_model(
            "artifact",
            # client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
            bucket = (str, FieldInfo(description="Bucket name")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Artifact", "icon_url": None}})
        )
    
    @classmethod
    def get_toolkit(cls, client: Any, bucket: str, selected_tools: list[str] = []):
        if selected_tools is None:
            selected_tools = []
        tools = []
        artifact_wrapper = ArtifactWrapper(client=client, bucket=bucket)
        available_tools = artifact_wrapper.get_available_tools()
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=artifact_wrapper,
                name=tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)
    
    def get_tools(self):
        return self.tools