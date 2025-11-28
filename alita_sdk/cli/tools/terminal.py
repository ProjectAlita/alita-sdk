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


class TerminalRunCommandTool(BaseTool):
    """Execute shell commands in the mounted working directory."""
    
    name: str = "terminal_run_command"
    description: str = """Execute a shell command in the workspace directory.
    
Use this to run tests, build commands, git operations, package managers, etc.
Commands are executed in the mounted workspace directory.

Examples:
- Run tests: `npm test`, `pytest`, `go test ./...`
- Build: `npm run build`, `cargo build`, `make`
- Git: `git status`, `git diff`, `git log --oneline -10`
- Package managers: `npm install`, `pip install -r requirements.txt`

The command runs with the workspace as the current working directory.
Returns stdout, stderr, and exit code."""
    args_schema: type[BaseModel] = TerminalRunCommandInput
    
    work_dir: str = ""
    blocked_patterns: List[str] = []
    
    def __init__(self, work_dir: str, blocked_patterns: Optional[List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.work_dir = str(Path(work_dir).resolve())
        self.blocked_patterns = blocked_patterns or DEFAULT_BLOCKED_PATTERNS
    
    def _is_command_blocked(self, command: str) -> tuple[bool, str]:
        """Check if command matches any blocked patterns."""
        command_lower = command.lower()
        for pattern in self.blocked_patterns:
            if re.search(pattern, command_lower, re.IGNORECASE):
                return True, pattern
        return False, ""
    
    def _validate_paths_in_command(self, command: str) -> tuple[bool, str]:
        """
        Validate that any paths referenced in the command don't escape work_dir.
        This is a best-effort check for obvious path traversal.
        """
        # Check for obvious path traversal patterns
        if "../../../" in command or "/.." in command:
            return False, "Path traversal detected"
        
        # Check for absolute paths outside work_dir
        parts = shlex.split(command)
        for part in parts:
            if part.startswith("/") and not part.startswith(self.work_dir):
                # Allow common system paths that are safe to reference
                safe_prefixes = ["/dev/null", "/tmp", "/usr/bin", "/usr/local/bin", "/bin"]
                if not any(part.startswith(p) for p in safe_prefixes):
                    return False, f"Absolute path outside workspace: {part}"
        
        return True, ""
    
    def _run(self, command: str, timeout: int = 300) -> str:
        """Execute the command and return results."""
        # Check if command is blocked
        is_blocked, pattern = self._is_command_blocked(command)
        if is_blocked:
            return f"❌ Command blocked for security reasons.\nMatched pattern: {pattern}\n\nThis command pattern is not allowed. Please use a safer alternative."
        
        # Validate paths in command
        path_valid, path_error = self._validate_paths_in_command(command)
        if not path_valid:
            return f"❌ Command rejected: {path_error}\n\nCommands must operate within the workspace directory: {self.work_dir}"
        
        try:
            # Execute command in work_dir
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PWD": self.work_dir}
            )
            
            output_parts = []
            
            if result.stdout:
                output_parts.append(f"stdout:\n{result.stdout}")
            
            if result.stderr:
                output_parts.append(f"stderr:\n{result.stderr}")
            
            output_parts.append(f"exit_code: {result.returncode}")
            
            return "\n\n".join(output_parts)
            
        except subprocess.TimeoutExpired:
            return f"❌ Command timed out after {timeout} seconds.\n\nConsider:\n- Breaking into smaller operations\n- Using --timeout flag for longer operations\n- Running in background if appropriate"
        except Exception as e:
            return f"❌ Error executing command: {str(e)}"


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
    blocked_patterns_path: Optional[str] = None
) -> List[BaseTool]:
    """
    Get terminal execution tools for the given working directory.
    
    Args:
        work_dir: The workspace directory (must be absolute path)
        blocked_patterns_path: Optional path to custom blocked_commands.txt
        
    Returns:
        List of terminal tools
    """
    work_dir = str(Path(work_dir).resolve())
    
    if not Path(work_dir).is_dir():
        raise ValueError(f"Work directory does not exist: {work_dir}")
    
    blocked_patterns = load_blocked_patterns(blocked_patterns_path)
    
    return [
        TerminalRunCommandTool(
            work_dir=work_dir,
            blocked_patterns=blocked_patterns
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
