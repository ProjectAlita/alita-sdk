from logging import getLogger
from typing import Any, List, Literal, Optional

from alita_sdk.tools.utils import clean_string, TOOLKIT_SPLITTER
from pydantic import BaseModel, create_model, Field, ConfigDict
from langchain_core.tools import BaseToolkit, BaseTool
from alita_sdk.tools.base.tool import BaseAction
from ..tools.vectorstore import VectorStoreWrapper

logger = getLogger(__name__)

class VectorStoreToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in VectorStoreWrapper.model_construct().get_available_tools()}
        return create_model(
            "vectorstore",
            embedding_model=(str, Field(description="Embedding model")),
            embedding_model_params=(dict, Field(description="Embedding model parameters")),
            vectorstore_type=(str, Field(description="Vectorstore type (Chroma, PGVector, Elastic, etc.)")),
            vectorstore_params=(dict, Field(description="Vectorstore connection parameters")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "VectorStore", "icon_url": None, "hidden": True}})
        )

    @classmethod
    def get_toolkit(cls, llm: Any, vectorstore_type: str, embedding_model: str, 
                    embedding_model_params: dict, vectorstore_params: dict,
                    toolkit_name: Optional[str] = None,
                    selected_tools: list[str] = []):
        logger.info("Selected tools: %s", selected_tools)
        prefix = clean_string(toolkit_name) + TOOLKIT_SPLITTER if toolkit_name else ''
        if selected_tools is None:
            selected_tools = []
        tools = []
        vectorstore_wrapper = VectorStoreWrapper(llm=llm,
                                                 vectorstore_type=vectorstore_type,
                                                 embedding_model=embedding_model, 
                                                 embedding_model_params=embedding_model_params, 
                                                 vectorstore_params=vectorstore_params)
        available_tools = vectorstore_wrapper.get_available_tools()
        logger.info("Available tools: %s", available_tools)
        for tool in available_tools:
            # if selected_tools:
            #     if tool["name"] not in selected_tools:
            #         continue
            tools.append(BaseAction(
                api_wrapper=vectorstore_wrapper,
                name=f'{prefix}{tool["name"]}',
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
