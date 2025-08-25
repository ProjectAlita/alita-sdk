from typing import List, Any, Literal, Optional

from alita_sdk.tools.utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo
from ..tools.artifact import ArtifactWrapper
from alita_sdk.tools.base.tool import BaseAction
from ...configurations.pgvector import PgVectorConfiguration


class ArtifactToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ArtifactWrapper.model_construct().get_available_tools()}
        ArtifactToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            "artifact",
            # client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
            bucket = (str, FieldInfo(description="Bucket name", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': ArtifactToolkit.toolkit_max_length})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            # indexer settings
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(default=None, description="PgVector Configuration", json_schema_extra={'configuration_types': ['pgvector']})),

            # embedding model settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.",
                                                  json_schema_extra={'configuration_model': 'embedding'})),

            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Artifact", "icon_url": None}})
        )
    
    @classmethod
    def get_toolkit(cls, client: Any, bucket: str, toolkit_name: Optional[str] = None, selected_tools: list[str] = [], **kwargs):
        if selected_tools is None:
            selected_tools = []
        tools = []
        wrapper_payload = {
            **kwargs,
            **(kwargs.get('pgvector_configuration') or {}),
        }
        artifact_wrapper = ArtifactWrapper(alita=client, bucket=bucket, **wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = artifact_wrapper.get_available_tools()
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=artifact_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)
    
    def get_tools(self):
        return self.tools