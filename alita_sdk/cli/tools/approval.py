"""
Tool approval wrapper for CLI.

Wraps tools to require user approval before execution based on approval mode.
Modes:
- 'always': Always require approval for each tool call
- 'auto': No approval required (automatic execution)
- 'yolo': No approval and no safety checks (use with caution)
"""

import functools
from typing import Any, Callable, Dict, List, Optional, Set
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text
import json

from langchain_core.tools import BaseTool, StructuredTool, Tool

console = Console()

# Tools that always require approval in 'always' mode (dangerous built-in operations)
# These are the built-in CLI tools that modify the filesystem or execute commands
DANGEROUS_TOOLS = {
    'terminal_run_command',  # Shell command execution
    'write_file',
    'create_file', 
    'delete_file',
    'move_file',
    'copy_file',
    'create_directory',
}

# Note: Tools NOT in DANGEROUS_TOOLS are auto-approved, including:
# - Read-only filesystem tools (read_file, list_directory, etc.)
# - User-added toolkit tools (via --toolkit_config or /add_toolkit)
# - MCP server tools (via --mcp or /add_mcp)
# 
# The assumption is that users explicitly add toolkits they trust.
# Only built-in tools that can modify files or run commands require approval.


def prompt_approval(tool_name: str, tool_args: Dict[str, Any], approval_mode: str) -> bool:
    """
    Prompt user for approval before executing a tool.
    
    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool
        approval_mode: Current approval mode ('always', 'auto', 'yolo')
        
    Returns:
        True if approved, False if rejected
    """
    # Auto mode - always approve
    if approval_mode == 'auto':
        return True
    
    # Yolo mode - always approve, no questions asked
    if approval_mode == 'yolo':
        return True
    
    # Always mode - only prompt for dangerous built-in tools
    # User-added toolkits and MCP tools are auto-approved (user explicitly added them)
    if tool_name not in DANGEROUS_TOOLS:
        return True
    
    # Create approval prompt panel for dangerous tools
    console.print()
    
    # Build args display
    args_content = []
    for key, value in tool_args.items():
        if isinstance(value, str) and len(value) > 100:
            display_value = value[:100] + "..."
        elif isinstance(value, (dict, list)):
            try:
                formatted = json.dumps(value, indent=2)
                if len(formatted) > 200:
                    formatted = formatted[:200] + "..."
                display_value = formatted
            except:
                display_value = str(value)[:100]
        else:
            display_value = str(value)
        args_content.append(f"  [cyan]{key}[/cyan]: {display_value}")
    
    args_text = "\n".join(args_content) if args_content else "  (no arguments)"
    
    # All tools reaching here are dangerous (in DANGEROUS_TOOLS)
    icon = "⚠️"
    border_style = "yellow"
    title_style = "bold yellow"
    
    panel = Panel(
        Text.from_markup(f"[bold]{tool_name}[/bold]\n\n[dim]Arguments:[/dim]\n{args_text}"),
        title=f"[{title_style}]{icon} Approve Tool Call?[/{title_style}]",
        title_align="left",
        subtitle="[dim][y]es / [n]o / [a]uto-approve / [q]uit[/dim]",
        subtitle_align="right",
        border_style=border_style,
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)
    
    # Get user input
    while True:
        try:
            response = input("→ ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled[/yellow]")
            return False
        
        if response in ('y', 'yes', ''):
            console.print("[green]✓ Approved[/green]")
            return True
        elif response in ('n', 'no'):
            console.print("[red]✗ Rejected[/red]")
            return False
        elif response in ('a', 'auto'):
            console.print("[cyan]→ Switching to auto mode for this session[/cyan]")
            # Signal to switch to auto mode
            return 'switch_auto'
        elif response in ('q', 'quit'):
            console.print("[yellow]Quitting...[/yellow]")
            raise KeyboardInterrupt()
        else:
            console.print("[dim]Please enter y/n/a/q[/dim]")


class ApprovalToolWrapper:
    """
    Wrapper that adds approval prompts to tools based on approval mode.
    
    This wrapper intercepts tool calls and prompts for user approval
    before executing dangerous operations.
    """
    
    def __init__(self, approval_mode_ref: List[str]):
        """
        Initialize the approval wrapper.
        
        Args:
            approval_mode_ref: A mutable list containing the current approval mode.
                              Using a list allows the mode to be changed externally.
                              access as approval_mode_ref[0]
        """
        self.approval_mode_ref = approval_mode_ref
    
    @property
    def approval_mode(self) -> str:
        """Get current approval mode."""
        return self.approval_mode_ref[0] if self.approval_mode_ref else 'always'
    
    def wrap_tool(self, tool: BaseTool) -> BaseTool:
        """
        Wrap a tool to add approval prompts.
        
        Args:
            tool: The tool to wrap
            
        Returns:
            Wrapped tool with approval logic
        """
        original_func = tool.func if hasattr(tool, 'func') else tool._run
        tool_name = tool.name
        wrapper_self = self
        
        @functools.wraps(original_func)
        def wrapped_func(*args, **kwargs):
            # Get approval
            approval = prompt_approval(tool_name, kwargs, wrapper_self.approval_mode)
            
            if approval == 'switch_auto':
                # Switch to auto mode
                wrapper_self.approval_mode_ref[0] = 'auto'
                console.print("[cyan]Mode switched to 'auto' - tools will auto-approve[/cyan]")
            elif not approval:
                return f"Tool execution rejected by user"
            
            # Execute the tool
            return original_func(*args, **kwargs)
        
        # Create new tool with wrapped function
        if isinstance(tool, StructuredTool):
            return StructuredTool(
                name=tool.name,
                description=tool.description,
                func=wrapped_func,
                args_schema=tool.args_schema,
                return_direct=tool.return_direct,
            )
        else:
            # Clone the tool with wrapped function
            tool.func = wrapped_func
            return tool
    
    def wrap_tools(self, tools: List[BaseTool]) -> List[BaseTool]:
        """
        Wrap multiple tools with approval logic.
        
        Args:
            tools: List of tools to wrap
            
        Returns:
            List of wrapped tools
        """
        return [self.wrap_tool(tool) for tool in tools]


def create_approval_wrapper(approval_mode_ref: List[str]) -> ApprovalToolWrapper:
    """
    Create an approval wrapper with a reference to the current mode.
    
    Args:
        approval_mode_ref: Mutable list containing current approval mode [0]
        
    Returns:
        ApprovalToolWrapper instance
    """
    return ApprovalToolWrapper(approval_mode_ref)
