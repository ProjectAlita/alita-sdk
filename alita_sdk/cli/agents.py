"""
Agent commands for Alita CLI.

Provides commands to work with agents interactively or in handoff mode,
supporting both platform agents and local agent definition files.
"""

import click
import json
import logging
import sqlite3
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
from .config import substitute_env_vars

logger = logging.getLogger(__name__)

# Create a rich console for beautiful output
console = Console()


def _print_banner(agent_name: str, agent_type: str = "local"):
    """Print a nice banner for the chat session using rich."""
    content = Text()
    content.append("🤖  ALITA AGENT CHAT\n\n", style="bold cyan")
    content.append(f"Agent: ", style="bold")
    content.append(f"{agent_name}\n", style="cyan")
    content.append(f"Type:  ", style="bold")
    content.append(f"{agent_type}", style="cyan")
    
    panel = Panel(
        content,
        box=box.DOUBLE,
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(panel)


def _print_help():
    """Print help message with commands using rich table."""
    table = Table(
        show_header=True,
        header_style="bold yellow",
        border_style="yellow",
        box=box.ROUNDED,
        title="Commands",
        title_style="bold yellow"
    )
    
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    
    table.add_row("/clear", "Clear conversation history")
    table.add_row("/history", "Show conversation history")
    table.add_row("/save", "Save conversation to file")
    table.add_row("/help", "Show this help")
    table.add_row("exit/quit", "End conversation")
    table.add_row("", "")
    table.add_row("@", "Mention files")
    table.add_row("/", "Run commands")
    
    console.print(table)


def load_agent_definition(file_path: str) -> Dict[str, Any]:
    """
    Load agent definition from file.
    
    Supports:
    - YAML files (.yaml, .yml)
    - JSON files (.json)
    - Markdown files with YAML frontmatter (.md)
    
    Args:
        file_path: Path to agent definition file
        
    Returns:
        Dictionary with agent configuration
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Agent definition not found: {file_path}")
    
    content = path.read_text()
    
    # Handle markdown with YAML frontmatter
    if path.suffix == '.md':
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                system_prompt = parts[2].strip()
                
                # Apply environment variable substitution
                system_prompt = substitute_env_vars(system_prompt)
                
                return {
                    'name': frontmatter.get('name', path.stem),
                    'description': frontmatter.get('description', ''),
                    'system_prompt': system_prompt,
                    'model': frontmatter.get('model'),
                    'tools': frontmatter.get('tools', []),
                    'temperature': frontmatter.get('temperature'),
                    'max_tokens': frontmatter.get('max_tokens'),
                    'toolkit_configs': frontmatter.get('toolkit_configs', []),
                }
        
        # Plain markdown - use content as system prompt
        return {
            'name': path.stem,
            'system_prompt': substitute_env_vars(content),
        }
    
    # Handle YAML
    if path.suffix in ['.yaml', '.yml']:
        content = substitute_env_vars(content)
        config = yaml.safe_load(content)
        if 'system_prompt' in config:
            config['system_prompt'] = substitute_env_vars(config['system_prompt'])
        return config
    
    # Handle JSON
    if path.suffix == '.json':
        content = substitute_env_vars(content)
        config = json.loads(content)
        if 'system_prompt' in config:
            config['system_prompt'] = substitute_env_vars(config['system_prompt'])
        return config
    
    raise ValueError(f"Unsupported file format: {path.suffix}")


def load_toolkit_config(file_path: str) -> Dict[str, Any]:
    """Load toolkit configuration from JSON file with env var substitution."""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Toolkit configuration not found: {file_path}")
    
    with open(path) as f:
        content = f.read()
    
    # Apply environment variable substitution
    content = substitute_env_vars(content)
    return json.loads(content)


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
@click.pass_context
def agent_chat(ctx, agent_source: Optional[str], version: Optional[str], 
               toolkit_config: tuple, thread_id: Optional[str],
               model: Optional[str], temperature: Optional[float], 
               max_tokens: Optional[int]):
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
        _print_banner(agent_name, agent_type)
        _print_help()
        
        # Initialize conversation
        chat_history = []
        
        # Create memory for agent
        from langgraph.checkpoint.sqlite import SqliteSaver
        memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
        
        # Load toolkits if provided
        toolkit_configs = []
        
        # First load from agent definition if local
        if is_local and 'toolkit_configs' in agent_def:
            for tk_config in agent_def['toolkit_configs']:
                if isinstance(tk_config, dict):
                    if 'file' in tk_config:
                        # Load from file
                        config = load_toolkit_config(tk_config['file'])
                        toolkit_configs.append(config)
                        console.print(f"[dim]Loaded toolkit config from agent definition: {tk_config['file']}[/dim]")
                    elif 'config' in tk_config:
                        # Inline config
                        toolkit_configs.append(tk_config['config'])
                        console.print(f"[dim]Loaded inline toolkit config: {tk_config['config'].get('toolkit_name', 'unknown')}[/dim]")
        
        # Then load from --toolkit-config options
        if toolkit_config:
            for config_path in toolkit_config:
                config = load_toolkit_config(config_path)
                toolkit_configs.append(config)
                console.print(f"[dim]Loaded toolkit config: {config_path}[/dim]")
        
        # Auto-add toolkits to tools if not already present
        if is_local and toolkit_configs:
            tools = agent_def.get('tools', [])
            for tk_config in toolkit_configs:
                toolkit_name = tk_config.get('toolkit_name')
                if toolkit_name and toolkit_name not in tools:
                    tools.append(toolkit_name)
                    console.print(f"[dim]Auto-added toolkit to tools: {toolkit_name}[/dim]")
            agent_def['tools'] = tools
        
        # Create agent executor
        if is_local:
            # For local agents, use direct LLM integration
            llm_model = model or agent_def.get('model', 'gpt-4o')
            llm_temperature = temperature if temperature is not None else agent_def.get('temperature', 0.7)
            llm_max_tokens = max_tokens or agent_def.get('max_tokens', 2000)
            
            system_prompt = agent_def.get('system_prompt', '')
            
            # Display configuration
            console.print()
            console.print(f"✓ [green]Using model:[/green] [bold]{llm_model}[/bold]")
            console.print(f"✓ [green]Temperature:[/green] [bold]{llm_temperature}[/bold]")
            if agent_def.get('tools'):
                console.print(f"✓ [green]Tools:[/green] [bold]{', '.join(agent_def['tools'])}[/bold]")
            console.print()
            
            # Create LLM instance using AlitaClient
            try:
                llm = client.get_llm(
                    model_name=llm_model,
                    model_config={
                        'temperature': llm_temperature,
                        'max_tokens': llm_max_tokens
                    }
                )
            except Exception as e:
                console.print(f"\n✗ [red]Failed to create LLM instance:[/red] {e}")
                console.print("[yellow]Hint: Make sure OPENAI_API_KEY or other LLM credentials are set[/yellow]")
                return
            
            agent_executor = None  # Local agents use direct LLM calls
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
                    _print_help()
                    continue
                
                # Execute agent
                if is_local:
                    # Local agent: use direct LLM call with streaming
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
                    # Platform agent: use agent executor
                    with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                        result = agent_executor.invoke({
                            "input": [user_input],
                            "chat_history": chat_history
                        })
                        output = result.get('output', '')
                    
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
@click.pass_context
def agent_run(ctx, agent_source: str, message: str, version: Optional[str],
              toolkit_config: tuple, model: Optional[str], 
              temperature: Optional[float], max_tokens: Optional[int],
              save_thread: Optional[str]):
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
        
        # Save thread for continuation
        alita-cli agent run my-agent "Start task" \\
            --save-thread thread.txt
    """
    formatter = ctx.obj['formatter']
    client = get_client(ctx)
    
    try:
        # Load agent
        is_local = Path(agent_source).exists()
        
        # Load toolkits
        toolkit_configs = []
        
        if is_local:
            agent_def = load_agent_definition(agent_source)
            agent_name = agent_def.get('name', Path(agent_source).stem)
            
            # Load toolkit configs from agent definition
            if 'toolkit_configs' in agent_def:
                for tk_config in agent_def['toolkit_configs']:
                    if isinstance(tk_config, dict):
                        if 'file' in tk_config:
                            config = load_toolkit_config(tk_config['file'])
                            toolkit_configs.append(config)
                        elif 'config' in tk_config:
                            toolkit_configs.append(tk_config['config'])
            
            # Load additional toolkit configs from --toolkit-config options
            if toolkit_config:
                for config_path in toolkit_config:
                    config = load_toolkit_config(config_path)
                    toolkit_configs.append(config)
            
            # Get LLM configuration
            llm_model = model or agent_def.get('model', 'gpt-4o')
            llm_temperature = temperature if temperature is not None else agent_def.get('temperature', 0.7)
            llm_max_tokens = max_tokens or agent_def.get('max_tokens', 2000)
            system_prompt = agent_def.get('system_prompt', '')
            
            # Create LLM instance
            try:
                llm = client.get_llm(
                    model_name=llm_model,
                    model_config={
                        'temperature': llm_temperature,
                        'max_tokens': llm_max_tokens
                    }
                )
            except Exception as e:
                error_panel = Panel(
                    f"Failed to create LLM instance: {e}",
                    title="Error",
                    border_style="red",
                    box=box.ROUNDED
                )
                console.print(error_panel, style="red")
                raise click.Abort()
            
            # Prepare messages
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
                
                # Format and display output
                console.print(f"\n[bold cyan]🤖 Agent: {agent_name}[/bold cyan]\n")
                console.print(f"[bold]Message:[/bold] {message}\n")
                console.print("[bold]Response:[/bold]")
                # Render markdown if the response looks like it contains markdown
                if any(marker in output for marker in ['```', '**', '##', '- ', '* ']):
                    console.print(Markdown(output))
                else:
                    console.print(output)
                console.print()
        
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
            
            # Load additional toolkit configs from --toolkit-config options
            if toolkit_config:
                for config_path in toolkit_config:
                    config = load_toolkit_config(config_path)
                    toolkit_configs.append(config)
            
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
                
                # Format and display output
                console.print(f"\n[bold cyan]🤖 Agent: {agent['name']}[/bold cyan]\n")
                console.print(f"[bold]Message:[/bold] {message}\n")
                console.print("[bold]Response:[/bold]")
                response = result.get('output', 'No response')
                # Render markdown if the response looks like it contains markdown
                if any(marker in response for marker in ['```', '**', '##', '- ', '* ']):
                    console.print(Markdown(response))
                else:
                    console.print(response)
                console.print()
            
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
