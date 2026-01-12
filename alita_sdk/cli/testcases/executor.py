"""
Executor cache management for test execution.

Handles creating, caching, and cleaning up agent executors.
"""

import logging
import sqlite3
from typing import Dict, Optional, Any, Tuple
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


def cleanup_executor_cache(cache: Dict[str, tuple], cache_name: str = "executor") -> None:
    """Clean up executor cache resources.
    
    Args:
        cache: Dictionary of cached executors
        cache_name: Name of cache for logging
    """
    console.print(f"[dim]Cleaning up {cache_name} cache...[/dim]")
    for cache_key, cached_items in cache.items():
        try:
            # Extract memory from tuple (second element)
            memory = cached_items[1] if len(cached_items) > 1 else None
            
            # Close SQLite memory connection
            if memory and hasattr(memory, 'conn') and memory.conn:
                memory.conn.close()
        except Exception as e:
            logger.debug(f"Error cleaning up {cache_name} cache for {cache_key}: {e}")


def create_executor_from_cache(
    cache: Dict[str, tuple], 
    cache_key: str, 
    client, 
    agent_def: Dict[str, Any], 
    toolkit_config_path: Optional[str],
    config, 
    model: Optional[str], 
    temperature: Optional[float],
    max_tokens: Optional[int], 
    work_dir: Optional[str],
    setup_executor_func
) -> Tuple:
    """Get or create executor from cache.
    
    Args:
        cache: Executor cache dictionary
        cache_key: Key for caching
        client: API client
        agent_def: Agent definition
        toolkit_config_path: Path to toolkit config
        config: CLI configuration
        model: Model override
        temperature: Temperature override
        max_tokens: Max tokens override
        work_dir: Working directory
        setup_executor_func: Function to setup local agent executor
        
    Returns:
        Tuple of (agent_executor, memory, mcp_session_manager)
    """
    if cache_key in cache:
        return cache[cache_key]
    
    # Create new executor
    from langgraph.checkpoint.sqlite import SqliteSaver
    
    memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
    toolkit_config_tuple = (toolkit_config_path,) if toolkit_config_path else ()
    
    agent_executor, mcp_session_manager, _, _, _, _, _ = setup_executor_func(
        client, agent_def, toolkit_config_tuple, config, model, temperature, 
        max_tokens, memory, work_dir
    )
    
    # Cache the executor
    cached_tuple = (agent_executor, memory, mcp_session_manager)
    cache[cache_key] = cached_tuple
    return cached_tuple
