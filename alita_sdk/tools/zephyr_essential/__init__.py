from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, Field, SecretStr

from .api_wrapper import ZephyrEssentialApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "zephyr_essential"

def get_tools(tool):
    return ZephyrEssentialToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        token=tool['settings']["token"],
        toolkit_name=tool.get('toolkit_name'),
        llm = tool['settings'].get('llm', None),

        # indexer settings
        connection_string = tool['settings'].get('connection_string', None),
        collection_name=str(tool['toolkit_name']),
        embedding_model = "HuggingFaceEmbeddings",
        embedding_model_params = {"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        vectorstore_type = "PGVector"
    ).get_tools()

class ZephyrEssentialToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in ZephyrEssentialApiWrapper.model_construct().get_available_tools()}
        ZephyrEssentialToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            token=(str, Field(description="Bearer api token")),
            base_url=(Optional[str], Field(description="Zephyr Essential base url", default=None)),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            # indexer settings
            connection_string=(Optional[SecretStr], Field(description="Connection string for vectorstore",
                                                          default=None,
                                                          json_schema_extra={'secret': True})),

            # embedder settings
            embedding_model=(str, Field(description="Embedding model: i.e. 'HuggingFaceEmbeddings', etc.", default="HuggingFaceEmbeddings")),
            embedding_model_params=(dict, Field(description="Embedding model parameters: i.e. `{'model_name': 'sentence-transformers/all-MiniLM-L6-v2'}", default={"model_name": "sentence-transformers/all-MiniLM-L6-v2"})),
            __config__={'json_schema_extra': {'metadata': {"label": "Zephyr Essential", "icon_url": "zephyr.svg",
                            "categories": ["test management"],
                            "extra_categories": ["test automation", "test case management", "test planning"]
                        }}}
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        zephyr_api_wrapper = ZephyrEssentialApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = zephyr_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=zephyr_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
