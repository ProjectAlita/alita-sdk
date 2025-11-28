"""
Agent UI and display utilities.

Rich console formatting for agent interactions.
"""

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.rule import Rule

console = Console()

# ALITA ASCII Art Logo - block letters
ALITA_LOGO = [
    " █████╗ ██╗     ██╗████████╗ █████╗ ",
    "██╔══██╗██║     ██║╚══██╔══╝██╔══██╗",
    "███████║██║     ██║   ██║   ███████║",
    "██╔══██║██║     ██║   ██║   ██╔══██║",
    "██║  ██║███████╗██║   ██║   ██║  ██║",
    "╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝   ╚═╝  ╚═╝",
]


def get_version():
    """Get CLI version from package."""
    try:
        from importlib.metadata import version
        return version('alita_sdk')
    except Exception:
        return "0.3.x"


def print_banner(agent_name: str, agent_type: str = "Local Agent"):
    """Print a cool banner for the chat session with ASCII art."""
    
    version = get_version()
    
    # Create the main banner content
    banner_text = Text()
    
    # Add logo lines with cyan styling
    for line in ALITA_LOGO:
        banner_text.append("    " + line + "\n", style="bold cyan")
    
    banner_text.append("\n")
    banner_text.append("                    CLI ", style="dim")
    banner_text.append(f"v{version}\n\n", style="bold white")
    
    # Agent info
    banner_text.append("    ● ", style="bold green")
    banner_text.append("Agent: ", style="bold white")
    banner_text.append(f"{agent_name}\n", style="bold cyan")
    banner_text.append("    ● ", style="bold green")
    banner_text.append("Type:  ", style="bold white")
    banner_text.append(f"{agent_type}\n", style="cyan")
    
    console.print()
    console.print(Panel(
        banner_text,
        box=box.DOUBLE,
        border_style="cyan",
        padding=(0, 2),
    ))


def print_help():
    """Print help message with commands using rich table."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        box=box.SIMPLE,
        padding=(0, 1),
    )
    
    table.add_column("Command", style="bold yellow", no_wrap=True, width=12)
    table.add_column("Description", style="white")
    
    table.add_row("/clear", "Clear conversation history")
    table.add_row("/history", "Show conversation history")
    table.add_row("/save", "Save conversation to file")
    table.add_row("/help", "Show this help")
    table.add_row("exit", "End conversation")
    
    console.print(table)
    console.print()


def print_welcome(agent_name: str, agent_type: str = "Local Agent"):
    """Print combined welcome banner with logo, agent info, and help."""
    
    version = get_version()
    
    # Build the complete welcome message using Text objects
    content = Text()
    
    # Add logo lines with cyan styling
    for line in ALITA_LOGO:
        content.append("    " + line + "\n", style="bold cyan")
    
    content.append("                    CLI ", style="dim")
    content.append(f"v{version}\n\n", style="bold white")
    
    # Connection status
    content.append("    ● ", style="bold green")
    content.append("Agent: ", style="bold white")
    content.append(f"{agent_name}\n", style="bold cyan")
    content.append("    ● ", style="bold green")
    content.append("Type:  ", style="bold white")
    content.append(f"{agent_type}\n\n", style="cyan")
    
    # Quick help section
    content.append("    Type a message to chat, or use these commands:\n\n", style="dim")
    
    # Commands
    content.append("    /help", style="bold yellow")
    content.append("    Show all commands\n", style="white")
    content.append("    /clear", style="bold yellow")
    content.append("   Clear history\n", style="white")
    content.append("    exit", style="bold yellow")
    content.append("     End conversation\n", style="white")
    
    console.print()
    console.print(Panel(
        content,
        box=box.DOUBLE,
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()


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
