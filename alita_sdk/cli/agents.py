"""
Agent commands for Alita CLI.

Provides commands to work with agents interactively or in handoff mode,
supporting both platform agents and local agent definition files.
"""

import asyncio
import click
import json
import logging
import sqlite3
import sys
from typing import Optional, Dict, Any, List
from pathlib import Path
import yaml

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from rich.text import Text
from rich.status import Status
from rich.live import Live

from .cli import get_client
# Import from refactored modules
from .agent_ui import print_banner, print_help, display_output, extract_output_from_result
from .agent_loader import load_agent_definition
from .agent_executor import create_llm_instance, create_agent_executor, create_agent_executor_with_mcp
from .toolkit_loader import load_toolkit_config, load_toolkit_configs

logger = logging.getLogger(__name__)

# Create a rich console for beautiful output
console = Console()


def _load_mcp_tools(agent_def: Dict[str, Any], mcp_config_path: str) -> List[Dict[str, Any]]:
    """Load MCP tools from agent definition with tool-level filtering.
    
    Args:
        agent_def: Agent definition dictionary containing mcps list
        mcp_config_path: Path to mcp.json configuration file (workspace-level)
        
    Returns:
        List of toolkit configurations for MCP servers
    """
    from .mcp_loader import load_mcp_tools
    return load_mcp_tools(agent_def, mcp_config_path)


def _setup_local_agent_executor(client, agent_def: Dict[str, Any], toolkit_config: tuple,
                                config, model: Optional[str], temperature: Optional[float],
                                max_tokens: Optional[int], memory, work_dir: Optional[str]):
    """Setup local agent executor with all configurations.
    
    Returns:
        Tuple of (agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools)
    """
    # Load toolkit configs
    toolkit_configs = load_toolkit_configs(agent_def, toolkit_config)
    
    # Load MCP tools
    mcp_toolkit_configs = _load_mcp_tools(agent_def, config.mcp_config_path)
    toolkit_configs.extend(mcp_toolkit_configs)
    
    # Create LLM instance
    llm, llm_model, llm_temperature, llm_max_tokens = create_llm_instance(
        client, model, agent_def, temperature, max_tokens
    )
    
    # Add filesystem tools if --dir is provided
    filesystem_tools = None
    if work_dir:
        from .tools import get_filesystem_tools
        preset = agent_def.get('filesystem_tools_preset')
        include_tools = agent_def.get('filesystem_tools_include')
        exclude_tools = agent_def.get('filesystem_tools_exclude')
        filesystem_tools = get_filesystem_tools(work_dir, include_tools, exclude_tools, preset)
        
        tool_count = len(filesystem_tools)
        access_msg = f"✓ Granted filesystem access to: {work_dir} ({tool_count} tools)"
        if preset:
            access_msg += f" [preset: {preset}]"
        if include_tools:
            access_msg += f" [include: {', '.join(include_tools)}]"
        if exclude_tools:
            access_msg += f" [exclude: {', '.join(exclude_tools)}]"
        console.print(f"[dim]{access_msg}[/dim]")
    
    # Check if we have tools
    has_tools = bool(agent_def.get('tools') or toolkit_configs or filesystem_tools)
    has_mcp = any(tc.get('toolkit_type') == 'mcp' for tc in toolkit_configs)
    
    if not has_tools:
        return None, None, llm, llm_model, filesystem_tools
    
    # Create agent executor with or without MCP
    mcp_session_manager = None
    if has_mcp:
        # Create persistent event loop for MCP tools
        from alita_sdk.runtime.tools.llm import LLMNode
        if not hasattr(LLMNode, '_persistent_loop') or \
           LLMNode._persistent_loop is None or \
           LLMNode._persistent_loop.is_closed():
            LLMNode._persistent_loop = asyncio.new_event_loop()
            console.print("[dim]Created persistent event loop for MCP tools[/dim]")
        
        # Load MCP tools using persistent loop
        loop = LLMNode._persistent_loop
        asyncio.set_event_loop(loop)
        agent_executor, mcp_session_manager = loop.run_until_complete(
            create_agent_executor_with_mcp(
                client, agent_def, toolkit_configs,
                llm, llm_model, llm_temperature, llm_max_tokens, memory,
                filesystem_tools=filesystem_tools
            )
        )
    else:
        agent_executor = create_agent_executor(
            client, agent_def, toolkit_configs,
            llm, llm_model, llm_temperature, llm_max_tokens, memory,
            filesystem_tools=filesystem_tools
        )
    
    return agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools


