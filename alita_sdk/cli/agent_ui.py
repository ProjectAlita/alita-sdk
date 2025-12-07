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
    
    table.add_column("Command", style="bold yellow", no_wrap=True, width=16)
    table.add_column("Description", style="white")
    
    table.add_row("/clear", "Clear conversation history")
    table.add_row("/history", "Show conversation history")
    table.add_row("/save", "Save conversation to file")
    table.add_row("/agent", "Switch to a different agent or direct chat")
    table.add_row("/model", "Switch to a different model (preserves history)")
    table.add_row("/reload", "Reload agent from file (hot reload)")
    table.add_row("/mode", "Set approval mode: always, auto, yolo")
    table.add_row("/dir [add|rm] <path>", "Add/remove/list allowed directories")
    table.add_row("/inventory <path>", "Load inventory/knowledge graph from JSON file")
    table.add_row("/session", "List or resume previous sessions with plans")
    table.add_row("/add_mcp", "Add an MCP server (preserves history)")
    table.add_row("/add_toolkit", "Add a toolkit (preserves history)")
    table.add_row("/rm_mcp", "Remove an MCP server")
    table.add_row("/rm_toolkit", "Remove a toolkit")
    table.add_row("/help", "Show this help")
    table.add_row("exit", "End conversation")
    
    console.print(table)
    console.print()


def print_welcome(agent_name: str, model: str = "gpt-4o", temperature: float = 0.1, mode: str = "always"):
    """Print combined welcome banner with logo, agent info, and help in two columns."""
    
    version = get_version()
    
    # Mode display with color
    mode_colors = {'always': 'yellow', 'auto': 'green', 'yolo': 'red'}
    mode_color = mode_colors.get(mode, 'white')
    
    # Left column: Logo + version + agent info
    left_content = Text()
    for line in ALITA_LOGO:
        left_content.append(line + "\n", style="bold cyan")
    left_content.append("        CLI ", style="dim")
    left_content.append(f"v{version}\n\n", style="bold white")
    left_content.append("● ", style="bold green")
    left_content.append("Agent: ", style="bold white")
    left_content.append(f"{agent_name}\n", style="bold cyan")
    left_content.append("● ", style="bold green")
    left_content.append("Model: ", style="bold white")
    left_content.append(f"{model}", style="cyan")
    left_content.append(" | ", style="dim")
    left_content.append("Temp: ", style="bold white")
    left_content.append(f"{temperature}\n", style="cyan")
    left_content.append("● ", style="bold green")
    left_content.append("Mode:  ", style="bold white")
    left_content.append(f"{mode}\n", style=f"bold {mode_color}")
    
    # Right column: Commands
    right_content = Text()
    right_content.append("\n")  # Align with logo
    right_content.append("/help", style="bold yellow")
    right_content.append("        Show all commands\n", style="dim")
    right_content.append("/agent", style="bold yellow")
    right_content.append("       Switch agent\n", style="dim")
    right_content.append("/model", style="bold yellow")
    right_content.append("       Switch model\n", style="dim")
    right_content.append("/reload", style="bold yellow")
    right_content.append("      Reload agent file\n", style="dim")
    right_content.append("/mode", style="bold yellow")
    right_content.append("        Set approval mode\n", style="dim")
    right_content.append("/dir", style="bold yellow")
    right_content.append("         Add/list directories\n", style="dim")
    right_content.append("/session", style="bold yellow")
    right_content.append("     List/resume sessions\n", style="dim")
    right_content.append("/inventory", style="bold yellow")
    right_content.append("   Load knowledge graph\n", style="dim")
    right_content.append("/add_mcp", style="bold yellow")
    right_content.append("     Add MCP server\n", style="dim")
    right_content.append("/add_toolkit", style="bold yellow")
    right_content.append(" Add toolkit\n", style="dim")
    right_content.append("exit", style="bold yellow")
    right_content.append("         End conversation\n", style="dim")
    
    # Create two-column layout
    columns = Columns([left_content, right_content], padding=(0, 4), expand=False)
    
    console.print()
    console.print(Panel(
        columns,
        box=box.DOUBLE,
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


def render_plan(plan_state) -> None:
    """Render a plan with checkboxes."""
    if not plan_state or not plan_state.steps:
        return
    
    console.print(plan_state.render())
    console.print()


def render_approval_prompt(tool_name: str, tool_args: dict, truncate: int = 60) -> str:
    """
    Render an approval prompt for a tool call.
    
    Returns the formatted string for display in the input box.
    """
    # Format args as a compact string
    args_str = ", ".join(f"{k}={repr(v)[:truncate]}" for k, v in tool_args.items())
    if len(args_str) > 80:
        args_str = args_str[:77] + "..."
    
    return f"🔧 {tool_name}: {args_str}"


def display_output(agent_name: str, message: str, output: str):
    """Display agent output with markdown rendering if applicable."""
    console.print(f"\n[bold cyan]🤖 Agent: {agent_name}[/bold cyan]\n")
    console.print(f"[bold]Message:[/bold] {message}\n")
    console.print("[bold]Response:[/bold]")
    
    # Ensure output is a string
    if not isinstance(output, str):
        output = str(output)
    
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
