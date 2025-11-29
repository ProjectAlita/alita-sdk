"""
Configuration management for Alita CLI.

Loads credentials and settings from .env files using the same pattern
as the SDK tests and Streamlit interface.
"""

import os
import re
import json
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
        self._config_json: Dict[str, Any] = {}
        
        if env_file:
            self.env_file = env_file
        else:
            # Check ALITA_ENV_FILE environment variable first
            alita_env_file = os.getenv('ALITA_ENV_FILE')
            if alita_env_file:
                # Expand ~ and resolve path
                expanded_path = os.path.expanduser(alita_env_file)
                if os.path.exists(expanded_path):
                    self.env_file = expanded_path
                else:
                    logger.warning(f"ALITA_ENV_FILE set to {alita_env_file} but file not found")
                    self.env_file = expanded_path  # Still use it, will warn later
            elif os.path.exists(os.path.expanduser('~/.alita/.env')):
                self.env_file = os.path.expanduser('~/.alita/.env')
            elif os.path.exists('.alita/.env'):
                self.env_file = '.alita/.env'
            else:
                self.env_file = '.env'
        self._load_env()
        self._load_config_json()
        
    def _load_env(self):
        """Load environment variables from .env file."""
        if os.path.exists(self.env_file):
            # Use override=True to ensure .env values take precedence
            load_dotenv(self.env_file, override=True)
            logger.debug(f"Loaded environment from {self.env_file}")
        else:
            logger.debug(f"No .env file found at {self.env_file}, using system environment")
    
    def _load_config_json(self):
        """Load configuration from $ALITA_DIR/config.json as fallback."""
        # Try ALITA_DIR from env, then ~/.alita, then .alita
        alita_dir = os.getenv('ALITA_DIR')
        if alita_dir:
            config_path = os.path.join(os.path.expanduser(alita_dir), 'config.json')
        else:
            # Try ~/.alita/config.json first, then .alita/config.json
            home_config = os.path.expanduser('~/.alita/config.json')
            local_config = '.alita/config.json'
            if os.path.exists(home_config):
                config_path = home_config
            elif os.path.exists(local_config):
                config_path = local_config
            else:
                config_path = home_config  # Default path even if doesn't exist
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self._config_json = json.load(f)
                logger.debug(f"Loaded config from {config_path}")
                
                # Load env section into environment variables
                self._load_env_section()
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config.json: {e}")
    
    def _load_env_section(self):
        """Load variables from config.json 'env' section into environment."""
        env_vars = self._config_json.get('env', {})
        if isinstance(env_vars, dict):
            for key, value in env_vars.items():
                # Only set if not already in environment (env vars take precedence)
                if key not in os.environ and value is not None:
                    os.environ[key] = str(value)
                    logger.debug(f"Set {key} from config.json env section")
    
    def _get_config_value(self, env_key: str, json_key: Optional[str] = None) -> Optional[str]:
        """
        Get config value from environment first, then config.json fallback.
        
        Args:
            env_key: Environment variable name
            json_key: Key in config.json (defaults to lowercase of env_key)
        """
        # Try environment variable first
        value = os.getenv(env_key)
        if value:
            return value
        
        # Fallback to config.json
        if json_key is None:
            json_key = env_key.lower()
        
        return self._config_json.get(json_key)
    
    @property
    def deployment_url(self) -> Optional[str]:
        """Get deployment URL from environment or config.json."""
        return self._get_config_value('DEPLOYMENT_URL', 'deployment_url')
    
    @property
    def project_id(self) -> Optional[int]:
        """Get project ID from environment or config.json."""
        try:
            value = self._get_config_value('PROJECT_ID', 'project_id')
            return int(value) if value else None
        except (TypeError, ValueError):
            return None
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key from environment or config.json."""
        return self._get_config_value('API_KEY', 'api_key')
    
    @property
    def default_model(self) -> Optional[str]:
        """Get default model from environment or config.json."""
        return self._get_config_value('ALITA_DEFAULT_MODEL', 'default_model')
    
    @property
    def default_temperature(self) -> Optional[float]:
        """Get default temperature from environment or config.json."""
        try:
            value = self._get_config_value('ALITA_DEFAULT_TEMPERATURE', 'default_temperature')
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    
    @property
    def default_max_tokens(self) -> Optional[int]:
        """Get default max tokens from environment or config.json."""
        try:
            value = self._get_config_value('ALITA_DEFAULT_MAX_TOKENS', 'default_max_tokens')
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    
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
    
    @property
    def context_management(self) -> Dict[str, Any]:
        """
        Get context management configuration from config.json.
        
        Returns configuration for chat history context management with defaults:
        - enabled: True - Enable context management
        - max_context_tokens: 8000 - Maximum tokens in context
        - preserve_recent_messages: 5 - Always keep N most recent messages
        - pruning_method: 'oldest_first' - Strategy for pruning (oldest_first, importance_based)
        - enable_summarization: True - Generate summaries of pruned messages
        - summary_trigger_ratio: 0.8 - Trigger summarization at 80% context fill
        - summaries_limit_count: 5 - Maximum number of summaries to keep
        - session_max_age_days: 30 - Purge sessions older than N days
        - max_sessions: 50 - Maximum number of sessions to keep
        """
        defaults = {
            'enabled': True,
            'max_context_tokens': 8000,
            'preserve_recent_messages': 5,
            'pruning_method': 'oldest_first',
            'enable_summarization': True,
            'summary_trigger_ratio': 0.8,
            'summaries_limit_count': 5,
            'session_max_age_days': 30,
            'max_sessions': 50,
            'weights': {
                'recency': 1.0,
                'importance': 1.0,
                'user_messages': 1.2,
                'thread_continuity': 1.0,
            },
        }
        
        # Get from config.json
        config = self._config_json.get('context_management', {})
        
        # Merge with defaults
        result = defaults.copy()
        if isinstance(config, dict):
            result.update(config)
        
        return result
    
    @property
    def sessions_dir(self) -> str:
        """Get sessions directory (derived from ALITA_DIR)."""
        return os.path.join(self.alita_dir, 'sessions')
    
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
