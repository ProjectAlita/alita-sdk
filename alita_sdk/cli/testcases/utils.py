"""
General utility functions for test execution.

Includes toolkit name extraction and other helper functions.
"""

from pathlib import Path
from typing import Optional


def extract_toolkit_name(config_path: Optional[str]) -> str:
    """
    Extract toolkit name from config path.
    
    Args:
        config_path: Path to toolkit config (e.g., '.alita/tool_configs/github-config.json')
        
    Returns:
        Toolkit name (e.g., 'github') or 'unknown' if path is None/empty
    """
    if not config_path:
        return 'unknown'
    
    # Convert to Path
    path = Path(config_path)
    
    # First, try to extract from filename by removing common config suffixes
    # For paths like '.alita/tool_configs/confluence-config.json' -> 'confluence'
    stem = path.stem.replace('_config', '').replace('-config', '')
    if stem and stem.lower() != 'config':
        return stem
    
    # Fallback: use parent directory name if it's not a common directory
    # For paths like 'toolkits/github/config.yaml' -> 'github'
    if path.parent.name and path.parent.name not in ['.', 'toolkits', 'tool_configs', 'configs']:
        return path.parent.name
    
    # Last resort
    return 'unknown'
