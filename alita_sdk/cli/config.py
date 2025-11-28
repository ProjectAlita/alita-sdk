"""
Configuration management for Alita CLI.

Loads credentials and settings from .env files using the same pattern
as the SDK tests and Streamlit interface.
"""

import os
import re
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


class CLIConfig:
    """Configuration manager for Alita CLI."""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize CLI configuration.
        
        Args:
            env_file: Path to .env file. If None, checks ALITA_ENV_FILE env var,
                      then falls back to .alita/.env or .env in current directory
        """
        if env_file:
            self.env_file = env_file
        else:
            # Check ALITA_ENV_FILE environment variable first
            alita_env_file = os.getenv('ALITA_ENV_FILE')
            if alita_env_file and os.path.exists(alita_env_file):
                self.env_file = alita_env_file
            elif os.path.exists('.alita/.env'):
                self.env_file = '.alita/.env'
            else:
                self.env_file = '.env'
        self._load_env()
        
    def _load_env(self):
        """Load environment variables from .env file."""
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file)
            logger.debug(f"Loaded environment from {self.env_file}")
        else:
            logger.debug(f"No .env file found at {self.env_file}, using system environment")
    
    @property
    def deployment_url(self) -> Optional[str]:
        """Get deployment URL from environment."""
        return os.getenv('DEPLOYMENT_URL')
    
    @property
    def project_id(self) -> Optional[int]:
        """Get project ID from environment."""
        try:
            value = os.getenv('PROJECT_ID')
            return int(value) if value else None
        except (TypeError, ValueError):
            return None
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key from environment."""
        return os.getenv('API_KEY')
    
    @property
    def alita_dir(self) -> str:
        """Get Alita directory from environment (defaults to .alita)."""
        return os.getenv('ALITA_DIR', '.alita')
    
    @property
    def agents_dir(self) -> str:
        """Get agents directory (derived from ALITA_DIR)."""
        alita_agents = os.path.join(self.alita_dir, 'agents')
        # Fallback to .github/agents if .alita/agents doesn't exist
        if self.alita_dir == '.alita' and not os.path.exists(alita_agents):
            if os.path.exists('.github/agents'):
                return '.github/agents'
        return alita_agents
    
    @property
    def tools_dir(self) -> str:
        """Get tools directory (derived from ALITA_DIR)."""
        return os.path.join(self.alita_dir, 'tools')
    
    @property
    def mcp_config_path(self) -> str:
        """Get MCP configuration path (derived from ALITA_DIR)."""
        alita_mcp = os.path.join(self.alita_dir, 'mcp.json')
        # Fallback to mcp.json in current directory
        if not os.path.exists(alita_mcp) and os.path.exists('mcp.json'):
            return 'mcp.json'
        return alita_mcp
    
    def is_configured(self) -> bool:
        """Check if all required configuration is present."""
        return all([
            self.deployment_url,
            self.project_id is not None,
            self.api_key
        ])
    
    def get_missing_config(self) -> list[str]:
        """Get list of missing configuration items."""
        missing = []
        if not self.deployment_url:
            missing.append('DEPLOYMENT_URL')
        if self.project_id is None:
            missing.append('PROJECT_ID')
        if not self.api_key:
            missing.append('API_KEY')
        return missing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'deployment_url': self.deployment_url,
            'project_id': self.project_id,
            'api_key': '***' if self.api_key else None  # Masked for security
        }


def get_config(env_file: Optional[str] = None) -> CLIConfig:
    """
    Get CLI configuration instance.
    
    Args:
        env_file: Optional path to .env file
        
    Returns:
        CLIConfig instance
    """
    return CLIConfig(env_file=env_file)


def substitute_env_vars(text: str) -> str:
    """
    Substitute environment variables in text.
    
    Supports both ${VAR} and $VAR syntax.
    
    Args:
        text: Text containing environment variable references
        
    Returns:
        Text with environment variables substituted
    """
    # Replace ${VAR} syntax
    def replace_braced(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))
    
    text = re.sub(r'\$\{([^}]+)\}', replace_braced, text)
    
    # Replace $VAR syntax (word boundaries)
    def replace_simple(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))
    
    text = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', replace_simple, text)
    
    return text
