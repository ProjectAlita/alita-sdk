"""
Toolkit configuration loading and management.

Handles loading toolkit configurations from JSON/YAML files.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, List

from .config import substitute_env_vars


# All available tools in the inventory toolkit
INVENTORY_TOOLS = [
    "search_graph",
    "get_entity",
    "get_entity_content",
    "impact_analysis",
    "get_related_entities",
    "get_stats",
    "get_citations",
    "list_entities_by_type",
    "list_entities_by_layer",
]


def load_toolkit_config(file_path: str) -> Dict[str, Any]:
    """Load toolkit configuration from JSON or YAML file with env var substitution."""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Toolkit configuration not found: {file_path}")
    
    with open(path) as f:
        content = f.read()
    
    # Apply environment variable substitution
    content = substitute_env_vars(content)
    
    # Parse based on file extension
    if path.suffix in ['.yaml', '.yml']:
        return yaml.safe_load(content)
    else:
        return json.loads(content)


def load_toolkit_configs(agent_def: Dict[str, Any], toolkit_config_paths: tuple) -> List[Dict[str, Any]]:
    """Load all toolkit configurations from agent definition and CLI options.
    
    Args:
        agent_def: Agent definition dictionary
        toolkit_config_paths: Tuple of file paths or dict configs from CLI options
        
    Returns:
        List of toolkit configuration dictionaries
    """
    toolkit_configs = []
    
    # Load from agent definition if present
    if 'toolkit_configs' in agent_def:
        for tk_config in agent_def['toolkit_configs']:
            if isinstance(tk_config, dict):
                if 'file' in tk_config:
                    config = load_toolkit_config(tk_config['file'])
                    toolkit_configs.append(config)
                elif 'config' in tk_config:
                    toolkit_configs.append(tk_config['config'])
                elif 'type' in tk_config:
                    # Direct toolkit config (e.g., {'type': 'inventory', ...})
                    toolkit_configs.append(tk_config)
    
    # Load from CLI options - can be file paths (str) or dict configs
    if toolkit_config_paths:
        for config_item in toolkit_config_paths:
            if isinstance(config_item, dict):
                # Direct config dict (e.g., from /inventory command)
                toolkit_configs.append(config_item)
            elif isinstance(config_item, str):
                # File path
                config = load_toolkit_config(config_item)
                toolkit_configs.append(config)
    
    return toolkit_configs
