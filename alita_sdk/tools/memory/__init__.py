from typing import Optional, List

from langchain_core.tools import BaseToolkit, BaseTool

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

def get_tools(tools_list: list, alita_client, llm, memory_store=None):
    """
    Get memory tools for the provided tool configurations.
    
    Args:
        tools_list: List of tool configurations
        alita_client: Alita client instance
        llm: LLM client instance
        memory_store: Optional memory store instance
    
    Returns:
        List of memory tools
    """
    all_tools = []
    
    for tool in tools_list:
        if tool.get('type') == 'memory' or tool.get('toolkit_name') == 'memory':
            try:
                toolkit_instance = MemoryToolkit().get_toolkit(
                    namespace=tool['settings'].get('namespace', str(tool['id'])),
                    username=tool['settings'].get('username', ''),
                    store=tool['settings'].get('store', memory_store),
                    toolkit_name=tool.get('toolkit_name', '')
                )
                all_tools.extend(toolkit_instance.get_tools())
            except Exception as e:
                print(f"DEBUG: Error in memory toolkit get_tools: {e}")
                print(f"DEBUG: Tool config: {tool}")
                raise
    
    return all_tools

class MemoryToolkit(BaseToolkit):
    tools: List[BaseTool] = []


    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            'MemoryConfig',
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
    def get_toolkit(cls, namespace: str, store=None, **kwargs):
        """
        Get toolkit with memory tools.
        
        Args:
            namespace: Memory namespace
            store: PostgresStore instance (imported dynamically)
            **kwargs: Additional arguments
        """
        try:
            from langgraph.store.postgres import PostgresStore
        except ImportError:
            raise ImportError(
                "PostgreSQL dependencies (psycopg) are required for MemoryToolkit. "
                "Install with: pip install psycopg[binary]"
            )
        
        # Validate store type
        if store is not None and not isinstance(store, PostgresStore):
            raise TypeError(f"Expected PostgresStore, got {type(store)}")
        
        return cls(tools=[
            create_manage_memory_tool(namespace=namespace, store=store),
            create_search_memory_tool(namespace=namespace, store=store)
        ])

    def get_tools(self):
        return self.tools
