"""
Agent loading and definition management.

Handles loading agent definitions from various file formats (YAML, JSON, Markdown).
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import SecretStr

from .config import substitute_env_vars


def load_agent_definition(file_path: str) -> Dict[str, Any]:
    """
    Load agent definition from file.
    
    Supports:
    - YAML files (.yaml, .yml)
    - JSON files (.json)
    - Markdown files with YAML frontmatter (.md)
    
    Args:
        file_path: Path to agent definition file
        
    Returns:
        Dictionary with agent configuration
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Agent definition not found: {file_path}")
    
    content = path.read_text()
    
    # Handle markdown with YAML frontmatter
    if path.suffix == '.md':
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                system_prompt = parts[2].strip()
                
                # Apply environment variable substitution
                system_prompt = substitute_env_vars(system_prompt)
                
                return {
                    'name': frontmatter.get('name', path.stem),
                    'description': frontmatter.get('description', ''),
                    'system_prompt': system_prompt,
                    'model': frontmatter.get('model'),
                    'tools': frontmatter.get('tools', []),
                    'temperature': frontmatter.get('temperature'),
                    'max_tokens': frontmatter.get('max_tokens'),
                    'toolkit_configs': frontmatter.get('toolkit_configs', []),
                    'filesystem_tools_preset': frontmatter.get('filesystem_tools_preset'),
                    'filesystem_tools_include': frontmatter.get('filesystem_tools_include'),
                    'filesystem_tools_exclude': frontmatter.get('filesystem_tools_exclude'),
                    'mcps': frontmatter.get('mcps', [])
                }
        
        # Plain markdown - use content as system prompt
        return {
            'name': path.stem,
            'system_prompt': substitute_env_vars(content),
        }
    
    # Handle YAML
    if path.suffix in ['.yaml', '.yml']:
        content = substitute_env_vars(content)
        config = yaml.safe_load(content)
        if 'system_prompt' in config:
            config['system_prompt'] = substitute_env_vars(config['system_prompt'])
        return config
    
    # Handle JSON
    if path.suffix == '.json':
        content = substitute_env_vars(content)
        config = json.loads(content)
        if 'system_prompt' in config:
            config['system_prompt'] = substitute_env_vars(config['system_prompt'])
        return config
    
    raise ValueError(f"Unsupported file format: {path.suffix}")


def unwrap_secrets(obj: Any) -> Any:
    """
    Recursively unwrap pydantic SecretStr values into plain strings.

    Handles nested dicts, lists, tuples, and sets while preserving structure.
    """
    if isinstance(obj, SecretStr):
        return obj.get_secret_value()
    if isinstance(obj, dict):
        return {k: unwrap_secrets(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [unwrap_secrets(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(unwrap_secrets(v) for v in obj)
    if isinstance(obj, set):
        return {unwrap_secrets(v) for v in obj}
    return obj


def build_agent_data_structure(agent_def: Dict[str, Any], toolkit_configs: list, 
                               llm_model: str, llm_temperature: float, llm_max_tokens: int) -> Dict[str, Any]:
    """
    Convert a local agent definition to the data structure expected by the Assistant class.
    
    This utility function bridges between simple agent definition formats (e.g., from markdown files)
    and the structured format that the Assistant class requires internally.
    
    Args:
        agent_def: The agent definition loaded from a local file (markdown, YAML, or JSON)
        toolkit_configs: List of toolkit configurations to be used by the agent
        llm_model: The LLM model name (e.g., 'gpt-4o')
        llm_temperature: Temperature setting for the model
        llm_max_tokens: Maximum tokens for model responses
        
    Returns:
        A dictionary in the format expected by the Assistant constructor with keys:
        - instructions: System prompt for the agent
        - tools: List of tool/toolkit configurations
        - variables: Agent variables (empty for local agents)
        - meta: Metadata including step_limit and internal_tools
        - llm_settings: Complete LLM configuration
        - agent_type: Type of agent (react, openai, etc.)
    """
    # Import toolkit registry to validate configs
    from alita_sdk.tools import AVAILABLE_TOOLS
    
    # Build the tools list from agent definition and toolkit configs
    tools = []
    processed_toolkit_names = set()
    
    # Validate and process toolkit configs through their Pydantic schemas
    validated_toolkit_configs = []
    for toolkit_config in toolkit_configs:
        toolkit_type = toolkit_config.get('type')
        if toolkit_type and toolkit_type in AVAILABLE_TOOLS:
            try:
                toolkit_info = AVAILABLE_TOOLS[toolkit_type]
                if 'toolkit_class' in toolkit_info:
                    toolkit_class = toolkit_info['toolkit_class']
                    if hasattr(toolkit_class, 'toolkit_config_schema'):
                        schema = toolkit_class.toolkit_config_schema()
                        validated_config = schema(**toolkit_config)
                        # Use python mode so SecretStr remains as objects, then unwrap recursively
                        validated_dict = unwrap_secrets(validated_config.model_dump(mode="python"))
                        validated_dict['type'] = toolkit_config.get('type')
                        validated_dict['toolkit_name'] = toolkit_config.get('toolkit_name')
                        validated_toolkit_configs.append(validated_dict)
                    else:
                        validated_toolkit_configs.append(toolkit_config)
                else:
                    validated_toolkit_configs.append(toolkit_config)
            except Exception:
                validated_toolkit_configs.append(toolkit_config)
        else:
            validated_toolkit_configs.append(toolkit_config)
    
    # Add tools from agent definition
    for tool_name in agent_def.get('tools', []):
        toolkit_config = next((tk for tk in validated_toolkit_configs if tk.get('toolkit_name') == tool_name), None)
        if toolkit_config:
            tools.append({
                'type': toolkit_config.get('type'),
                'toolkit_name': toolkit_config.get('toolkit_name'),
                'settings': toolkit_config,
                'selected_tools': toolkit_config.get('selected_tools', [])
            })
            processed_toolkit_names.add(tool_name)
        else:
            tools.append({
                'type': tool_name,
                'name': tool_name
            })
    
    # Add toolkit_configs that weren't already referenced
    for toolkit_config in validated_toolkit_configs:
        toolkit_name = toolkit_config.get('toolkit_name')
        if toolkit_name and toolkit_name not in processed_toolkit_names:
            tools.append({
                'type': toolkit_config.get('type'),
                'toolkit_name': toolkit_name,
                'settings': toolkit_config,
                'selected_tools': toolkit_config.get('selected_tools', [])
            })
    return {
        'instructions': agent_def.get('system_prompt', ''),
        'tools': tools,
        'variables': [],
        'meta': {
            'step_limit': agent_def.get('step_limit', 25),
            'internal_tools': agent_def.get('internal_tools', [])
        },
        'llm_settings': {
            'model_name': llm_model,
            'max_tokens': llm_max_tokens,
            'temperature': llm_temperature,
            'integration_uid': None,
            'indexer_config': {
                'ai_model': 'langchain_openai.ChatOpenAI',
                'ai_model_params': {
                    'model': llm_model,
                    'temperature': llm_temperature,
                    'max_tokens': llm_max_tokens
                }
            }
        },
        'agent_type': agent_def.get('agent_type', 'react')
    }
