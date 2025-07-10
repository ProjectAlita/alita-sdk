from typing import Optional, List

from langchain_core.tools import BaseToolkit, BaseTool
from langgraph.store.postgres import PostgresStore
try:
    from langmem import create_manage_memory_tool, create_search_memory_tool
except ImportError:
    # langmem is optional; define stubs to avoid import errors
    def create_manage_memory_tool(*args, **kwargs):  # pragma: no cover
        raise ImportError("langmem is required for MemoryToolkit")

    def create_search_memory_tool(*args, **kwargs):  # pragma: no cover
        raise ImportError("langmem is required for MemoryToolkit")
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

name = "memory"

def get_tools(tool):
    return MemoryToolkit().get_toolkit(
        namespace=tool['settings'].get('namespace', str(tool['id'])),
        username=tool['settings'].get('username', ''),
        store=tool['settings'].get('store', None),
        toolkit_name=tool.get('toolkit_name', '')
).get_tools()

class MemoryToolkit(BaseToolkit):
    tools: List[BaseTool] = []


    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            name,
            namespace=(str, Field(description="Memory namespace", json_schema_extra={'toolkit_name': True})),
            username=(Optional[str], Field(description="Username", default='Tester', json_schema_extra={'hidden': True})),
            connection_string=(Optional[SecretStr], Field(description="Connection string for vectorstore",
                                                          default=None,
                                                          json_schema_extra={'secret': True})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Memory",
                    "icon_url": "memory.svg",
                    "hidden": True,
                    "categories": ["other"],
                    "extra_categories": ["long-term memory", "langmem"],
                }
            })
        )

    @classmethod
    def get_toolkit(cls, namespace: str, store: PostgresStore, **kwargs):
        return cls(tools=[
            create_manage_memory_tool(namespace=namespace, store=store),
            create_search_memory_tool(namespace=namespace, store=store)
        ])

    def get_tools(self):
        return self.tools
