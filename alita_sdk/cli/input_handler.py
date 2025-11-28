"""
Enhanced input handler with readline support.

Provides tab completion for commands, cursor movement, and input history.
"""

import readline
import os
from typing import List, Optional

from rich.console import Console
from rich.text import Text

console = Console()

# Available commands for autocompletion
CHAT_COMMANDS = [
    '/help',
    '/clear',
    '/history', 
    '/save',
    '/agent',
    '/model',
    '/mode',
    '/mode always',
    '/mode auto',
    '/mode yolo',
    '/dir',
    '/session',
    '/session list',
    '/session resume',
    '/add_mcp',
    '/add_toolkit',
    'exit',
    'quit',
]


class ChatInputHandler:
    """
    Enhanced input handler with readline support for chat sessions.
    
    Features:
    - Tab completion for slash commands
    - Arrow key navigation through input history
    - Cursor movement with left/right arrows
    - Ctrl+A (start of line), Ctrl+E (end of line)
    - Persistent command history within session
    - Material UI-style input prompt
    """
    
    def __init__(self):
        self._setup_readline()
        self._input_history: List[str] = []
    
    def _setup_readline(self):
        """Configure readline for enhanced input."""
        # Set up tab completion
        readline.set_completer(self._completer)
        
        # Detect if we're using libedit (macOS) or GNU readline (Linux)
        # libedit uses different syntax for parse_and_bind
        if 'libedit' in readline.__doc__:
            # macOS libedit syntax
            readline.parse_and_bind('bind ^I rl_complete')
        else:
            # GNU readline syntax
            readline.parse_and_bind('tab: complete')
        
        # Enable emacs-style keybindings (Ctrl+A, Ctrl+E, etc.)
        # This is usually the default on macOS/Linux
        try:
            if 'libedit' not in readline.__doc__:
                readline.parse_and_bind('set editing-mode emacs')
        except Exception:
            pass  # Some systems might not support this
        
        # Set completion display style (GNU readline only)
        try:
            if 'libedit' not in readline.__doc__:
                readline.parse_and_bind('set show-all-if-ambiguous on')
                readline.parse_and_bind('set completion-ignore-case on')
        except Exception:
            pass
        
        # Set delimiters for completion (space and common punctuation)
        readline.set_completer_delims(' \t\n;')
    
    def _completer(self, text: str, state: int) -> Optional[str]:
        """
        Readline completer function for slash commands.
        
        Args:
            text: The current text being completed
            state: The state of completion (0 for first match, 1 for second, etc.)
            
        Returns:
            The next matching command or None
        """
        # Get the full line buffer
        line = readline.get_line_buffer()
        
        # Only complete at the start of the line or after whitespace
        if line and not line.startswith('/') and text != line:
            return None
        
        # Find matching commands
        if text.startswith('/'):
            matches = [cmd for cmd in CHAT_COMMANDS if cmd.startswith(text)]
        elif text == '' and line == '':
            # Show all commands on empty tab
            matches = [cmd for cmd in CHAT_COMMANDS if cmd.startswith('/')]
        else:
            matches = [cmd for cmd in CHAT_COMMANDS if cmd.startswith(text)]
        
        # Return the match at the given state
        if state < len(matches):
            return matches[state]
        return None
    
    def get_input(self, prompt: str = "") -> str:
        """
        Get user input with enhanced readline features.
        
        Args:
            prompt: The prompt to display (note: for rich console, prompt is printed separately)
            
        Returns:
            The user's input string
        """
        try:
            user_input = input(prompt)
            
            # Add non-empty, non-duplicate inputs to history
            if user_input.strip() and (not self._input_history or 
                                        self._input_history[-1] != user_input):
                self._input_history.append(user_input)
                readline.add_history(user_input)
            
            return user_input
        except (KeyboardInterrupt, EOFError):
            raise
    
    def clear_history(self):
        """Clear the input history."""
        self._input_history.clear()
        readline.clear_history()
    
    @property
    def history(self) -> List[str]:
        """Get the current input history."""
        return self._input_history.copy()


# Global instance for use across the CLI
_input_handler: Optional[ChatInputHandler] = None


def get_input_handler() -> ChatInputHandler:
    """Get or create the global input handler instance."""
    global _input_handler
    if _input_handler is None:
        _input_handler = ChatInputHandler()
    return _input_handler


def chat_input(prompt: str = "") -> str:
    """
    Convenience function for getting chat input with enhanced features.
    
    Args:
        prompt: The prompt to display
        
    Returns:
        The user's input string
    """
    return get_input_handler().get_input(prompt)


def styled_input() -> str:
    """
    Get user input with a styled bordered prompt that works correctly with readline.
    
    The prompt is passed directly to input() so readline can properly
    handle cursor positioning and history navigation.
    
    Returns:
        The user's input string
    """
    # Get terminal width for the border
    try:
        width = console.width - 2
    except Exception:
        width = 78
    
    # Print the complete box frame first, then move cursor up to input line
    console.print()
    console.print(f"[dim]╭{'─' * width}╮[/dim]")
    console.print(f"[dim]│[/dim]{' ' * width}[dim]│[/dim]")
    console.print(f"[dim]╰{'─' * width}╯[/dim]")
    
    # Move cursor up 2 lines and to position after "│ > "
    # \033[2A = move up 2 lines, \033[4C = move right 4 columns
    prompt = "\033[2A\033[2C > "
    
    user_input = get_input_handler().get_input(prompt)
    
    # Move cursor down to after the box
    console.print()
    
    return user_input


def styled_selection_input(prompt_text: str = "Select") -> str:
    """
    Get user selection input with a styled bordered prompt.
    
    Args:
        prompt_text: The prompt text to show (e.g., "Select model number")
        
    Returns:
        The user's input string
    """
    # Get terminal width for the border
    try:
        width = console.width - 2
    except Exception:
        width = 78
    
    # Print the complete box frame first, then move cursor up to input line
    console.print()
    console.print(f"[dim]╭{'─' * width}╮[/dim]")
    console.print(f"[dim]│[/dim]{' ' * width}[dim]│[/dim]")
    console.print(f"[dim]╰{'─' * width}╯[/dim]")
    
    # Move cursor up 2 lines and to position after "│"
    # \033[2A = move up 2 lines, \033[2C = move right 2 columns
    prompt = f"\033[2A\033[2C {prompt_text}: "
    
    try:
        user_input = input(prompt)
    except (KeyboardInterrupt, EOFError):
        console.print()
        raise
    
    # Move cursor down to after the box
    console.print()
    
    return user_input.strip()


def print_input_prompt():
    """Print a clean, modern input prompt."""
    # Simple clean prompt with > indicator
    console.print()  # Empty line for spacing
    console.print("[bold cyan]>[/bold cyan] ", end="")