def _select_agent_interactive(client, config) -> Optional[str]:
    """
    Show interactive menu to select an agent from platform and local agents.
    
    Returns:
        Agent source (name/id for platform, file path for local) or None if cancelled
    """
    from .config import CLIConfig
    
    console.print("\n🤖 [bold cyan]Select an agent to chat with:[/bold cyan]\n")
    
    agents_list = []
    
    # Load platform agents
    try:
        platform_agents = client.get_list_of_apps()
        for agent in platform_agents:
            agents_list.append({
                'type': 'platform',
                'name': agent['name'],
                'source': agent['name'],
                'description': agent.get('description', '')[:60]
            })
    except Exception as e:
        logger.debug(f"Failed to load platform agents: {e}")
    
    # Load local agents
    agents_dir = config.agents_dir
    search_dir = Path(agents_dir)
    
    if search_dir.exists():
        for pattern in ['*.agent.md', '*.agent.yaml', '*.agent.yml', '*.agent.json']:
            for file_path in search_dir.rglob(pattern):
                try:
                    agent_def = load_agent_definition(str(file_path))
                    agents_list.append({
                        'type': 'local',
                        'name': agent_def.get('name', file_path.stem),
                        'source': str(file_path),
                        'description': agent_def.get('description', '')[:60]
                    })
                except Exception as e:
                    logger.debug(f"Failed to load {file_path}: {e}")
    
    if not agents_list:
        console.print("[yellow]No agents found. Create an agent first or check your configuration.[/yellow]")
        return None
    
    # Display agents with numbers using rich
    for i, agent in enumerate(agents_list, 1):
        agent_type = "📦 Platform" if agent['type'] == 'platform' else "📁 Local"
        console.print(f"{i}. [[bold]{agent_type}[/bold]] [cyan]{agent['name']}[/cyan]")
        if agent['description']:
            console.print(f"   [dim]{agent['description']}[/dim]")
    
    console.print(f"\n[dim]0. Cancel[/dim]")
    
    # Get user selection
    while True:
        try:
            choice = input("\nSelect agent number: ").strip()
            
            if choice == '0':
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(agents_list):
                selected = agents_list[idx]
                console.print(f"\n✓ [green]Selected:[/green] [bold]{selected['name']}[/bold]")
                return selected['source']
            else:
                console.print(f"[yellow]Invalid selection. Please enter a number between 0 and {len(agents_list)}[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a valid number[/yellow]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n\n[dim]Cancelled.[/dim]")
            return None


@click.group()
def agent():
    """Agent testing and interaction commands."""
    pass


