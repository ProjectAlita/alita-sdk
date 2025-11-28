"""
Agent executor creation and management.

Creates LLM instances and agent executors with support for MCP tools.
"""

from typing import Optional, Dict, Any, List, Tuple
from rich.console import Console

from .agent_loader import build_agent_data_structure
from alita_sdk.runtime.langchain.assistant import Assistant

console = Console()


def create_llm_instance(client, model: Optional[str], agent_def: Dict[str, Any], 
                       temperature: Optional[float], max_tokens: Optional[int]):
    """Create LLM instance with appropriate configuration."""
    llm_model = model or agent_def.get('model', 'gpt-4o')
    llm_temperature = temperature if temperature is not None else agent_def.get('temperature', 0.7)
    llm_max_tokens = max_tokens or agent_def.get('max_tokens', 2000)
    
    try:
        llm = client.get_llm(
            model_name=llm_model,
            model_config={
                'temperature': llm_temperature,
                'max_tokens': llm_max_tokens
            }
        )
        return llm, llm_model, llm_temperature, llm_max_tokens
    except Exception as e:
        console.print(f"\n✗ [red]Failed to create LLM instance:[/red] {e}")
        console.print("[yellow]Hint: Make sure OPENAI_API_KEY or other LLM credentials are set[/yellow]")
        raise


def _create_assistant(client, agent_data: Dict[str, Any], llm, memory, tools: List) -> Assistant:
    """Create Assistant instance with given configuration.
    
    Args:
        client: Alita client instance
        agent_data: Agent configuration data
        llm: LLM instance
        memory: Memory/checkpoint instance
        tools: List of tools to add to agent
        
    Returns:
        Assistant instance
    """
    return Assistant(
        alita=client,
        data=agent_data,
        client=llm,
        chat_history=[],
        app_type=agent_data.get('agent_type', 'react'),
        tools=tools,
        memory=memory,
        store=None,
        debug_mode=False,
        mcp_tokens=None
    )


def create_agent_executor(client, agent_def: Dict[str, Any], toolkit_configs: List[Dict[str, Any]],
                         llm, llm_model: str, llm_temperature: float, llm_max_tokens: int, memory,
                         filesystem_tools: Optional[List] = None, mcp_tools: Optional[List] = None,
                         terminal_tools: Optional[List] = None, planning_tools: Optional[List] = None):
    """Create agent executor for local agents with tools (sync version).
    
    Note: mcp_tools parameter is deprecated - use create_agent_executor_with_mcp for MCP support.
    """
    agent_data = build_agent_data_structure(
        agent_def=agent_def,
        toolkit_configs=toolkit_configs,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens
    )
    
    # Combine all tools
    additional_tools = []
    if filesystem_tools:
        additional_tools.extend(filesystem_tools)
    if terminal_tools:
        additional_tools.extend(terminal_tools)
    if planning_tools:
        additional_tools.extend(planning_tools)
    if mcp_tools:
        additional_tools.extend(mcp_tools)
    
    assistant = _create_assistant(client, agent_data, llm, memory, additional_tools)
    return assistant.runnable()


async def create_agent_executor_with_mcp(
    client, 
    agent_def: Dict[str, Any], 
    toolkit_configs: List[Dict[str, Any]],
    llm, 
    llm_model: str, 
    llm_temperature: float, 
    llm_max_tokens: int, 
    memory,
    filesystem_tools: Optional[List] = None,
    terminal_tools: Optional[List] = None,
    planning_tools: Optional[List] = None
) -> Tuple[Any, Optional[Any]]:
    """Create agent executor with MCP tools using persistent sessions.
    
    Returns:
        Tuple of (agent_executor, mcp_session_manager) where session_manager must be kept alive
        to maintain stateful MCP server state (e.g., Playwright browser sessions).
        
    See: https://github.com/langchain-ai/langchain-mcp-adapters/issues/178
    """
    from .mcp_loader import load_mcp_tools_async
    
    # Separate MCP toolkit configs from regular configs
    mcp_configs = [tc for tc in toolkit_configs if tc.get('toolkit_type') == 'mcp']
    regular_configs = [tc for tc in toolkit_configs if tc.get('toolkit_type') != 'mcp']
    
    # Load MCP tools with persistent sessions
    mcp_session_manager = None
    mcp_tools = []
    if mcp_configs:
        console.print("\n[cyan]Loading MCP tools with persistent sessions...[/cyan]")
        mcp_session_manager, mcp_tools = await load_mcp_tools_async(mcp_configs)
        if mcp_tools:
            console.print(f"[green]✓ Loaded {len(mcp_tools)} MCP tools with persistent sessions[/green]\n")
    
    # Build agent data structure
    agent_data = build_agent_data_structure(
        agent_def=agent_def,
        toolkit_configs=regular_configs,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens
    )
    
    # Combine all tools
    additional_tools = []
    if filesystem_tools:
        additional_tools.extend(filesystem_tools)
    if terminal_tools:
        additional_tools.extend(terminal_tools)
    if planning_tools:
        additional_tools.extend(planning_tools)
    if mcp_tools:
        additional_tools.extend(mcp_tools)
    
    assistant = _create_assistant(client, agent_data, llm, memory, additional_tools)
    
    # Return agent and session manager (must be kept alive for stateful MCP tools)
    return assistant.runnable(), mcp_session_manager
