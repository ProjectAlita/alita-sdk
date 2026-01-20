"""
Agent setup utilities for test execution.

Handles loading and validating test runner, data generator, and validator agents.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


def load_test_runner_agent(agent_source: str) -> Tuple[Dict[str, Any], str]:
    """Load test runner agent definition.
    
    Args:
        agent_source: Path to agent definition file
        
    Returns:
        Tuple of (agent_def, agent_name)
        
    Raises:
        FileNotFoundError: If agent file doesn't exist
    """
    from ..agent_loader import load_agent_definition
    
    agent_source_path = Path(agent_source)
    if not agent_source_path.exists():
        raise FileNotFoundError(
            f"Agent definition not found: {agent_source}. "
            f"Make sure you are running from the repository root, "
            f"or pass --agent_source explicitly."
        )
    
    agent_def = load_agent_definition(agent_source)
    agent_name = agent_def.get('name', agent_source_path.stem)
    
    return agent_def, agent_name


def load_data_generator_agent(data_generator: str, skip_data_generation: bool) -> Optional[Dict[str, Any]]:
    """Load data generator agent definition if needed.
    
    Args:
        data_generator: Path to data generator agent file
        skip_data_generation: Whether data generation is skipped
        
    Returns:
        Agent definition dict or None if skipped/failed
    """
    from ..agent_loader import load_agent_definition
    
    if skip_data_generation:
        return None
    
    if not data_generator:
        return None
    
    try:
        data_gen_def = load_agent_definition(data_generator)
        data_gen_name = data_gen_def.get('name', Path(data_generator).stem)
        console.print(f"Data Generator Agent: [bold]{data_gen_name}[/bold]\n")
        return data_gen_def
    except Exception as e:
        console.print(f"[yellow]⚠ Warning: Failed to setup data generator: {e}[/yellow]")
        console.print("[yellow]Continuing with test execution...[/yellow]\n")
        logger.debug(f"Data generator setup error: {e}", exc_info=True)
        return None


def load_validator_agent(validator: Optional[str]) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
    """Load validator agent definition.
    
    Args:
        validator: Path to validator agent file (optional)
        
    Returns:
        Tuple of (validator_def, validator_name, validator_path)
    """
    from ..agent_loader import load_agent_definition
    
    validator_def = None
    validator_agent_name = "Default Validator"
    validator_path = validator
    
    # Try to load validator from specified path or default location
    if not validator_path:
        default_validator = Path.cwd() / '.alita' / 'agents' / 'test-validator.agent.md'
        if default_validator.exists():
            validator_path = str(default_validator)
    
    if validator_path and Path(validator_path).exists():
        try:
            validator_def = load_agent_definition(validator_path)
            validator_agent_name = validator_def.get('name', Path(validator_path).stem)
            console.print(f"Validator Agent: [bold]{validator_agent_name}[/bold]")
            console.print(f"[dim]Using: {validator_path}[/dim]\n")
        except Exception as e:
            console.print(f"[yellow]⚠ Warning: Failed to load validator agent: {e}[/yellow]")
            console.print(f"[yellow]Will use test runner agent for validation[/yellow]\n")
            logger.debug(f"Validator load error: {e}", exc_info=True)
    else:
        console.print(f"[dim]No validator agent specified, using test runner agent for validation[/dim]\n")
    
    return validator_def, validator_agent_name, validator_path
