"""
Terminal command execution tools for CLI agents.

Provides secure shell command execution restricted to mounted directories
with blocked command patterns and path traversal protection.
"""

import os
import re
import subprocess
import shlex
from pathlib import Path
from typing import Optional, List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


# Default blocked command patterns (security)
DEFAULT_BLOCKED_PATTERNS = [
    # Destructive commands
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\*",
    r"rm\s+-rf\s+\.\.",
    r"sudo\s+rm",
    r"mkfs",
    r"dd\s+if=",
    r":\(\)\{\s*:\|:&\s*\};:",  # Fork bomb
    
    # Privilege escalation
    r"sudo\s+su",
    r"sudo\s+-i",
    r"sudo\s+-s",
    r"chmod\s+777",
    r"chmod\s+-R\s+777",
    r"chown\s+root",
    
    # Data exfiltration
    r"curl.*\|.*sh",
    r"wget.*\|.*sh",
    r"curl.*\|.*bash",
    r"wget.*\|.*bash",
    r"nc\s+-e",
    r"/dev/tcp",
    
    # System modification
    r"shutdown",
    r"reboot",
    r"init\s+0",
    r"init\s+6",
    r"systemctl\s+stop",
    r"systemctl\s+disable",
    r"launchctl\s+unload",
    
    # Path traversal attempts
    r"\.\./\.\./\.\.",
    r"/etc/passwd",
    r"/etc/shadow",
]


class TerminalRunCommandInput(BaseModel):
    """Input for running a terminal command."""
    command: str = Field(description="Shell command to execute")
    timeout: int = Field(default=300, description="Timeout in seconds (default: 300)")
    directory: Optional[str] = Field(
        default=None, 
        description="Working directory to execute the command in. Must be from the allowed directories list. If not specified, uses the default workspace directory."
    )


