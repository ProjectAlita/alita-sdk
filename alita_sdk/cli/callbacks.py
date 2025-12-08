"""
CLI Callback Handler for Alita CLI.

Provides rich console output for tool calls, LLM thinking, and agent steps
during agent execution in the CLI with beautifully styled blocks.
"""

import logging
import json
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import Any, Dict, List, Optional, Sequence
from collections import defaultdict

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import ChatGenerationChunk, LLMResult
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage

from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich.tree import Tree
from rich import box
from rich.markdown import Markdown
from rich.rule import Rule
from rich.padding import Padding

logger = logging.getLogger(__name__)

# Create a rich console for beautiful output
console = Console()

# Custom box styles for different block types
TOOL_BOX = box.ROUNDED
OUTPUT_BOX = box.ROUNDED
ERROR_BOX = box.HEAVY


class CLICallbackHandler(BaseCallbackHandler):
    """
    CLI Callback handler that displays tool calls, LLM responses, and agent steps
    with rich formatting using beautifully styled blocks.
    """
    
    def __init__(self, verbose: bool = True, show_tool_outputs: bool = True,
                 show_thinking: bool = True, show_llm_calls: bool = False):
        """
        Initialize the CLI callback handler.
        
        Args:
            verbose: Show detailed output for all operations
            show_tool_outputs: Show tool call inputs and outputs
            show_thinking: Show LLM thinking/reasoning process
            show_llm_calls: Show LLM call start/end (can be noisy)
        """
        super().__init__()
        self.verbose = verbose
        self.show_tool_outputs = show_tool_outputs
        self.show_thinking = show_thinking
        self.show_llm_calls = show_llm_calls
        
        # Track state
        self.tool_runs: Dict[str, Dict[str, Any]] = {}
        self.llm_runs: Dict[str, Dict[str, Any]] = {}
        self.pending_tokens: Dict[str, List[str]] = defaultdict(list)
        self.current_model: str = ""
        self.step_counter: int = 0
        
        # External status spinner that can be stopped
        self.status = None
    
    def _stop_status(self):
        """Stop the external status spinner if set."""
        if self.status is not None:
            try:
                self.status.stop()
                self.status = None
            except Exception:
                pass
    
    def _format_json_content(self, data: Any, max_length: int = 1500) -> str:
        """Format data as pretty JSON string."""
        try:
            if isinstance(data, str):
                # Try to parse if it looks like JSON
                if data.strip().startswith(('{', '[')):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        return data[:max_length] + ('...' if len(data) > max_length else '')
            
            formatted = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            if len(formatted) > max_length:
                formatted = formatted[:max_length] + f"\n... (truncated)"
            return formatted
        except Exception:
            return str(data)[:max_length]
    
    def _format_tool_output_content(self, output: Any) -> Any:
        """Format tool output for display in panel."""
        if output is None:
            return Text("(no output)", style="dim italic")
        
        try:
            output_str = str(output)
            max_length = 2000
            
            # Check if it's JSON-like
            if output_str.strip().startswith(('{', '[')):
                try:
                    parsed = json.loads(output_str)
                    formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
                    if len(formatted) > max_length:
                        formatted = formatted[:max_length] + f"\n... (truncated, {len(output_str)} chars total)"
                    return Syntax(formatted, "json", theme="monokai", word_wrap=True, line_numbers=False)
                except json.JSONDecodeError:
                    pass
            
            # Truncate if needed
            if len(output_str) > max_length:
                output_str = output_str[:max_length] + f"\n... (truncated, {len(str(output))} chars total)"
            
            # Check for markdown-like content
            if any(marker in output_str for marker in ['```', '**', '##', '- ', '* ', '\n\n']):
                return Markdown(output_str)
            
            return Text(output_str, style="white")
            
        except Exception:
            return Text(str(output)[:500], style="white")
    
    #
    # Tool Callbacks
    #
    
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool starts running."""
        # Stop the thinking spinner when a tool starts
        self._stop_status()
        
        if not self.show_tool_outputs:
            return
        
        tool_name = serialized.get("name", "Unknown Tool")
        tool_run_id = str(run_id)
        self.step_counter += 1
        
        # Store tool run info
        self.tool_runs[tool_run_id] = {
            "name": tool_name,
            "start_time": datetime.now(tz=timezone.utc),
            "inputs": inputs or input_str,
            "step": self.step_counter,
        }
        
        # Format inputs
        tool_inputs = inputs if inputs else input_str
        
        # Create the tool call panel
        console.print()
        
        # Build content for the panel
        content_parts = []
        
        if tool_inputs:
            if isinstance(tool_inputs, dict):
                formatted_input = self._format_json_content(tool_inputs, max_length=1200)
                input_syntax = Syntax(formatted_input, "json", theme="monokai", 
                                      word_wrap=True, line_numbers=False)
                content_parts.append(input_syntax)
            elif isinstance(tool_inputs, str) and len(tool_inputs) > 0:
                display_input = tool_inputs[:800] + "..." if len(tool_inputs) > 800 else tool_inputs
                content_parts.append(Text(display_input, style="white"))
        
        if content_parts:
            panel_content = Group(*content_parts)
        else:
            panel_content = Text("(no input)", style="dim italic")
        
        # Create styled panel
        panel = Panel(
            panel_content,
            title=f"[bold yellow]🔧 Tool Call[/bold yellow] [dim]│[/dim] [bold cyan]{tool_name}[/bold cyan]",
            title_align="left",
            subtitle=f"[dim]Step {self.step_counter}[/dim]",
            subtitle_align="right",
            border_style="yellow",
            box=TOOL_BOX,
            padding=(0, 1),
        )
        console.print(panel)
    
    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool finishes running."""
        if not self.show_tool_outputs:
            return
        
        tool_run_id = str(run_id)
        tool_info = self.tool_runs.pop(tool_run_id, {})
        tool_name = tool_info.get("name", kwargs.get("name", "Unknown"))
        step_num = tool_info.get("step", "?")
        
        # Calculate duration
        start_time = tool_info.get("start_time")
        duration_str = ""
        if start_time:
            elapsed = (datetime.now(tz=timezone.utc) - start_time).total_seconds()
            duration_str = f" │ {elapsed:.2f}s"
        
        # Format output
        output_content = self._format_tool_output_content(output)
        
        # Create result panel
        panel = Panel(
            output_content,
            title=f"[bold green]✓ Result[/bold green] [dim]│[/dim] [dim]{tool_name}[/dim]",
            title_align="left",
            subtitle=f"[dim]Step {step_num}{duration_str}[/dim]",
            subtitle_align="right",
            border_style="green",
            box=OUTPUT_BOX,
            padding=(0, 1),
        )
        console.print(panel)
        console.print()
    
    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool errors."""
        tool_run_id = str(run_id)
        tool_info = self.tool_runs.pop(tool_run_id, {})
        tool_name = tool_info.get("name", kwargs.get("name", "Unknown"))
        step_num = tool_info.get("step", "?")
        
        # Calculate duration
        start_time = tool_info.get("start_time")
        duration_str = ""
        if start_time:
            elapsed = (datetime.now(tz=timezone.utc) - start_time).total_seconds()
            duration_str = f" │ {elapsed:.2f}s"
        
        # Build error content with exception details
        content_parts = []
        
        # Error message
        error_msg = str(error)
        content_parts.append(Text(error_msg, style="red bold"))
        
        # Add traceback if available
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        if tb_str and tb_str.strip():
            content_parts.append(Text(""))  # blank line
            content_parts.append(Text("Exception Traceback:", style="dim bold"))
            # Truncate if too long
            max_tb_len = 1500
            if len(tb_str) > max_tb_len:
                tb_str = tb_str[:max_tb_len] + f"\n... (truncated, {len(tb_str)} chars total)"
            content_parts.append(Syntax(tb_str, "python", theme="monokai", 
                                        word_wrap=True, line_numbers=False))
        
        panel_content = Group(*content_parts) if len(content_parts) > 1 else content_parts[0]
        
        panel = Panel(
            panel_content,
            title=f"[bold red]✗ Error[/bold red] [dim]│[/dim] [bold]{tool_name}[/bold]",
            title_align="left",
            subtitle=f"[dim]Step {step_num}{duration_str}[/dim]",
            subtitle_align="right",
            border_style="red",
            box=ERROR_BOX,
            padding=(0, 1),
        )
        console.print()
        console.print(panel)
        console.print()
    
    #
    # LLM Callbacks
    #
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts generating."""
        if not self.show_llm_calls:
            return
        
        llm_run_id = str(run_id)
        model_name = metadata.get("ls_model_name", "") if metadata else ""
        self.current_model = model_name
        
        self.llm_runs[llm_run_id] = {
            "model": model_name,
            "start_time": datetime.now(tz=timezone.utc),
        }
        
        # Display thinking indicator
        console.print()
        console.print(Panel(
            Text("Processing...", style="italic"),
            title=f"[bold blue]🤔 LLM[/bold blue] [dim]│[/dim] [dim]{model_name or 'model'}[/dim]",
            title_align="left",
            border_style="blue",
            box=box.SIMPLE,
            padding=(0, 1),
        ))
    
    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chat model starts."""
        if not self.show_llm_calls:
            return
        
        llm_run_id = str(run_id)
        model_name = metadata.get("ls_model_name", "") if metadata else ""
        self.current_model = model_name
        
        self.llm_runs[llm_run_id] = {
            "model": model_name,
            "start_time": datetime.now(tz=timezone.utc),
        }
        
        # Display thinking indicator
        console.print()
        console.print(Panel(
            Text("Processing...", style="italic"),
            title=f"[bold blue]🤔 LLM[/bold blue] [dim]│[/dim] [dim]{model_name or 'model'}[/dim]",
            title_align="left",
            border_style="blue",
            box=box.SIMPLE,
            padding=(0, 1),
        ))
    
    def on_llm_new_token(
        self,
        token: str,
        *,
        chunk: Optional[ChatGenerationChunk] = None,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called on each new LLM token."""
        # Stream tokens if showing thinking process
        if self.show_thinking and token:
            self.pending_tokens[str(run_id)].append(token)
    
    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM finishes."""
        llm_run_id = str(run_id)
        llm_info = self.llm_runs.pop(llm_run_id, {})
        
        # Clear pending tokens - we don't show them as "Thinking" anymore
        # The final response will be displayed by the main chat loop
        # Only show thinking if there were tool calls (indicated by having active tool runs)
        tokens = self.pending_tokens.pop(llm_run_id, [])
        
        # Only show thinking panel if we have active tool context (intermediate reasoning)
        if self.show_thinking and tokens and len(self.tool_runs) > 0:
            thinking_text = "".join(tokens)
            if thinking_text.strip():
                # Show thinking in a subtle panel
                max_len = 600
                display_text = thinking_text[:max_len] + ('...' if len(thinking_text) > max_len else '')
                console.print(Panel(
                    Text(display_text, style="dim italic"),
                    title="[dim]💭 Thinking[/dim]",
                    title_align="left",
                    border_style="dim",
                    box=box.SIMPLE,
                    padding=(0, 1),
                ))
        
        if self.show_llm_calls and llm_info:
            start_time = llm_info.get("start_time")
            model = llm_info.get("model", "model")
            if start_time:
                elapsed = (datetime.now(tz=timezone.utc) - start_time).total_seconds()
                console.print(f"[dim]✓ LLM complete ({model}, {elapsed:.2f}s)[/dim]")
    
    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM errors."""
        error_str = str(error)
        
        # Parse common error patterns for user-friendly messages
        user_message = None
        hint = None
        
        # Invalid model identifier (Bedrock/Claude)
        if "model identifier is invalid" in error_str.lower() or "BedrockException" in error_str:
            user_message = "Invalid model identifier"
            hint = "The model may not be available in your region or the model ID is incorrect.\nUse /model to switch to a different model."
        
        # Rate limiting
        elif "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
            user_message = "Rate limit exceeded"
            hint = "Wait a moment and try again, or switch to a different model with /model."
        
        # Token/context length exceeded
        elif "context length" in error_str.lower() or "maximum.*tokens" in error_str.lower() or "too long" in error_str.lower():
            user_message = "Context length exceeded"
            hint = "The conversation is too long. Start a new session or use /clear to reset."
        
        # Authentication errors
        elif "authentication" in error_str.lower() or "unauthorized" in error_str.lower() or "api key" in error_str.lower():
            user_message = "Authentication failed"
            hint = "Check your API credentials in the configuration."
        
        # Model not found/available
        elif "model not found" in error_str.lower() or "does not exist" in error_str.lower():
            user_message = "Model not found"
            hint = "The requested model is not available. Use /model to select a different one."
        
        # Build the display message
        console.print()
        if user_message:
            content = Text()
            content.append(f"❌ {user_message}\n\n", style="bold red")
            if hint:
                content.append(f"💡 {hint}\n\n", style="yellow")
            content.append("Technical details:\n", style="dim")
            # Truncate long error messages
            if len(error_str) > 300:
                content.append(error_str[:300] + "...", style="dim")
            else:
                content.append(error_str, style="dim")
            console.print(Panel(
                content,
                title="[bold red]✗ LLM Error[/bold red]",
                title_align="left",
                border_style="red",
                box=ERROR_BOX,
                padding=(0, 1),
            ))
        else:
            # Fallback to original behavior for unrecognized errors
            console.print(Panel(
                Text(str(error), style="red"),
                title="[bold red]✗ LLM Error[/bold red]",
                title_align="left",
                border_style="red",
                box=ERROR_BOX,
                padding=(0, 1),
            ))
    
    #
    # Chain Callbacks
    #
    
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain starts."""
        pass  # Can be noisy, skip by default
    
    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain ends."""
        pass  # Can be noisy, skip by default
    
    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain errors."""
        if self.verbose:
            console.print()
            console.print(Panel(
                Text(str(error), style="red"),
                title="[bold red]✗ Chain Error[/bold red]",
                title_align="left",
                border_style="red",
                box=ERROR_BOX,
                padding=(0, 1),
            ))
    
    #
    # Agent Callbacks
    #
    
    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent takes an action."""
        # This is handled by on_tool_start, so we skip to avoid duplicates
        pass
    
    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent finishes."""
        if self.verbose and self.show_llm_calls:
            console.print(Rule("Agent Complete", style="dim"))
    
    #
    # Custom Events (LangGraph)
    #
    
    def on_custom_event(
        self,
        name: str,
        data: Any,
        *,
        run_id: UUID,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Handle custom events from LangGraph."""
        if not self.verbose:
            return
        
        if name == "on_conditional_edge":
            # Show decision making in debug mode
            if self.show_llm_calls:
                condition = data.get('condition', '')
                if condition:
                    console.print(f"[dim]📍 Conditional: {condition[:100]}[/dim]")
        
        elif name == "on_transitional_edge":
            # Show transitions in debug mode
            if self.show_llm_calls:
                next_step = data.get("next_step", "")
                if next_step and next_step != "__end__":
                    console.print(f"[dim]→ Transition: {next_step}[/dim]")
    
    #
    # Utility Methods
    #
    
    def reset_step_counter(self) -> None:
        """Reset the step counter for a new conversation."""
        self.step_counter = 0


def create_cli_callback(verbose: bool = True, debug: bool = False) -> CLICallbackHandler:
    """
    Create a CLI callback handler with appropriate settings.
    
    Args:
        verbose: Enable verbose output (tool calls and outputs)
        debug: Enable debug output (includes LLM calls and detailed info)
        
    Returns:
        CLICallbackHandler instance configured for the verbosity level
    """
    return CLICallbackHandler(
        verbose=verbose,
        show_tool_outputs=verbose,
        show_thinking=verbose,
        show_llm_calls=debug  # Only show LLM calls in debug mode
    )