@agent.command('list')
@click.option('--local', is_flag=True, help='List local agent definition files')
@click.option('--directory', default=None, help='Directory to search for local agents (defaults to AGENTS_DIR from .env)')
@click.pass_context
def agent_list(ctx, local: bool, directory: Optional[str]):
    """
    List available agents.
    
    By default, lists agents from the platform.
    Use --local to list agent definition files in the local directory.
    """
    formatter = ctx.obj['formatter']
    config = ctx.obj['config']
    
    try:
        if local:
            # List local agent definition files
            if directory is None:
                directory = config.agents_dir
            search_dir = Path(directory)
            
            if not search_dir.exists():
                console.print(f"[red]Directory not found: {directory}[/red]")
                return
            
            agents = []
            
            # Find agent definition files
            for pattern in ['*.agent.md', '*.agent.yaml', '*.agent.yml', '*.agent.json']:
                for file_path in search_dir.rglob(pattern):
                    try:
                        agent_def = load_agent_definition(str(file_path))
                        # Use relative path if already relative, otherwise make it relative to cwd
                        try:
                            display_path = str(file_path.relative_to(Path.cwd()))
                        except ValueError:
                            display_path = str(file_path)
                        
                        agents.append({
                            'name': agent_def.get('name', file_path.stem),
                            'file': display_path,
                            'description': agent_def.get('description', '')[:80]
                        })
                    except Exception as e:
                        logger.debug(f"Failed to load {file_path}: {e}")
            
            if not agents:
                console.print(f"\n[yellow]No agent definition files found in {directory}[/yellow]")
                return
            
            # Display local agents in a table
            table = Table(
                title=f"Local Agent Definitions in {directory}",
                show_header=True,
                header_style="bold cyan",
                border_style="cyan",
                box=box.ROUNDED
            )
            table.add_column("Name", style="bold cyan", no_wrap=True)
            table.add_column("File", style="dim")
            table.add_column("Description", style="white")
            
            for agent_info in sorted(agents, key=lambda x: x['name']):
                table.add_row(
                    agent_info['name'],
                    agent_info['file'],
                    agent_info['description'] or "-"
                )
            
            console.print("\n")
            console.print(table)
            console.print(f"\n[green]Total: {len(agents)} local agents[/green]")
            
        else:
            # List platform agents
            client = get_client(ctx)
            
            agents = client.get_list_of_apps()
            
            if formatter.__class__.__name__ == 'JSONFormatter':
                click.echo(formatter._dump({'agents': agents, 'total': len(agents)}))
            else:
                table = Table(
                    title="Available Platform Agents",
                    show_header=True,
                    header_style="bold cyan",
                    border_style="cyan",
                    box=box.ROUNDED
                )
                table.add_column("ID", style="yellow", no_wrap=True)
                table.add_column("Name", style="bold cyan")
                table.add_column("Description", style="white")
                
                for agent_info in agents:
                    table.add_row(
                        str(agent_info['id']),
                        agent_info['name'],
                        agent_info.get('description', '')[:80] or "-"
                    )
                
                console.print("\n")
                console.print(table)
                console.print(f"\n[green]Total: {len(agents)} agents[/green]")
        
    except Exception as e:
        logger.exception("Failed to list agents")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()


@agent.command('show')
@click.argument('agent_source')
@click.option('--version', help='Agent version (for platform agents)')
@click.pass_context
def agent_show(ctx, agent_source: str, version: Optional[str]):
    """
    Show agent details.
    
    AGENT_SOURCE can be:
    - Platform agent ID or name (e.g., "123" or "my-agent")
    - Path to local agent file (e.g., ".github/agents/sdk-dev.agent.md")
    """
    formatter = ctx.obj['formatter']
    
    try:
        # Check if it's a file path
        if Path(agent_source).exists():
            # Local agent file
            agent_def = load_agent_definition(agent_source)
            
            if formatter.__class__.__name__ == 'JSONFormatter':
                click.echo(formatter._dump(agent_def))
            else:
                # Create details panel
                details = Text()
                details.append("File: ", style="bold")
                details.append(f"{agent_source}\n", style="cyan")
                
                if agent_def.get('description'):
                    details.append("\nDescription: ", style="bold")
                    details.append(f"{agent_def['description']}\n", style="white")
                
                if agent_def.get('model'):
                    details.append("Model: ", style="bold")
                    details.append(f"{agent_def['model']}\n", style="cyan")
                
                if agent_def.get('tools'):
                    details.append("Tools: ", style="bold")
                    details.append(f"{', '.join(agent_def['tools'])}\n", style="cyan")
                
                if agent_def.get('temperature') is not None:
                    details.append("Temperature: ", style="bold")
                    details.append(f"{agent_def['temperature']}\n", style="cyan")
                
                panel = Panel(
                    details,
                    title=f"Local Agent: {agent_def.get('name', 'Unknown')}",
                    title_align="left",
                    border_style="cyan",
                    box=box.ROUNDED
                )
                console.print("\n")
                console.print(panel)
                
                if agent_def.get('system_prompt'):
                    console.print("\n[bold]System Prompt:[/bold]")
                    console.print(Panel(agent_def['system_prompt'][:500] + "...", border_style="dim", box=box.ROUNDED))
        
        else:
            # Platform agent
            client = get_client(ctx)
            
            # Try to find agent by ID or name
            agents = client.get_list_of_apps()
            
            agent = None
            try:
                agent_id = int(agent_source)
                agent = next((a for a in agents if a['id'] == agent_id), None)
            except ValueError:
                agent = next((a for a in agents if a['name'] == agent_source), None)
            
            if not agent:
                raise click.ClickException(f"Agent '{agent_source}' not found")
            
            # Get details
            details = client.get_app_details(agent['id'])
            
            if formatter.__class__.__name__ == 'JSONFormatter':
                click.echo(formatter._dump(details))
            else:
                # Create platform agent details panel
                content = Text()
                content.append("ID: ", style="bold")
                content.append(f"{details['id']}\n", style="yellow")
                
                if details.get('description'):
                    content.append("\nDescription: ", style="bold")
                    content.append(f"{details['description']}\n", style="white")
                
                panel = Panel(
                    content,
                    title=f"Agent: {details['name']}",
                    title_align="left",
                    border_style="cyan",
                    box=box.ROUNDED
                )
                console.print("\n")
                console.print(panel)
                
                # Display versions in a table
                if details.get('versions'):
                    console.print("\n[bold]Versions:[/bold]")
                    versions_table = Table(box=box.ROUNDED, border_style="dim")
                    versions_table.add_column("Name", style="cyan")
                    versions_table.add_column("ID", style="yellow")
                    for ver in details.get('versions', []):
                        versions_table.add_row(ver['name'], str(ver['id']))
                    console.print(versions_table)
    
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to show agent details")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()


