"""
Toolkit configuration and instantiation utilities for inventory ingestion.

This module provides functions to load toolkit configurations, instantiate source
toolkits from various sources (filesystem, GitHub, ADO), and get LLM instances
for entity extraction.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from alita_sdk.alita_client import AlitaClient


def load_toolkit_config(toolkit_path: str) -> Dict[str, Any]:
    """
    Load and parse a toolkit config JSON file.
    
    Supports environment variable substitution for values like ${GITHUB_PAT}.
    
    Args:
        toolkit_path: Path to the toolkit configuration JSON file
        
    Returns:
        Dictionary containing the parsed and environment-resolved configuration
        
    Example:
        >>> config = load_toolkit_config("configs/github_toolkit.json")
        >>> config['type']
        'github'
    """
    with open(toolkit_path, 'r') as f:
        config = json.load(f)
    
    # Recursively resolve environment variables
    def resolve_env_vars(obj):
        if isinstance(obj, str):
            # Match ${VAR_NAME} pattern
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, obj)
            for var_name in matches:
                env_value = os.environ.get(var_name, '')
                obj = obj.replace(f'${{{var_name}}}', env_value)
            return obj
        elif isinstance(obj, dict):
            return {k: resolve_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env_vars(item) for item in obj]
        return obj
    
    return resolve_env_vars(config)


def get_llm_for_config(
    client: AlitaClient,
    model: Optional[str] = None,
    temperature: float = 0.0
):
    """
    Get LLM instance from Alita client for entity extraction.
    
    Args:
        client: AlitaClient instance
        model: Model name (defaults to 'gpt-4o-mini' if not specified)
        temperature: Temperature for the model (default 0.0 for deterministic output)
        
    Returns:
        LLM instance configured with the specified model and parameters
        
    Example:
        >>> client = AlitaClient(...)
        >>> llm = get_llm_for_config(client, model='gpt-4o', temperature=0.0)
    """
    model_name = model or 'gpt-4o-mini'
    
    return client.get_llm(
        model_name=model_name,
        model_config={
            'temperature': temperature,
            'max_tokens': 4096
        }
    )


def get_source_toolkit(toolkit_config: Dict[str, Any]):
    """
    Instantiate a source toolkit from configuration.
    
    Supports filesystem, GitHub, and Azure DevOps (ADO) toolkit types. For SDK-based
    toolkits (GitHub, ADO), automatically handles configuration mapping and toolkit
    instantiation from the registry.
    
    Args:
        toolkit_config: Toolkit configuration dictionary with 'type' key
                       and type-specific parameters
                       
    Returns:
        Instantiated toolkit object ready for ingestion
        
    Raises:
        ValueError: If toolkit type is unsupported or configuration is invalid
        
    Example:
        >>> # Filesystem toolkit
        >>> config = {'type': 'filesystem', 'base_path': '/path/to/code'}
        >>> toolkit = get_source_toolkit(config)
        
        >>> # GitHub toolkit
        >>> config = {
        ...     'type': 'github',
        ...     'github_token': 'ghp_...',
        ...     'github_repository': 'owner/repo',
        ...     'github_branch': 'main'
        ... }
        >>> toolkit = get_source_toolkit(config)
    """
    from alita_sdk.community.inventory.filesystem_toolkit import FilesystemToolkit
    from alita_sdk.community.toolkits import AVAILABLE_TOOLS
    
    toolkit_type = toolkit_config.get('type')
    
    if toolkit_type == 'filesystem':
        base_path = toolkit_config.get('base_path')
        if not base_path:
            raise ValueError("Filesystem toolkit requires 'base_path' configuration")
        return FilesystemToolkit(base_path=Path(base_path))
    
    # Handle SDK toolkits (GitHub, ADO)
    if toolkit_type not in AVAILABLE_TOOLS:
        raise ValueError(
            f"Unknown toolkit type: {toolkit_type}. "
            f"Available types: filesystem, {', '.join(AVAILABLE_TOOLS.keys())}"
        )
    
    toolkit_class = AVAILABLE_TOOLS[toolkit_type]
    
    # Flatten nested config if needed
    config_for_init = {}
    for key, value in toolkit_config.items():
        if key == 'type':
            continue
        if isinstance(value, dict):
            # Flatten nested dicts
            config_for_init.update(value)
        else:
            config_for_init[key] = value
    
    # Map field names for specific toolkit types
    if toolkit_type == 'github':
        field_mapping = {
            'github_token': 'token',
            'github_repository': 'repository',
            'github_branch': 'branch'
        }
        config_for_init = {
            field_mapping.get(k, k): v 
            for k, v in config_for_init.items()
        }
    elif toolkit_type == 'ado':
        field_mapping = {
            'ado_token': 'token',
            'ado_organization': 'organization',
            'ado_project': 'project',
            'ado_repository': 'repository',
            'ado_branch': 'branch'
        }
        config_for_init = {
            field_mapping.get(k, k): v 
            for k, v in config_for_init.items()
        }
    
    # Instantiate toolkit
    return toolkit_class(**config_for_init)
