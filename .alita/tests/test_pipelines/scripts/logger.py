"""
Unified logging module for test pipeline framework.

Provides consistent logging across all test pipeline scripts with:
- Colored output (when TTY detected)
- Smart truncation for long messages
- Verbose/quiet mode support
- JSON-safe output routing (verbose to stderr in quiet mode)
"""

import os
import sys
from typing import Optional, TextIO


class TestLogger:
    """
    Unified logger for test pipeline framework.
    
    Handles output routing, formatting, and truncation consistently across
    all scripts (run_pipeline, run_suite, seed_pipelines, setup, cleanup).
    
    Args:
        verbose: Enable verbose debug output
        quiet: Suppress non-essential output (for JSON mode)
        use_colors: Force color output on/off. If None, auto-detect TTY.
        max_truncate_length: Maximum message length before truncation (default: 500)
        
    Output routing:
        - quiet=False (normal mode): All output to stdout
        - quiet=True (JSON mode): Essential output to stdout, verbose to stderr
        - Error messages: Always to stderr
    """
    
    # ANSI color codes
    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'dim': '\033[2m',
        'red': '\033[31m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'magenta': '\033[35m',
        'cyan': '\033[36m',
        'gray': '\033[90m',
    }
    
    def __init__(
        self,
        verbose: bool = False,
        quiet: bool = False,
        use_colors: Optional[bool] = None,
        max_truncate_length: int = 500
    ):
        # Auto-detect CI environment for verbose mode
        ci_detected = self._is_ci_environment()
        self.verbose = verbose or ci_detected or os.getenv('TEST_VERBOSE', '').lower() in ('1', 'true', 'yes')
        self.quiet = quiet
        self.max_truncate_length = max_truncate_length
        
        # Auto-detect TTY if not specified, with FORCE_COLOR override
        if use_colors is None:
            # Check for FORCE_COLOR environment variable (supports NO_COLOR convention too)
            force_color = os.getenv('FORCE_COLOR', '').lower() in ('1', 'true', 'yes')
            no_color = os.getenv('NO_COLOR', '') != ''
            
            if no_color:
                self.use_colors = False
            elif force_color:
                self.use_colors = True
            else:
                self.use_colors = sys.stdout.isatty() and sys.stderr.isatty()
        else:
            self.use_colors = use_colors
    
    @staticmethod
    def _is_ci_environment() -> bool:
        """Detect if running in a CI environment."""
        ci_indicators = [
            'CI',                # Generic CI indicator
            'CONTINUOUS_INTEGRATION',
            'GITHUB_ACTIONS',    # GitHub Actions
            'GITLAB_CI',         # GitLab CI
            'JENKINS_HOME',      # Jenkins
            'CIRCLECI',          # CircleCI
            'TRAVIS',            # Travis CI
            'BUILDKITE',         # Buildkite
            'DRONE',             # Drone CI
            'TEAMCITY_VERSION',  # TeamCity
        ]
        return any(os.getenv(var) for var in ci_indicators)
    
    def _colorize(self, text: str, color: str) -> str:
        """Apply ANSI color codes if colors are enabled."""
        if not self.use_colors:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"
    
    def _truncate(self, message: str, max_length: Optional[int] = None) -> str:
        """
        Truncate long messages with ellipsis and length indicator.
        
        Args:
            message: Message to potentially truncate
            max_length: Maximum length. If None, uses self.max_truncate_length
            
        Returns:
            Original or truncated message with length indicator
        """
        max_len = max_length or self.max_truncate_length
        if len(message) <= max_len:
            return message
        
        truncated = message[:max_len]
        return f"{truncated}... [truncated, total length: {len(message)} chars]"
    
    def _write(
        self,
        message: str,
        stream: Optional[TextIO] = None,
        end: str = '\n'
    ):
        """
        Write message to appropriate stream.
        
        Args:
            message: Message to write
            stream: Target stream. If None, auto-select based on quiet mode.
            end: Line ending (default: newline)
        """
        if stream is None:
            stream = sys.stdout
        
        stream.write(message + end)
        stream.flush()
    
    def debug(self, message: str, truncate: bool = True):
        """
        Log debug message (only shown in verbose mode).
        
        In quiet mode, routes to stderr to avoid corrupting JSON output.
        
        Args:
            message: Debug message
            truncate: Apply smart truncation (default: True)
        """
        if not self.verbose:
            return
        
        if truncate:
            message = self._truncate(message)
        
        formatted = self._colorize(f"[DEBUG] {message}", 'gray')
        
        # Route verbose output to stderr in quiet mode (JSON mode)
        stream = sys.stderr if self.quiet else sys.stdout
        self._write(formatted, stream)
    
    def info(self, message: str, truncate: bool = False):
        """
        Log informational message.
        
        Args:
            message: Info message
            truncate: Apply smart truncation (default: False)
        """
        if self.quiet:
            return
        
        if truncate:
            message = self._truncate(message)
        
        formatted = self._colorize(f"[INFO] {message}", 'blue')
        self._write(formatted, sys.stdout)
    
    def success(self, message: str, truncate: bool = False):
        """
        Log success message.
        
        Args:
            message: Success message
            truncate: Apply smart truncation (default: False)
        """
        if self.quiet:
            return
        
        if truncate:
            message = self._truncate(message)
        
        formatted = self._colorize(f"[SUCCESS] {message}", 'green')
        self._write(formatted, sys.stdout)
    
    def warning(self, message: str, truncate: bool = True):
        """
        Log warning message.
        
        Args:
            message: Warning message
            truncate: Apply smart truncation (default: True)
        """
        if self.quiet:
            return
        
        if truncate:
            message = self._truncate(message)
        
        formatted = self._colorize(f"[WARNING] {message}", 'yellow')
        self._write(formatted, sys.stderr)
    
    def error(self, message: str, truncate: bool = True):
        """
        Log error message (always shown, routes to stderr).
        
        Args:
            message: Error message
            truncate: Apply smart truncation (default: True)
        """
        if truncate:
            message = self._truncate(message)
        
        formatted = self._colorize(f"[ERROR] {message}", 'red')
        self._write(formatted, sys.stderr)
    
    def raw(self, message: str, to_stderr: bool = False):
        """
        Output raw message without formatting or prefixes.
        
        Useful for JSON output or passing through external command output.
        
        Args:
            message: Raw message
            to_stderr: Force output to stderr (default: False)
        """
        stream = sys.stderr if to_stderr else sys.stdout
        self._write(message, stream, end='')
    
    def separator(self, char: str = '-', length: int = 60):
        """
        Print a separator line.
        
        Args:
            char: Character to use for separator
            length: Length of separator line
        """
        if self.quiet:
            return
        
        line = char * length
        self._write(self._colorize(line, 'dim'), sys.stdout)
    
    def section(self, title: str):
        """
        Print a section header.
        
        Args:
            title: Section title
        """
        if self.quiet:
            return
        
        formatted = self._colorize(f"\n{'=' * 60}\n{title}\n{'=' * 60}", 'bold')
        self._write(formatted, sys.stdout)
    
    def http_error(
        self,
        status_code: int,
        response_text: str,
        context: str = "",
        max_response_length: int = 500
    ):
        """
        Format and log HTTP error response.
        
        Args:
            status_code: HTTP status code
            response_text: Response body text
            context: Additional context (e.g., "seeding composable pipeline X")
            max_response_length: Maximum response text length before truncation
        """
        truncated_response = self._truncate(response_text, max_response_length)
        
        if context:
            message = f"HTTP {status_code} Error ({context}):\n{truncated_response}"
        else:
            message = f"HTTP {status_code} Error:\n{truncated_response}"
        
        self.error(message, truncate=False)
    
    def progress(self, message: str, current: int, total: int):
        """
        Log progress message with counter.
        
        Args:
            message: Progress message
            current: Current item number
            total: Total item count
        """
        if self.quiet:
            return
        
        formatted = self._colorize(f"[{current}/{total}] {message}", 'cyan')
        self._write(formatted, sys.stdout)


# Convenience function for creating logger instances
def create_logger(
    verbose: bool = False,
    quiet: bool = False,
    use_colors: Optional[bool] = None
) -> TestLogger:
    """
    Create a TestLogger instance with standard configuration.
    
    Args:
        verbose: Enable verbose debug output
        quiet: Suppress non-essential output (for JSON mode)
        use_colors: Force color output on/off. If None, auto-detect TTY.
        
    Returns:
        Configured TestLogger instance
    """
    return TestLogger(verbose=verbose, quiet=quiet, use_colors=use_colors)