@agent.command('chat')
@click.argument('agent_source', required=False)
@click.option('--version', help='Agent version (for platform agents)')
@click.option('--toolkit-config', multiple=True, type=click.Path(exists=True),
              help='Toolkit configuration files (can specify multiple)')
@click.option('--thread-id', help='Continue existing conversation thread')
@click.option('--model', help='Override LLM model')
@click.option('--temperature', type=float, help='Override temperature')
@click.option('--max-tokens', type=int, help='Override max tokens')
@click.option('--dir', 'work_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='Grant agent filesystem access to this directory')
@click.pass_context
def agent_chat(ctx, agent_source: Optional[str], version: Optional[str], 
               toolkit_config: tuple, thread_id: Optional[str],
               model: Optional[str], temperature: Optional[float], 
               max_tokens: Optional[int], work_dir: Optional[str]):
    """
    Start interactive chat with an agent.
    
    If AGENT_SOURCE is not provided, shows an interactive menu to select from
    available agents (both platform and local).
    
    AGENT_SOURCE can be:
    - Platform agent ID or name
    - Path to local agent file
    
    Examples:
    
        # Interactive selection
        alita-cli agent chat
        
        # Chat with platform agent
        alita-cli agent chat my-agent
        
        # Chat with local agent
        alita-cli agent chat .github/agents/sdk-dev.agent.md
        
        # With toolkit configurations
        alita-cli agent chat my-agent \\
            --toolkit-config jira-config.json \\
            --toolkit-config github-config.json
        
        # With filesystem access
        alita-cli agent chat my-agent --dir ./workspace
        
        # Continue previous conversation
        alita-cli agent chat my-agent --thread-id abc123
    """
    formatter = ctx.obj['formatter']
    config = ctx.obj['config']
    client = get_client(ctx)
    
    try:
        # If no agent specified, show selection menu
        if not agent_source:
            agent_source = _select_agent_interactive(client, config)
            if not agent_source:
                console.print("[yellow]No agent selected. Exiting.[/yellow]")
                return
        
        # Load agent
        is_local = Path(agent_source).exists()
        
        if is_local:
            agent_def = load_agent_definition(agent_source)
            agent_name = agent_def.get('name', Path(agent_source).stem)
            agent_type = "Local Agent"
        else:
            # Platform agent - find it
            agents = client.get_list_of_apps()
            agent = None
            
            try:
                agent_id = int(agent_source)
                agent = next((a for a in agents if a['id'] == agent_id), None)
            except ValueError:
                agent = next((a for a in agents if a['name'] == agent_source), None)
            
            if not agent:
                raise click.ClickException(f"Agent '{agent_source}' not found")
            
            agent_name = agent['name']
            agent_type = "Platform Agent"
        
        # Print nice banner
        print_banner(agent_name, agent_type)
        print_help()
        
        # Initialize conversation
        chat_history = []
        
        # Create memory for agent
        from langgraph.checkpoint.sqlite import SqliteSaver
        memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
        
        # Create agent executor
        if is_local:
            # Display configuration
            llm_model_display = model or agent_def.get('model', 'gpt-4o')
            llm_temperature_display = temperature if temperature is not None else agent_def.get('temperature', 0.7)
            console.print()
            console.print(f"✓ [green]Using model:[/green] [bold]{llm_model_display}[/bold]")
            console.print(f"✓ [green]Temperature:[/green] [bold]{llm_temperature_display}[/bold]")
            if agent_def.get('tools'):
                console.print(f"✓ [green]Tools:[/green] [bold]{', '.join(agent_def['tools'])}[/bold]")
            console.print()
            
            # Setup local agent executor (handles all config, tools, MCP, etc.)
            try:
                agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools = _setup_local_agent_executor(
                    client, agent_def, toolkit_config, config, model, temperature, max_tokens, memory, work_dir
                )
            except Exception:
                return
        else:
            # Platform agent
            details = client.get_app_details(agent['id'])
            
            if version:
                version_obj = next((v for v in details['versions'] if v['name'] == version), None)
                if not version_obj:
                    raise click.ClickException(f"Version '{version}' not found")
                version_id = version_obj['id']
            else:
                # Use first version
                version_id = details['versions'][0]['id']
            
            # Display configuration
            console.print()
            console.print("✓ [green]Connected to platform agent[/green]")
            console.print()
            
            agent_executor = client.application(
                application_id=agent['id'],
                application_version_id=version_id,
                memory=memory,
                chat_history=chat_history
            )
            llm = None  # Platform agents don't use direct LLM
        
        # Interactive chat loop
        while True:
            try:
                # Styled prompt
                console.print("\n[bold bright_white]>[/bold bright_white] ", end="")
                user_input = input().strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['exit', 'quit']:
                    console.print("\n[bold cyan]👋 Goodbye![/bold cyan]\n")
                    break
                
                if user_input == '/clear':
                    chat_history = []
                    console.print("[green]✓ Conversation history cleared.[/green]")
                    continue
                
                if user_input == '/history':
                    if not chat_history:
                        console.print("[yellow]No conversation history yet.[/yellow]")
                    else:
                        console.print("\n[bold cyan]── Conversation History ──[/bold cyan]")
                        for i, msg in enumerate(chat_history, 1):
                            role = msg.get('role', 'unknown')
                            content = msg.get('content', '')
                            role_color = 'blue' if role == 'user' else 'green'
                            console.print(f"\n[bold {role_color}]{i}. {role.upper()}:[/bold {role_color}] {content[:100]}...")
                    continue
                
                if user_input == '/save':
                    console.print("[yellow]Save to file (default: conversation.json):[/yellow] ", end="")
                    filename = input().strip()
                    filename = filename or "conversation.json"
                    with open(filename, 'w') as f:
                        json.dump({'history': chat_history}, f, indent=2)
                    console.print(f"[green]✓ Conversation saved to {filename}[/green]")
                    continue
                
                if user_input == '/help':
                    print_help()
                    continue
                
                # Execute agent
                if is_local and agent_executor is None:
                    # Local agent without tools: use direct LLM call with streaming
                    system_prompt = agent_def.get('system_prompt', '')
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    
                    # Add chat history
                    for msg in chat_history:
                        messages.append(msg)
                    
                    # Add user message
                    messages.append({"role": "user", "content": user_input})
                    
                    try:
                        # Try streaming if available
                        if hasattr(llm, 'stream'):
                            output_chunks = []
                            first_chunk = True
                            
                            # Show spinner until first token arrives
                            status = console.status("[yellow]Thinking...[/yellow]", spinner="dots")
                            status.start()
                            
                            # Stream the response token by token
                            for chunk in llm.stream(messages):
                                if hasattr(chunk, 'content'):
                                    token = chunk.content
                                else:
                                    token = str(chunk)
                                
                                if token:
                                    # Stop spinner and show agent name on first token
                                    if first_chunk:
                                        status.stop()
                                        console.print(f"\n[bold bright_cyan]{agent_name}:[/bold bright_cyan]\n", end="")
                                        first_chunk = False
                                    
                                    console.print(token, end="", markup=False)
                                    output_chunks.append(token)
                            
                            # Stop status if still running (no tokens received)
                            if first_chunk:
                                status.stop()
                                console.print(f"\n[bold bright_cyan]{agent_name}:[/bold bright_cyan]\n", end="")
                            
                            output = ''.join(output_chunks)
                            console.print()  # New line after streaming
                        else:
                            # Fallback to non-streaming with spinner
                            with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                                response = llm.invoke(messages)
                                if hasattr(response, 'content'):
                                    output = response.content
                                else:
                                    output = str(response)
                            
                            # Display response after spinner stops
                            console.print(f"\n[bold bright_cyan]{agent_name}:[/bold bright_cyan]")
                            if any(marker in output for marker in ['```', '**', '##', '- ', '* ']):
                                console.print(Markdown(output))
                            else:
                                console.print(output)
                    except Exception as e:
                        console.print(f"\n[red]✗ Error: {e}[/red]\n")
                        continue
                else:
                    # Agent with tools or platform agent: use agent executor
                    with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                        result = agent_executor.invoke({
                            "input": [user_input] if not is_local else user_input,
                            "chat_history": chat_history
                        })
                        
                        # Extract output from result
                        output = extract_output_from_result(result)
                    
                    # Display response
                    console.print(f"\n[bold bright_cyan]{agent_name}:[/bold bright_cyan]")
                    if any(marker in output for marker in ['```', '**', '##', '- ', '* ']):
                        console.print(Markdown(output))
                    else:
                        console.print(output)
                
                # Update chat history
                chat_history.append({"role": "user", "content": user_input})
                chat_history.append({"role": "assistant", "content": output})
                
            except KeyboardInterrupt:
                console.print("\n\n[yellow]Interrupted. Type 'exit' to quit or continue chatting.[/yellow]")
                continue
            except EOFError:
                console.print("\n\n[bold cyan]Goodbye! 👋[/bold cyan]")
                break
    
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to start chat")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()


@agent.command('run')
@click.argument('agent_source')
@click.argument('message')
@click.option('--version', help='Agent version (for platform agents)')
@click.option('--toolkit-config', multiple=True, type=click.Path(exists=True),
              help='Toolkit configuration files')
@click.option('--model', help='Override LLM model')
@click.option('--temperature', type=float, help='Override temperature')
@click.option('--max-tokens', type=int, help='Override max tokens')
@click.option('--save-thread', help='Save thread ID to file for continuation')
@click.option('--dir', 'work_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='Grant agent filesystem access to this directory')
@click.pass_context
def agent_run(ctx, agent_source: str, message: str, version: Optional[str],
              toolkit_config: tuple, model: Optional[str], 
              temperature: Optional[float], max_tokens: Optional[int],
              save_thread: Optional[str], work_dir: Optional[str]):
    """
    Run agent with a single message (handoff mode).
    
    AGENT_SOURCE can be:
    - Platform agent ID or name
    - Path to local agent file
    
    MESSAGE is the input message to send to the agent.
    
    Examples:
    
        # Simple query
        alita-cli agent run my-agent "What is the status of JIRA-123?"
        
        # With local agent
        alita-cli agent run .github/agents/sdk-dev.agent.md \\
            "Create a new toolkit for Stripe API"
        
        # With toolkit configs and JSON output
        alita-cli --output json agent run my-agent "Search for bugs" \\
            --toolkit-config jira-config.json
        
        # With filesystem access
        alita-cli agent run my-agent "Analyze the code in src/" --dir ./myproject
        
        # Save thread for continuation
        alita-cli agent run my-agent "Start task" \\
            --save-thread thread.txt
    """
    formatter = ctx.obj['formatter']
    client = get_client(ctx)
    
    try:
        # Load agent
        is_local = Path(agent_source).exists()
        
        if is_local:
            agent_def = load_agent_definition(agent_source)
            agent_name = agent_def.get('name', Path(agent_source).stem)
            
            # Create memory for agent
            from langgraph.checkpoint.sqlite import SqliteSaver
            memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
            
            # Setup local agent executor (reuses same logic as agent_chat)
            try:
                agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools = _setup_local_agent_executor(
                    client, agent_def, toolkit_config, ctx.obj['config'], model, temperature, max_tokens, memory, work_dir
                )
            except Exception as e:
                error_panel = Panel(
                    f"Failed to setup agent: {e}",
                    title="Error",
                    border_style="red",
                    box=box.ROUNDED
                )
                console.print(error_panel, style="red")
                raise click.Abort()
            
            # Execute agent
            if agent_executor:
                
                # Execute with spinner for non-JSON output
                if formatter.__class__.__name__ == 'JSONFormatter':
                    with console.status("[yellow]Processing...[/yellow]", spinner="dots"):
                        result = agent_executor.invoke({
                            "input": message,
                            "chat_history": []
                        })
                    
                    click.echo(formatter._dump({
                        'agent': agent_name,
                        'message': message,
                        'response': extract_output_from_result(result),
                        'full_result': result
                    }))
                else:
                    # Show spinner while executing
                    with console.status("[yellow]Processing...[/yellow]", spinner="dots"):
                        result = agent_executor.invoke({
                            "input": message,
                            "chat_history": []
                        })
                    
                    # Extract and display output
                    output = extract_output_from_result(result)
                    display_output(agent_name, message, output)
            else:
                # Simple LLM mode without tools
                system_prompt = agent_def.get('system_prompt', '')
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": message})
                
                # Execute with spinner for non-JSON output
                if formatter.__class__.__name__ == 'JSONFormatter':
                    response = llm.invoke(messages)
                    if hasattr(response, 'content'):
                        output = response.content
                    else:
                        output = str(response)
                    
                    click.echo(formatter._dump({
                        'agent': agent_name,
                        'message': message,
                        'response': output
                    }))
                else:
                    # Show spinner while executing
                    with console.status("[yellow]Processing...[/yellow]", spinner="dots"):
                        response = llm.invoke(messages)
                        if hasattr(response, 'content'):
                            output = response.content
                        else:
                            output = str(response)
                    
                    # Display output
                    display_output(agent_name, message, output)
        
        else:
            # Platform agent
            agents = client.get_list_of_apps()
            agent = None
            
            try:
                agent_id = int(agent_source)
                agent = next((a for a in agents if a['id'] == agent_id), None)
            except ValueError:
                agent = next((a for a in agents if a['name'] == agent_source), None)
            
            if not agent:
                raise click.ClickException(f"Agent '{agent_source}' not found")
            
            # Get version
            details = client.get_app_details(agent['id'])
            
            if version:
                version_obj = next((v for v in details['versions'] if v['name'] == version), None)
                if not version_obj:
                    raise click.ClickException(f"Version '{version}' not found")
                version_id = version_obj['id']
            else:
                version_id = details['versions'][0]['id']
            
            # Load toolkit configs from CLI options
            toolkit_configs = []
            if toolkit_config:
                for config_path in toolkit_config:
                    toolkit_configs.append(load_toolkit_config(config_path))
            
            # Create memory
            from langgraph.checkpoint.sqlite import SqliteSaver
            memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
            
            # Create agent executor
            agent_executor = client.application(
                application_id=agent['id'],
                application_version_id=version_id,
                memory=memory
            )
            
            # Execute with spinner for non-JSON output
            if formatter.__class__.__name__ == 'JSONFormatter':
                result = agent_executor.invoke({
                    "input": [message],
                    "chat_history": []
                })
                
                click.echo(formatter._dump({
                    'agent': agent['name'],
                    'message': message,
                    'response': result.get('output', ''),
                    'full_result': result
                }))
            else:
                # Show spinner while executing
                with console.status("[yellow]Processing...[/yellow]", spinner="dots"):
                    result = agent_executor.invoke({
                        "input": [message],
                        "chat_history": []
                    })
                
                # Display output
                response = result.get('output', 'No response')
                display_output(agent['name'], message, response)
            
            # Save thread if requested
            if save_thread:
                thread_data = {
                    'agent_id': agent['id'],
                    'agent_name': agent['name'],
                    'version_id': version_id,
                    'thread_id': result.get('thread_id'),
                    'last_message': message
                }
                with open(save_thread, 'w') as f:
                    json.dump(thread_data, f, indent=2)
                logger.info(f"Thread saved to {save_thread}")
    
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to run agent")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()
