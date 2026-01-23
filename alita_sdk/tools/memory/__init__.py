from typing import List, Literal, Optional, Any, Dict
import json
import logging

from langchain_core.tools import BaseToolkit, BaseTool, ToolException, tool
from langchain_core.runnables import RunnableConfig
from pydantic import create_model, BaseModel, ConfigDict, Field

from alita_sdk.configurations.pgvector import PgVectorConfiguration

logger = logging.getLogger(__name__)

name = "memory"


class ManageMemoryInput(BaseModel):
    """Input for managing memory."""
    content: str = Field(description="The content/information to store in memory")
    key: Optional[str] = Field(default=None, description="Optional unique key for the memory. If not provided, one will be generated.")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata to attach to the memory")


class SearchMemoryInput(BaseModel):
    """Input for searching memory."""
    query: str = Field(description="Natural language query to search memories")
    limit: int = Field(default=5, description="Maximum number of results to return")


class GetMemoryInput(BaseModel):
    """Input for getting a specific memory."""
    key: str = Field(description="The key of the memory to retrieve")


class DeleteMemoryInput(BaseModel):
    """Input for deleting a memory."""
    key: str = Field(description="The key of the memory to delete")


def create_memory_tools(namespace: str, store) -> List[BaseTool]:
    """
    Create memory management tools using LangGraph's native store.

    Args:
        namespace: Memory namespace for organizing memories
        store: LangGraph BaseStore instance (PostgresStore or InMemoryStore)

    Returns:
        List of memory tools
    """
    from uuid import uuid4

    @tool("manage_memory", args_schema=ManageMemoryInput)
    def manage_memory(content: str, key: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store information in long-term memory. Use this to remember important facts,
        user preferences, or any information that should persist across conversations.
        """
        try:
            memory_key = key or str(uuid4())
            value = {"content": content}
            if metadata:
                value["metadata"] = metadata

            store.put((namespace,), memory_key, value)
            return f"Successfully stored memory with key: {memory_key}"
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            raise ToolException(f"Failed to store memory: {str(e)}")

    @tool("search_memory", args_schema=SearchMemoryInput)
    def search_memory(query: str, limit: int = 5) -> str:
        """
        Search through stored memories using natural language. Returns memories
        that are semantically similar to the query.
        """
        try:
            results = store.search((namespace,), query=query, limit=limit)
            if not results:
                return "No memories found matching your query."

            memories = []
            for item in results:
                memory_data = {
                    "key": item.key,
                    "content": item.value.get("content", str(item.value)),
                }
                if item.value.get("metadata"):
                    memory_data["metadata"] = item.value["metadata"]
                memories.append(memory_data)

            return json.dumps(memories, indent=2)
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            raise ToolException(f"Failed to search memory: {str(e)}")

    @tool("get_memory", args_schema=GetMemoryInput)
    def get_memory(key: str) -> str:
        """
        Retrieve a specific memory by its key.
        """
        try:
            result = store.get((namespace,), key)
            if result is None:
                return f"No memory found with key: {key}"

            memory_data = {
                "key": key,
                "content": result.value.get("content", str(result.value)),
            }
            if result.value.get("metadata"):
                memory_data["metadata"] = result.value["metadata"]

            return json.dumps(memory_data, indent=2)
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            raise ToolException(f"Failed to retrieve memory: {str(e)}")

    @tool("delete_memory", args_schema=DeleteMemoryInput)
    def delete_memory(key: str) -> str:
        """
        Delete a specific memory by its key.
        """
        try:
            store.delete((namespace,), key)
            return f"Successfully deleted memory with key: {key}"
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            raise ToolException(f"Failed to delete memory: {str(e)}")

    return [manage_memory, search_memory, get_memory, delete_memory]


def get_tools(tools_list: list, memory_store=None):
    """
    Get memory tools for the provided tool configurations.

    Args:
        tools_list: List of tool configurations
        memory_store: Optional memory store instance

    Returns:
        List of memory tools
    """
    all_tools = []

    for tool_config in tools_list:
        if tool_config.get('type') == 'memory' or tool_config.get('toolkit_name') == 'memory':
            try:
                toolkit_instance = MemoryToolkit.get_toolkit(
                    namespace=tool_config['settings'].get('namespace', str(tool_config['id'])),
                    store=tool_config['settings'].get('store', memory_store),
                    pgvector_configuration=tool_config['settings'].get('pgvector_configuration', {}),
                    toolkit_name=tool_config.get('toolkit_name', ''),
                    selected_tools=tool_config['settings'].get('selected_tools', [])
                )
                all_tools.extend(toolkit_instance.get_tools())
            except Exception as e:
                logger.error(f"Error in memory toolkit get_tools: {e}")
                logger.debug(f"Tool config: {tool_config}")
                raise

    return all_tools


class MemoryToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        # Define available tools statically - no external dependencies needed
        available_tools = {
            "manage_memory": ManageMemoryInput.model_json_schema(),
            "search_memory": SearchMemoryInput.model_json_schema(),
            "get_memory": GetMemoryInput.model_json_schema(),
            "delete_memory": DeleteMemoryInput.model_json_schema(),
        }

        return create_model(
            'memory',
            namespace=(str, Field(description="Memory namespace for organizing memories")),
            pgvector_configuration=(PgVectorConfiguration, Field(
                description="PgVector Configuration for PostgresStore",
                json_schema_extra={'configuration_types': ['pgvector']}
            )),
            selected_tools=(
                List[Literal["manage_memory", "search_memory", "get_memory", "delete_memory"]],
                Field(default=["manage_memory", "search_memory"], json_schema_extra={'args_schemas': available_tools})
            ),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Memory",
                    "icon_url": "memory.svg",
                    "hidden": False,
                    "categories": ["other"],
                    "extra_categories": ["long-term memory", "langgraph store"],
                }
            })
        )

    @classmethod
    def get_toolkit(cls, namespace: str, store=None, toolkit_name: str = None,
                    selected_tools: List[str] = None, **kwargs):
        """
        Get toolkit with memory tools using LangGraph's native store.

        Args:
            namespace: Memory namespace
            store: LangGraph store instance (PostgresStore or InMemoryStore)
            toolkit_name: Optional toolkit name for metadata
            selected_tools: List of tool names to include
            **kwargs: Additional arguments including pgvector_configuration
        """
        try:
            from langgraph.store.postgres import PostgresStore
        except ImportError:
            raise ImportError(
                "PostgreSQL dependencies (psycopg) are required for MemoryToolkit. "
                "Install with: pip install 'langgraph[postgres]'"
            )

        if store is None:
            # Create store from configuration
            from ...runtime.langchain.store_manager import get_manager
            conn_str = (kwargs.get('pgvector_configuration') or {}).get('connection_string', '')
            if not conn_str:
                raise ToolException("Connection string is required to create PostgresStore for memory toolkit.")
            store = get_manager().get_store(conn_str)

        # Create all memory tools
        all_tools = create_memory_tools(namespace=namespace, store=store)

        # Filter to selected tools if specified
        if selected_tools:
            all_tools = [t for t in all_tools if t.name in selected_tools]

        # Add metadata to tools if toolkit_name is provided
        if toolkit_name:
            for t in all_tools:
                t.metadata = {"toolkit_name": toolkit_name, "toolkit_type": name}

        return cls(tools=all_tools)

    def get_tools(self):
        return self.tools