class TerminalRunCommandTool(BaseTool):
    """Execute shell commands in the mounted working directory."""
    
    name: str = "terminal_run_command"
    description: str = """Execute a shell command in the workspace directory.
    
Use this to run tests, build commands, git operations, package managers, etc.
Commands are executed in the mounted workspace directory or a specified allowed directory.

Examples:
- Run tests: `npm test`, `pytest`, `go test ./...`
- Build: `npm run build`, `cargo build`, `make`
- Git: `git status`, `git diff`, `git log --oneline -10`
- Package managers: `npm install`, `pip install -r requirements.txt`

The command runs with the workspace (or specified directory) as the current working directory.
Returns stdout, stderr, and exit code.

Use the 'directory' parameter to run commands in a specific allowed directory when working with multi-folder workspaces."""
    args_schema: type[BaseModel] = TerminalRunCommandInput
    
    work_dir: str = ""
    allowed_directories: List[str] = []
    blocked_patterns: List[str] = []
    
    def __init__(self, work_dir: str, blocked_patterns: Optional[List[str]] = None, 
                 allowed_directories: Optional[List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.work_dir = str(Path(work_dir).resolve())
        self.blocked_patterns = blocked_patterns or DEFAULT_BLOCKED_PATTERNS
        # Build allowed directories list: always include work_dir, plus any additional allowed dirs
        self.allowed_directories = [self.work_dir]
        if allowed_directories:
            for d in allowed_directories:
                resolved = str(Path(d).resolve())
                if resolved not in self.allowed_directories:
                    self.allowed_directories.append(resolved)
    
    def _is_command_blocked(self, command: str) -> tuple[bool, str]:
        """Check if command matches any blocked patterns."""
        command_lower = command.lower()
        for pattern in self.blocked_patterns:
            if re.search(pattern, command_lower, re.IGNORECASE):
                return True, pattern
        return False, ""
    
    def _validate_directory(self, directory: Optional[str]) -> tuple[bool, str, str]:
        """
        Validate that the requested directory is in the allowed list.
        
        Args:
            directory: Requested directory path or None
            
        Returns:
            Tuple of (is_valid, error_message, resolved_directory)
        """
        if directory is None:
            return True, "", self.work_dir
        
        # Resolve the requested directory
        try:
            resolved = str(Path(directory).resolve())
        except Exception as e:
            return False, f"Invalid directory path: {e}", ""
        
        # Check if directory exists
        if not Path(resolved).is_dir():
            return False, f"Directory does not exist: {directory}", ""
        
        # Check if it's in the allowed list or is a subdirectory of an allowed directory
        for allowed in self.allowed_directories:
            if resolved == allowed or resolved.startswith(allowed + os.sep):
                return True, "", resolved
        
        allowed_list = "\n  - ".join(self.allowed_directories)
        return False, f"Directory not in allowed list: {directory}\n\nAllowed directories:\n  - {allowed_list}", ""
    
    def _validate_paths_in_command(self, command: str, target_dir: str) -> tuple[bool, str]:
        """
        Validate that any paths referenced in the command don't escape allowed directories.
        This is a best-effort check for obvious path traversal.
        
        Args:
            command: The command to validate
            target_dir: The target directory where command will be executed
        """
        # Check for obvious path traversal patterns
        if "../../../" in command or "/.." in command:
            return False, "Path traversal detected"
        
        # Check for absolute paths outside allowed directories
        try:
            parts = shlex.split(command)
        except ValueError:
            # If we can't parse the command, skip path validation
            parts = []
            
        for part in parts:
            if part.startswith("/"):
                # Allow common system paths that are safe to reference
                safe_prefixes = ["/dev/null", "/tmp", "/usr/bin", "/usr/local/bin", "/bin"]
                if any(part.startswith(p) for p in safe_prefixes):
                    continue
                # Check if it's within any allowed directory
                is_allowed = False
                for allowed in self.allowed_directories:
                    if part.startswith(allowed) or part == allowed:
                        is_allowed = True
                        break
                if not is_allowed:
                    return False, f"Absolute path outside allowed directories: {part}"
        
        return True, ""
    
    def _run(self, command: str, timeout: int = 300, directory: Optional[str] = None) -> str:
        """Execute the command and return results."""
        # Validate the requested directory
        dir_valid, dir_error, target_dir = self._validate_directory(directory)
        if not dir_valid:
            return f"❌ Directory validation failed: {dir_error}"
        
        # Check if command is blocked
        is_blocked, pattern = self._is_command_blocked(command)
        if is_blocked:
            return f"❌ Command blocked for security reasons.\nMatched pattern: {pattern}\n\nThis command pattern is not allowed. Please use a safer alternative."
        
        # Validate paths in command
        path_valid, path_error = self._validate_paths_in_command(command, target_dir)
        if not path_valid:
            allowed_list = ", ".join(self.allowed_directories)
            return f"❌ Command rejected: {path_error}\n\nCommands must operate within allowed directories: {allowed_list}"
        
        try:
            # Execute command in target_dir
            result = subprocess.run(
                command,
                shell=True,
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PWD": target_dir}
            )
            
            output_parts = []
            
            # Show which directory the command was executed in if not default
            if target_dir != self.work_dir:
                output_parts.append(f"[Executed in: {target_dir}]")
            
            if result.stdout:
                output_parts.append(f"stdout:\n{result.stdout}")
            
            if result.stderr:
                output_parts.append(f"stderr:\n{result.stderr}")
            
            output_parts.append(f"exit_code: {result.returncode}")
            
            # Add hint when search-like commands return empty results
            if result.returncode == 0 and not result.stdout.strip():
                if self._is_search_command(command):
                    hint = self._generate_empty_search_hint(command, target_dir)
                    output_parts.append(hint)
            
            return "\n\n".join(output_parts)
            
        except subprocess.TimeoutExpired:
            return f"❌ Command timed out after {timeout} seconds.\n\nConsider:\n- Breaking into smaller operations\n- Using --timeout flag for longer operations\n- Running in background if appropriate"
        except Exception as e:
            return f"❌ Error executing command: {str(e)}"
    
    def _is_search_command(self, command: str) -> bool:
        """Check if the command is a search/find operation."""
        search_patterns = [
            r'\bfind\b',
            r'\bgrep\b',
            r'\brg\b',  # ripgrep
            r'\bag\b',  # silver searcher
            r'\back\b',
            r'\bfzf\b',
            r'\blocate\b',
            r'\bfd\b',  # fd-find
            r'\bxargs\s+grep',
        ]
        command_lower = command.lower()
        return any(re.search(pattern, command_lower) for pattern in search_patterns)
    
    def _generate_empty_search_hint(self, command: str, target_dir: str) -> str:
        """Generate a helpful hint when a search command returns no results."""
        hints = ["💡 **No results found.** Consider:"]
        
        # Check if searching in the right directory
        if len(self.allowed_directories) > 1:
            other_dirs = [d for d in self.allowed_directories if d != target_dir]
            hints.append(f"  - **Wrong directory?** You searched in `{target_dir}`")
            hints.append(f"    Other allowed directories: {', '.join(f'`{d}`' for d in other_dirs)}")
        else:
            hints.append(f"  - **Verify directory:** Currently searching in `{target_dir}`")
        
        # Suggest adjusting search criteria
        hints.append("  - **Adjust search pattern:** Try broader terms, different casing, or partial matches")
        hints.append("  - **Check file extensions:** Ensure you're searching the right file types")
        
        # Specific suggestions based on command patterns
        if 'grep' in command.lower():
            hints.append("  - **Grep tips:** Use `-i` for case-insensitive, `-r` for recursive, or try regex patterns")
        if 'find' in command.lower() and '-name' in command:
            hints.append("  - **Find tips:** Use wildcards like `*.py` or `-iname` for case-insensitive matching")
        
        return "\n".join(hints)


def load_blocked_patterns(config_path: Optional[str] = None) -> List[str]:
    """
    Load blocked command patterns from config file.
    Falls back to defaults if file doesn't exist.
    
    Args:
        config_path: Path to blocked_commands.txt file
        
    Returns:
        List of regex patterns
    """
    patterns = list(DEFAULT_BLOCKED_PATTERNS)
    
    if config_path and Path(config_path).exists():
        try:
            content = Path(config_path).read_text()
            for line in content.splitlines():
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    patterns.append(line)
            logger.debug(f"Loaded {len(patterns)} blocked patterns from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load blocked patterns from {config_path}: {e}")
    
    return patterns


def get_terminal_tools(
    work_dir: str,
    blocked_patterns_path: Optional[str] = None,
    allowed_directories: Optional[List[str]] = None
) -> List[BaseTool]:
    """
    Get terminal execution tools for the given working directory.
    
    Args:
        work_dir: The default workspace directory (must be absolute path)
        blocked_patterns_path: Optional path to custom blocked_commands.txt
        allowed_directories: Optional list of additional directories where commands can be executed.
                           The work_dir is always included in the allowed list.
                           This enables multi-folder workspace support.
        
    Returns:
        List of terminal tools
    """
    work_dir = str(Path(work_dir).resolve())
    
    if not Path(work_dir).is_dir():
        raise ValueError(f"Work directory does not exist: {work_dir}")
    
    blocked_patterns = load_blocked_patterns(blocked_patterns_path)
    
    # Validate and resolve allowed directories
    validated_allowed_dirs = []
    if allowed_directories:
        for d in allowed_directories:
            resolved = str(Path(d).resolve())
            if Path(resolved).is_dir():
                validated_allowed_dirs.append(resolved)
            else:
                logger.warning(f"Allowed directory does not exist, skipping: {d}")
    
    return [
        TerminalRunCommandTool(
            work_dir=work_dir,
            blocked_patterns=blocked_patterns,
            allowed_directories=validated_allowed_dirs
        )
    ]


def create_default_blocked_patterns_file(config_dir: str) -> str:
    """
    Create default blocked_commands.txt file in config directory.
    
    Args:
        config_dir: Directory to create the file in (e.g., $ALITA_DIR/security)
        
    Returns:
        Path to created file
    """
    security_dir = Path(config_dir) / "security"
    security_dir.mkdir(parents=True, exist_ok=True)
    
    blocked_file = security_dir / "blocked_commands.txt"
    
    if not blocked_file.exists():
        content = """# Blocked Command Patterns for Alita CLI
# Each line is a regex pattern. Lines starting with # are comments.
# These patterns are checked against commands before execution.

# === Destructive Commands ===
rm\\s+-rf\\s+/
rm\\s+-rf\\s+~
rm\\s+-rf\\s+\\*
sudo\\s+rm
mkfs
dd\\s+if=

# === Privilege Escalation ===
sudo\\s+su
sudo\\s+-i
chmod\\s+777
chown\\s+root

# === Data Exfiltration ===
curl.*\\|.*sh
wget.*\\|.*sh
nc\\s+-e

# === System Modification ===
shutdown
reboot
init\\s+0
systemctl\\s+stop

# === Path Traversal ===
\\.\\./\\.\\./\\.\\.
/etc/passwd
/etc/shadow

# Add your custom patterns below:
"""
        blocked_file.write_text(content)
        logger.info(f"Created default blocked patterns file: {blocked_file}")
    
    return str(blocked_file)
