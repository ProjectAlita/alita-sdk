"""
Agent UI and display utilities.

Rich console formatting for agent interactions.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from rich.text import Text

console = Console()


def print_banner(agent_name: str, agent_type: str = "local"):
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


def print_help():
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


def display_output(agent_name: str, message: str, output: str):
    """Display agent output with markdown rendering if applicable."""
    console.print(f"\n[bold cyan]🤖 Agent: {agent_name}[/bold cyan]\n")
    console.print(f"[bold]Message:[/bold] {message}\n")
    console.print("[bold]Response:[/bold]")
    if any(marker in output for marker in ['```', '**', '##', '- ', '* ']):
        console.print(Markdown(output))
    else:
        console.print(output)
    console.print()


def extract_output_from_result(result) -> str:
    """Extract output string from agent result (handles multiple formats)."""
    if isinstance(result, dict):
        # Try different keys that might contain the response
        output = result.get('output')
        if output is None and 'messages' in result:
            # LangGraph format - get last message
            messages = result['messages']
            if messages and len(messages) > 0:
                last_msg = messages[-1]
                output = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        if output is None:
            output = str(result)
    else:
        output = str(result)
    return output
