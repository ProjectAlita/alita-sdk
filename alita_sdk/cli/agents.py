"""
Agent commands for Alita CLI.

Provides commands to work with agents interactively or in handoff mode,
supporting both platform agents and local agent definition files.
"""

import asyncio
import click
import json
import logging
import sqlite3
import sys
import re
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import yaml

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from rich.text import Text
from rich.status import Status
from rich.live import Live

from .cli import get_client
# Import from refactored modules
from .agent_ui import print_welcome, print_help, display_output, extract_output_from_result
from .agent_loader import load_agent_definition
from .agent_executor import create_llm_instance, create_agent_executor, create_agent_executor_with_mcp
from .toolkit_loader import load_toolkit_config, load_toolkit_configs
from .callbacks import create_cli_callback, CLICallbackHandler
from .input_handler import get_input_handler, styled_input, styled_selection_input
# Context management for chat history
from .context import CLIContextManager, CLIMessage, purge_old_sessions as purge_context_sessions

logger = logging.getLogger(__name__)

# Create a rich console for beautiful output
console = Console()


def resolve_toolkit_config_path(config_path_str: str, test_file: Path, test_cases_dir: Path) -> Optional[str]:
    """
    Resolve toolkit configuration file path from test case.
    
    Tries multiple locations in order:
    1. Absolute path
    2. Relative to test case file directory
    3. Relative to test cases directory
    4. Relative to workspace root
    
    Args:
        config_path_str: Config path from test case
        test_file: Path to the test case file
        test_cases_dir: Path to test cases directory
        
    Returns:
        Absolute path to config file if found, None otherwise
    """
    if not config_path_str:
        return None
    
    # Normalize path separators
    config_path_str = config_path_str.replace('\\', '/')
    
    # Try absolute path first
    config_path = Path(config_path_str)
    if config_path.is_absolute() and config_path.exists():
        return str(config_path)
    
    # Try relative to test case file directory
    config_path = test_file.parent / config_path_str
    if config_path.exists():
        return str(config_path)
    
    # Try relative to test_cases_dir
    config_path = test_cases_dir / config_path_str
    if config_path.exists():
        return str(config_path)
    
    # Try relative to workspace root
    workspace_root = Path.cwd()
    config_path = workspace_root / config_path_str
    if config_path.exists():
        return str(config_path)
    
    return None


def parse_test_case(test_case_path: str) -> Dict[str, Any]:
    """
    Parse a test case markdown file to extract configuration, steps, and expectations.
    
    Args:
        test_case_path: Path to the test case markdown file
        
    Returns:
        Dictionary containing:
        - name: Test case name
        - objective: Test objective
        - config_path: Path to toolkit config file
        - generate_test_data: Boolean flag indicating if test data generation is needed (default: True)
        - test_data_config: Dictionary of test data configuration from table
        - prerequisites: Pre-requisites section text
        - variables: List of variable placeholders found (e.g., {{TEST_PR_NUMBER}})
        - steps: List of test steps with their descriptions
        - expectations: List of expectations/assertions
    """
    path = Path(test_case_path)
    if not path.exists():
        raise FileNotFoundError(f"Test case not found: {test_case_path}")
    
    content = path.read_text(encoding='utf-8')
    
    # Extract test case name from the first heading
    name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    name = name_match.group(1) if name_match else path.stem
    
    # Extract objective
    objective_match = re.search(r'##\s+Objective\s*\n\n(.+?)(?=\n\n##|\Z)', content, re.DOTALL)
    objective = objective_match.group(1).strip() if objective_match else ""
    
    # Extract config path and generateTestData flag
    config_section_match = re.search(r'##\s+Config\s*\n\n(.+?)(?=\n\n##|\Z)', content, re.DOTALL)
    config_path = None
    generate_test_data = True  # Default to True if not specified
    
    if config_section_match:
        config_section = config_section_match.group(1)
        # Extract path
        path_match = re.search(r'path:\s*(.+?)(?=\n|$)', config_section, re.MULTILINE)
        if path_match:
            config_path = path_match.group(1).strip()
        
        # Extract generateTestData flag
        gen_data_match = re.search(r'generateTestData\s*:\s*(true|false)', config_section, re.IGNORECASE)
        if gen_data_match:
            generate_test_data = gen_data_match.group(1).lower() == 'true'
    
    # Extract Test Data Configuration table
    test_data_config = {}
    config_section_match = re.search(r'##\s+Test Data Configuration\s*\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
    if config_section_match:
        config_section = config_section_match.group(1)
        # Parse markdown table (format: | Parameter | Value | Description |)
        table_rows = re.findall(r'\|\s*\*\*([^*]+)\*\*\s*\|\s*`?([^|`]+)`?\s*\|', config_section)
        for param, value in table_rows:
            test_data_config[param.strip()] = value.strip()
    
    # Extract Pre-requisites section
    prerequisites = ""
    prereq_match = re.search(r'##\s+Pre-requisites\s*\n\n(.+?)(?=\n\n##|\Z)', content, re.DOTALL)
    if prereq_match:
        prerequisites = prereq_match.group(1).strip()
    
    # Find all variable placeholders ({{VARIABLE_NAME}})
    variables = list(set(re.findall(r'\{\{([A-Z_]+)\}\}', content)))
    
    # Extract test steps and expectations
    steps = []
    expectations = []
    
    # Find all Step sections
    step_pattern = r'###\s+Step\s+(\d+):\s+(.+?)\n\n(.+?)(?=\n\n###|\n\n##|\Z)'
    for step_match in re.finditer(step_pattern, content, re.DOTALL):
        step_num = step_match.group(1)
        step_title = step_match.group(2).strip()
        step_content = step_match.group(3).strip()
        
        # Extract the actual instruction (first paragraph before "Expectation:")
        instruction_match = re.search(r'(.+?)(?=\n\n\*\*Expectation:\*\*|\Z)', step_content, re.DOTALL)
        instruction = instruction_match.group(1).strip() if instruction_match else step_content
        
        # Extract expectation if present
        expectation_match = re.search(r'\*\*Expectation:\*\*\s+(.+)', step_content, re.DOTALL)
        expectation = expectation_match.group(1).strip() if expectation_match else None
        
        steps.append({
            'number': int(step_num),
            'title': step_title,
            'instruction': instruction,
            'expectation': expectation
        })
        
        if expectation:
            expectations.append({
                'step': int(step_num),
                'description': expectation
            })
    
    return {
        'name': name,
        'objective': objective,
        'config_path': config_path,
        'generate_test_data': generate_test_data,
        'test_data_config': test_data_config,
        'prerequisites': prerequisites,
        'variables': variables,
        'steps': steps,
        'expectations': expectations
    }


def validate_test_output(output: str, expectation: str) -> tuple[bool, str]:
    """
    Validate test output against expectations.
    
    Args:
        output: The actual output from the agent
        expectation: The expected result description
        
    Returns:
        Tuple of (passed: bool, details: str)
    """
    # Simple keyword-based validation
    # Extract key phrases from expectation
    
    # Common patterns in expectations
    if "contains" in expectation.lower():
        # Extract what should be contained
        contains_match = re.search(r'contains.*?["`]([^"`]+)["`]', expectation, re.IGNORECASE)
        if contains_match:
            expected_text = contains_match.group(1)
            if expected_text in output:
                return True, f"Output contains expected text: '{expected_text}'"
            else:
                return False, f"Output does not contain expected text: '{expected_text}'"
    
    if "without errors" in expectation.lower() or "runs without errors" in expectation.lower():
        # Check for common error indicators
        error_indicators = ['error', 'exception', 'failed', 'traceback']
        has_error = any(indicator in output.lower() for indicator in error_indicators)
        if not has_error:
            return True, "Execution completed without errors"
        else:
            return False, "Execution encountered errors"
    
    # Default: assume pass if output is non-empty
    if output and len(output.strip()) > 0:
        return True, "Output generated successfully"
    
    return False, "No output generated"


def _build_bulk_data_gen_prompt(parsed_test_cases: list) -> str:
    """Build consolidated requirements text for bulk test data generation."""
    requirements = []
    for idx, tc in enumerate(parsed_test_cases, 1):
        test_case = tc['data']
        test_file = tc['file']
        
        parts = [f"Test Case #{idx}: {test_case['name']}", f"File: {test_file.name}", ""]
        
        if test_case.get('test_data_config'):
            parts.append("Test Data Configuration:")
            for param, value in test_case['test_data_config'].items():
                parts.append(f"  - {param}: {value}")
        
        if test_case.get('prerequisites'):
            parts.append(f"\nPre-requisites:\n{test_case['prerequisites']}")
        
        if test_case.get('variables'):
            parts.append(f"\nVariables to generate: {', '.join(test_case['variables'])}")
        
        requirements.append("\n".join(parts))
    
    return f"""{'='*60}

{chr(10).join(requirements)}

{'='*60}"""


def _build_single_test_execution_prompt(test_case_info: dict, test_number: int) -> str:
    """Build execution prompt for a single test case."""
    test_case = test_case_info['data']
    test_file = test_case_info['file']
    
    parts = [
        f"\n{'='*80}",
        f"TEST CASE #{test_number}: {test_case['name']}",
        f"File: {test_file.name}",
        f"{'='*80}",
        "\nList all the tools you have in your environment. Execute the following steps in sequential order and report results:"
    ]
    
    if test_case['steps']:
        for step in test_case['steps']:
            parts.append(f"\nStep {step['number']}: {step['title']}")
            parts.append(step['instruction'])
    else:
        parts.append("\n(No steps defined)")
    
    return "\n".join(parts)


def _build_single_test_validation_prompt(test_case_info: dict, test_number: int, execution_output: str) -> str:
    """Build validation prompt for a single test case."""
    test_case = test_case_info['data']
    
    parts = [
        "Review the test execution results and validate this test case and provide the output in JSON format.\n",
        f"\nTest Case #{test_number}: {test_case['name']}"
    ]
    
    if test_case['steps']:
        for step in test_case['steps']:
            parts.append(f"  Step {step['number']}: {step['title']}")
            if step['expectation']:
                parts.append(f"    Expected: {step['expectation']}")
    
    parts.append(f"\n\nActual Execution Results:\n{execution_output}\n")
    
    # Escape quotes in test name for valid JSON in prompt
    escaped_test_name = test_case['name'].replace('"', '\\"')
    
    parts.append(f"""\nBased on the execution results above, validate this test case.

Respond ONLY with valid JSON in this EXACT format (no additional text before or after):
{{
  "test_number": {test_number},
  "test_name": "{escaped_test_name}",
  "steps": [
    {{"step_number": 1, "title": "<step title>", "passed": true/false, "details": "<brief explanation>"}},
    {{"step_number": 2, "title": "<step title>", "passed": true/false, "details": "<brief explanation>"}}
  ]
}}

IMPORTANT: Return ONLY the JSON object. Do not include any explanatory text before or after the JSON.""")
    
    return "\n".join(parts)


def _extract_json_from_text(text: str) -> dict:
    """Extract JSON object from text using brace counting."""
    start_idx = text.find('{')
    if start_idx == -1:
        raise ValueError("No JSON found in text")
    
    brace_count = 0
    end_idx = -1
    for i, char in enumerate(text[start_idx:], start=start_idx):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
    
    if end_idx == -1:
        raise ValueError("Could not find matching closing brace")
    
    return json.loads(text[start_idx:end_idx])


def _create_fallback_result_for_test(test_case: dict, test_file: Path, reason: str = 'Validation failed') -> dict:
    """Create a fallback result for a single test case with detailed step information.
    
    Args:
        test_case: Parsed test case data
        test_file: Path to test case file
        reason: Reason for fallback
        
    Returns:
        Fallback test result dict with step details
    """
    fallback_steps = []
    for step_info in test_case.get('steps', []):
        fallback_steps.append({
            'step_number': step_info['number'],
            'title': step_info['title'],
            'passed': False,
            'details': reason
        })
    
    return {
        'title': test_case['name'],
        'passed': False,
        'file': test_file.name,
        'step_results': fallback_steps,
        'validation_error': reason
    }


def _cleanup_executor_cache(cache: Dict[str, tuple], cache_name: str = "executor") -> None:
    """Clean up executor cache resources.
    
    Args:
        cache: Dictionary of cached executors
        cache_name: Name of cache for logging
    """
    console.print(f"[dim]Cleaning up {cache_name} cache...[/dim]")
    for cache_key, cached_items in cache.items():
        try:
            # Extract memory from tuple (second element)
            memory = cached_items[1] if len(cached_items) > 1 else None
            
            # Close SQLite memory connection
            if memory and hasattr(memory, 'conn') and memory.conn:
                memory.conn.close()
        except Exception as e:
            logger.debug(f"Error cleaning up {cache_name} cache for {cache_key}: {e}")


def _create_executor_from_cache(cache: Dict[str, tuple], cache_key: str, 
                                client, agent_def: Dict, toolkit_config_path: Optional[str],
                                config, model: Optional[str], temperature: Optional[float],
                                max_tokens: Optional[int], work_dir: Optional[str]) -> tuple:
    """Get or create executor from cache.
    
    Args:
        cache: Executor cache dictionary
        cache_key: Key for caching
        client: API client
        agent_def: Agent definition
        toolkit_config_path: Path to toolkit config
        config: CLI configuration
        model: Model override
        temperature: Temperature override
        max_tokens: Max tokens override
        work_dir: Working directory
        
    Returns:
        Tuple of (agent_executor, memory, mcp_session_manager)
    """
    if cache_key in cache:
        return cache[cache_key]
    
    # Create new executor
    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3
    
    memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
    toolkit_config_tuple = (toolkit_config_path,) if toolkit_config_path else ()
    
    agent_executor, mcp_session_manager, _, _, _, _, _ = _setup_local_agent_executor(
        client, agent_def, toolkit_config_tuple, config, model, temperature, 
        max_tokens, memory, work_dir
    )
    
    # Cache the executor
    cached_tuple = (agent_executor, memory, mcp_session_manager)
    cache[cache_key] = cached_tuple
    return cached_tuple


def _print_validation_diagnostics(validation_output: str) -> None:
    """Print diagnostic information for validation output.
    
    Args:
        validation_output: The validation output to diagnose
    """
    console.print(f"\n[bold red]🔍 Diagnostic Information:[/bold red]")
    console.print(f"[dim]Output length: {len(validation_output)} characters[/dim]")
    
    # Check for key JSON elements
    has_json = '{' in validation_output and '}' in validation_output
    has_fields = 'test_number' in validation_output and 'steps' in validation_output
    
    console.print(f"[dim]Has JSON structure: {has_json}[/dim]")
    console.print(f"[dim]Has required fields: {has_fields}[/dim]")
    
    # Show relevant excerpt
    if len(validation_output) > 400:
        console.print(f"\n[red]First 200 chars:[/red] [dim]{validation_output[:200]}[/dim]")
        console.print(f"[red]Last 200 chars:[/red] [dim]{validation_output[-200:]}[/dim]")
    else:
        console.print(f"\n[red]Full output:[/red] [dim]{validation_output}[/dim]")


def _get_alita_system_prompt(config) -> str:
    """
    Get the Alita system prompt from user config or fallback to default.
    
    Checks for $ALITA_DIR/agents/default.agent.md first, then falls back
    to the built-in DEFAULT_PROMPT.
    
    Returns:
        The system prompt string for Alita
    """
    from .agent.default import DEFAULT_PROMPT
    
    # Check for user-customized prompt
    custom_prompt_path = Path(config.agents_dir) / 'default.agent.md'
    
    if custom_prompt_path.exists():
        try:
            content = custom_prompt_path.read_text(encoding='utf-8')
            # Parse the agent.md file - extract system_prompt from frontmatter or use content
            if content.startswith('---'):
                # Has YAML frontmatter, try to parse
                try:
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        body = parts[2].strip()
                        # Use system_prompt from frontmatter if present, otherwise use body
                        return frontmatter.get('system_prompt', body) if frontmatter else body
                except Exception:
                    pass
            # No frontmatter or parsing failed, use entire content as prompt
            return content.strip()
        except Exception as e:
            logger.debug(f"Failed to load custom Alita prompt from {custom_prompt_path}: {e}")
    
    return DEFAULT_PROMPT


def _get_inventory_system_prompt(config) -> str:
    """
    Get the Inventory agent system prompt from user config or fallback to default.
    
    Checks for $ALITA_DIR/agents/inventory.agent.md first, then falls back
    to the default prompt with inventory-specific instructions.
    
    Returns:
        The system prompt string for Inventory agent
    """
    from .agent.default import DEFAULT_PROMPT
    
    # Check for user-customized prompt
    custom_prompt_path = Path(config.agents_dir) / 'inventory.agent.md'
    
    if custom_prompt_path.exists():
        try:
            content = custom_prompt_path.read_text(encoding='utf-8')
            # Parse the agent.md file - extract system_prompt from frontmatter or use content
            if content.startswith('---'):
                try:
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        body = parts[2].strip()
                        return frontmatter.get('system_prompt', body) if frontmatter else body
                except Exception:
                    pass
            return content.strip()
        except Exception as e:
            logger.debug(f"Failed to load custom Inventory prompt from {custom_prompt_path}: {e}")
    
    # Use default prompt + inventory toolkit instructions
    inventory_context = """

## Inventory Knowledge Graph

You have access to the Inventory toolkit for querying a knowledge graph of software entities and relationships.
Use these tools to help users understand their codebase:

- **search_entities**: Find entities by name, type, or path patterns
- **get_entity**: Get full details of a specific entity
- **get_relationships**: Find relationships from/to an entity
- **impact_analysis**: Analyze what depends on an entity (useful for change impact)
- **get_graph_stats**: Get statistics about the knowledge graph

When answering questions about the codebase, use these tools to provide accurate, citation-backed answers.
"""
    return DEFAULT_PROMPT + inventory_context


def _resolve_inventory_path(path: str, work_dir: Optional[str] = None) -> Optional[str]:
    """
    Resolve an inventory/knowledge graph file path.
    
    Tries locations in order:
    1. Absolute path
    2. Relative to current working directory (or work_dir if provided)
    3. Relative to .alita/inventory/ in current directory
    4. Relative to .alita/inventory/ in work_dir (if different)
    
    Args:
        path: The path to resolve (can be relative or absolute)
        work_dir: Optional workspace directory to check
        
    Returns:
        Absolute path to the file if found, None otherwise
    """
    # Expand user home directory
    path = str(Path(path).expanduser())
    
    # Try absolute path first
    if Path(path).is_absolute() and Path(path).exists():
        return str(Path(path).resolve())
    
    # Try relative to current working directory
    cwd = Path.cwd()
    cwd_path = cwd / path
    if cwd_path.exists():
        return str(cwd_path.resolve())
    
    # Try .alita/inventory/ in current directory
    alita_inventory_path = cwd / '.alita' / 'inventory' / path
    if alita_inventory_path.exists():
        return str(alita_inventory_path.resolve())
    
    # If work_dir is different from cwd, try there too
    if work_dir:
        work_path = Path(work_dir)
        if work_path != cwd:
            # Try relative to work_dir
            work_rel_path = work_path / path
            if work_rel_path.exists():
                return str(work_rel_path.resolve())
            
            # Try .alita/inventory/ in work_dir
            work_alita_path = work_path / '.alita' / 'inventory' / path
            if work_alita_path.exists():
                return str(work_alita_path.resolve())
    
    return None


def _build_inventory_config(path: str, work_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Build an inventory toolkit configuration from a file path.
    
    The toolkit name is derived from the filename (stem).
    All available tools are included.
    
    Args:
        path: Path to the knowledge graph JSON file
        work_dir: Optional workspace directory for path resolution
        
    Returns:
        Toolkit configuration dict if file found, None otherwise
    """
    # Resolve the path
    resolved_path = _resolve_inventory_path(path, work_dir)
    if not resolved_path:
        return None
    
    # Validate it's a JSON file
    if not resolved_path.endswith('.json'):
        return None
    
    # Validate file exists and is readable
    try:
        with open(resolved_path, 'r') as f:
            # Just check it's valid JSON
            json.load(f)
    except (IOError, json.JSONDecodeError):
        return None
    
    # Extract toolkit name from filename (e.g., 'alita' from 'alita.json')
    toolkit_name = Path(resolved_path).stem
    
    # Build configuration with all available tools
    from .toolkit_loader import INVENTORY_TOOLS
    
    return {
        'type': 'inventory',
        'toolkit_name': toolkit_name,
        'graph_path': resolved_path,
        'base_directory': work_dir,
        'selected_tools': INVENTORY_TOOLS,
    }


def _get_inventory_json_files(work_dir: Optional[str] = None) -> List[str]:
    """
    Get list of .json files for inventory path completion.
    
    Searches:
    1. Current working directory (*.json files)
    2. .alita/inventory/ directory (*.json files)
    3. work_dir and work_dir/.alita/inventory/ if different from cwd
    
    Args:
        work_dir: Optional workspace directory
        
    Returns:
        List of relative or display paths for completion
    """
    suggestions = []
    seen = set()
    
    cwd = Path.cwd()
    
    # Current directory .json files
    for f in cwd.glob('*.json'):
        if f.name not in seen:
            suggestions.append(f.name)
            seen.add(f.name)
    
    # .alita/inventory/ directory
    alita_inv = cwd / '.alita' / 'inventory'
    if alita_inv.exists():
        for f in alita_inv.glob('*.json'):
            display = f'.alita/inventory/{f.name}'
            if display not in seen:
                suggestions.append(display)
                seen.add(display)
    
    # work_dir if different
    if work_dir:
        work_path = Path(work_dir)
        if work_path != cwd:
            for f in work_path.glob('*.json'):
                if f.name not in seen:
                    suggestions.append(f.name)
                    seen.add(f.name)
            
            work_alita_inv = work_path / '.alita' / 'inventory'
            if work_alita_inv.exists():
                for f in work_alita_inv.glob('*.json'):
                    display = f'.alita/inventory/{f.name}'
                    if display not in seen:
                        suggestions.append(display)
                        seen.add(display)
    
    return sorted(suggestions)


def _load_mcp_tools(agent_def: Dict[str, Any], mcp_config_path: str) -> List[Dict[str, Any]]:
    """Load MCP tools from agent definition with tool-level filtering.
    
    Args:
        agent_def: Agent definition dictionary containing mcps list
        mcp_config_path: Path to mcp.json configuration file (workspace-level)
        
    Returns:
        List of toolkit configurations for MCP servers
    """
    from .mcp_loader import load_mcp_tools
    return load_mcp_tools(agent_def, mcp_config_path)


def _setup_local_agent_executor(client, agent_def: Dict[str, Any], toolkit_config: tuple,
                                config, model: Optional[str], temperature: Optional[float],
                                max_tokens: Optional[int], memory, allowed_directories: Optional[List[str]],
                                plan_state: Optional[Dict] = None):
    """Setup local agent executor with all configurations.
    
    Args:
        allowed_directories: List of allowed directories for filesystem access.
                           First directory is the primary/base directory.
    
    Returns:
        Tuple of (agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools)
    """
    # Load toolkit configs
    toolkit_configs = load_toolkit_configs(agent_def, toolkit_config)
    
    # Load MCP tools
    mcp_toolkit_configs = _load_mcp_tools(agent_def, config.mcp_config_path)
    toolkit_configs.extend(mcp_toolkit_configs)
    
    # Create LLM instance
    llm, llm_model, llm_temperature, llm_max_tokens = create_llm_instance(
        client, model, agent_def, temperature, max_tokens
    )
    
    # Add filesystem tools if directories are provided
    filesystem_tools = None
    terminal_tools = None
    if allowed_directories:
        from .tools import get_filesystem_tools, get_terminal_tools
        preset = agent_def.get('filesystem_tools_preset')
        include_tools = agent_def.get('filesystem_tools_include')
        exclude_tools = agent_def.get('filesystem_tools_exclude')
        
        # First directory is the primary base directory
        base_dir = allowed_directories[0]
        extra_dirs = allowed_directories[1:] if len(allowed_directories) > 1 else None
        filesystem_tools = get_filesystem_tools(base_dir, include_tools, exclude_tools, preset, extra_dirs)
        
        # Terminal tools use primary directory as cwd
        terminal_tools = get_terminal_tools(base_dir)
        
        tool_count = len(filesystem_tools) + len(terminal_tools)
        if len(allowed_directories) == 1:
            access_msg = f"✓ Granted filesystem & terminal access to: {base_dir} ({tool_count} tools)"
        else:
            access_msg = f"✓ Granted filesystem & terminal access to {len(allowed_directories)} directories ({tool_count} tools)"
        if preset:
            access_msg += f" [preset: {preset}]"
        if include_tools:
            access_msg += f" [include: {', '.join(include_tools)}]"
        if exclude_tools:
            access_msg += f" [exclude: {', '.join(exclude_tools)}]"
        console.print(f"[dim]{access_msg}[/dim]")
    
    # Add planning tools (always available)
    planning_tools = None
    plan_state_obj = None
    if plan_state is not None:
        from .tools import get_planning_tools, PlanState
        # Create a plan callback to update the dict when plan changes
        def plan_callback(state: PlanState):
            plan_state['title'] = state.title
            plan_state['steps'] = state.to_dict()['steps']
            plan_state['session_id'] = state.session_id
        
        # Get session_id from plan_state dict if provided
        session_id = plan_state.get('session_id')
        planning_tools, plan_state_obj = get_planning_tools(
            plan_state=None,
            plan_callback=plan_callback,
            session_id=session_id
        )
        console.print(f"[dim]✓ Planning tools enabled ({len(planning_tools)} tools) [session: {plan_state_obj.session_id}][/dim]")
    
    # Check if we have tools
    has_tools = bool(agent_def.get('tools') or toolkit_configs or filesystem_tools or terminal_tools or planning_tools)
    has_mcp = any(tc.get('toolkit_type') == 'mcp' for tc in toolkit_configs)
    
    if not has_tools:
        return None, None, llm, llm_model, filesystem_tools, terminal_tools, planning_tools
    
    # Create agent executor with or without MCP
    mcp_session_manager = None
    if has_mcp:
        # Create persistent event loop for MCP tools
        from alita_sdk.runtime.tools.llm import LLMNode
        if not hasattr(LLMNode, '_persistent_loop') or \
           LLMNode._persistent_loop is None or \
           LLMNode._persistent_loop.is_closed():
            LLMNode._persistent_loop = asyncio.new_event_loop()
            console.print("[dim]Created persistent event loop for MCP tools[/dim]")
        
        # Load MCP tools using persistent loop
        loop = LLMNode._persistent_loop
        asyncio.set_event_loop(loop)
        agent_executor, mcp_session_manager = loop.run_until_complete(
            create_agent_executor_with_mcp(
                client, agent_def, toolkit_configs,
                llm, llm_model, llm_temperature, llm_max_tokens, memory,
                filesystem_tools=filesystem_tools,
                terminal_tools=terminal_tools,
                planning_tools=planning_tools
            )
        )
    else:
        agent_executor = create_agent_executor(
            client, agent_def, toolkit_configs,
            llm, llm_model, llm_temperature, llm_max_tokens, memory,
            filesystem_tools=filesystem_tools,
            terminal_tools=terminal_tools,
            planning_tools=planning_tools
        )
    
    return agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools


def _select_model_interactive(client) -> Optional[Dict[str, Any]]:
    """
    Show interactive menu to select a model from available models.
    
    Returns:
        Selected model info dict or None if cancelled
    """
    console.print("\n🔧 [bold cyan]Select a model:[/bold cyan]\n")
    
    try:
        # Use the new get_available_models API
        models = client.get_available_models()
        if not models:
            console.print("[yellow]No models available from the platform.[/yellow]")
            return None
        
        # Build models list - API returns items[].name
        models_list = []
        for model in models:
            model_name = model.get('name')
            if model_name:
                models_list.append({
                    'name': model_name,
                    'id': model.get('id'),
                    'model_data': model
                })
        
        if not models_list:
            console.print("[yellow]No models found.[/yellow]")
            return None
        
        # Display models with numbers
        table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
        table.add_column("#", style="dim", width=4)
        table.add_column("Model", style="cyan")
        
        for i, model in enumerate(models_list, 1):
            table.add_row(str(i), model['name'])
        
        console.print(table)
        console.print(f"\n[dim]0. Cancel[/dim]")
        
        # Get user selection using styled input
        while True:
            try:
                choice = styled_selection_input("Select model number")
                
                if choice == '0':
                    return None
                
                idx = int(choice) - 1
                if 0 <= idx < len(models_list):
                    selected = models_list[idx]
                    console.print(f"✓ [green]Selected:[/green] [bold]{selected['name']}[/bold]")
                    return selected
                else:
                    console.print(f"[yellow]Invalid selection. Please enter a number between 0 and {len(models_list)}[/yellow]")
            except ValueError:
                console.print("[yellow]Please enter a valid number[/yellow]")
            except (KeyboardInterrupt, EOFError):
                return None
                
    except Exception as e:
        console.print(f"[red]Error fetching models: {e}[/red]")
        return None


def _select_mcp_interactive(config) -> Optional[Dict[str, Any]]:
    """
    Show interactive menu to select an MCP server from mcp.json.
    
    Returns:
        Selected MCP server config dict or None if cancelled
    """
    from .mcp_loader import load_mcp_config
    
    console.print("\n🔌 [bold cyan]Select an MCP server to add:[/bold cyan]\n")
    
    mcp_config = load_mcp_config(config.mcp_config_path)
    mcp_servers = mcp_config.get('mcpServers', {})
    
    if not mcp_servers:
        console.print(f"[yellow]No MCP servers found in {config.mcp_config_path}[/yellow]")
        return None
    
    servers_list = list(mcp_servers.items())
    
    # Display servers with numbers
    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("#", style="dim", width=4)
    table.add_column("Server", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Command/URL", style="dim")
    
    for i, (name, server_config) in enumerate(servers_list, 1):
        server_type = server_config.get('type', 'stdio')
        cmd_or_url = server_config.get('url') or server_config.get('command', '')
        table.add_row(str(i), name, server_type, cmd_or_url[:40])
    
    console.print(table)
    console.print(f"\n[dim]0. Cancel[/dim]")
    
    # Get user selection using styled input
    while True:
        try:
            choice = styled_selection_input("Select MCP server number")
            
            if choice == '0':
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(servers_list):
                name, server_config = servers_list[idx]
                console.print(f"✓ [green]Selected:[/green] [bold]{name}[/bold]")
                return {'name': name, 'config': server_config}
            else:
                console.print(f"[yellow]Invalid selection. Please enter a number between 0 and {len(servers_list)}[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a valid number[/yellow]")
        except (KeyboardInterrupt, EOFError):
            return None


def _select_toolkit_interactive(config) -> Optional[Dict[str, Any]]:
    """
    Show interactive menu to select a toolkit from $ALITA_DIR/tools.
    
    Returns:
        Selected toolkit config dict or None if cancelled
    """
    console.print("\n🧰 [bold cyan]Select a toolkit to add:[/bold cyan]\n")
    
    tools_dir = Path(config.tools_dir)
    
    if not tools_dir.exists():
        console.print(f"[yellow]Tools directory not found: {tools_dir}[/yellow]")
        return None
    
    # Find all toolkit config files
    toolkit_files = []
    for pattern in ['*.json', '*.yaml', '*.yml']:
        toolkit_files.extend(tools_dir.glob(pattern))
    
    if not toolkit_files:
        console.print(f"[yellow]No toolkit configurations found in {tools_dir}[/yellow]")
        return None
    
    # Load toolkit info
    toolkits_list = []
    for file_path in toolkit_files:
        try:
            config_data = load_toolkit_config(str(file_path))
            toolkits_list.append({
                'file': str(file_path),
                'name': config_data.get('toolkit_name') or config_data.get('name') or file_path.stem,
                'type': config_data.get('toolkit_type') or config_data.get('type', 'unknown'),
                'config': config_data
            })
        except Exception as e:
            logger.debug(f"Failed to load toolkit config {file_path}: {e}")
    
    if not toolkits_list:
        console.print(f"[yellow]No valid toolkit configurations found in {tools_dir}[/yellow]")
        return None
    
    # Display toolkits with numbers
    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("#", style="dim", width=4)
    table.add_column("Toolkit", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("File", style="dim")
    
    for i, toolkit in enumerate(toolkits_list, 1):
        table.add_row(str(i), toolkit['name'], toolkit['type'], Path(toolkit['file']).name)
    
    console.print(table)
    console.print(f"\n[dim]0. Cancel[/dim]")
    
    # Get user selection using styled input
    while True:
        try:
            choice = styled_selection_input("Select toolkit number")
            
            if choice == '0':
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(toolkits_list):
                selected = toolkits_list[idx]
                console.print(f"✓ [green]Selected:[/green] [bold]{selected['name']}[/bold]")
                return selected
            else:
                console.print(f"[yellow]Invalid selection. Please enter a number between 0 and {len(toolkits_list)}[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a valid number[/yellow]")
        except (KeyboardInterrupt, EOFError):
            return None


def _list_available_toolkits(config) -> List[str]:
    """
    List names of all available toolkits in $ALITA_DIR/tools.
    
    Returns:
        List of toolkit names
    """
    tools_dir = Path(config.tools_dir)
    
    if not tools_dir.exists():
        return []
    
    toolkit_names = []
    for pattern in ['*.json', '*.yaml', '*.yml']:
        for file_path in tools_dir.glob(pattern):
            try:
                config_data = load_toolkit_config(str(file_path))
                name = config_data.get('toolkit_name') or config_data.get('name') or file_path.stem
                toolkit_names.append(name)
            except Exception:
                pass
    
    return toolkit_names


def _find_toolkit_by_name(config, toolkit_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a toolkit by name in $ALITA_DIR/tools.
    
    Args:
        config: CLI configuration
        toolkit_name: Name of the toolkit to find (case-insensitive)
        
    Returns:
        Toolkit config dict or None if not found
    """
    tools_dir = Path(config.tools_dir)
    
    if not tools_dir.exists():
        return None
    
    toolkit_name_lower = toolkit_name.lower()
    
    for pattern in ['*.json', '*.yaml', '*.yml']:
        for file_path in tools_dir.glob(pattern):
            try:
                config_data = load_toolkit_config(str(file_path))
                name = config_data.get('toolkit_name') or config_data.get('name') or file_path.stem
                
                # Match by name (case-insensitive) or file stem
                if name.lower() == toolkit_name_lower or file_path.stem.lower() == toolkit_name_lower:
                    return {
                        'file': str(file_path),
                        'name': name,
                        'type': config_data.get('toolkit_type') or config_data.get('type', 'unknown'),
                        'config': config_data
                    }
            except Exception:
                pass
    
    return None


def _select_agent_interactive(client, config) -> Optional[str]:
    """
    Show interactive menu to select an agent from platform and local agents.
    
    Returns:
        Agent source (name/id for platform, file path for local, '__direct__' for direct chat,
        '__inventory__' for inventory agent) or None if cancelled
    """
    from .config import CLIConfig
    
    console.print("\n🤖 [bold cyan]Select an agent to chat with:[/bold cyan]\n")
    
    # Built-in agents
    console.print(f"1. [[bold]💬 Alita[/bold]] [cyan]Chat directly with LLM (no agent)[/cyan]")
    console.print(f"   [dim]Direct conversation with the model without agent configuration[/dim]")
    console.print(f"2. [[bold]📊 Inventory[/bold]] [cyan]Knowledge graph builder agent[/cyan]")
    console.print(f"   [dim]Build inventories from connected toolkits (use --toolkit-config to add sources)[/dim]")
    
    agents_list = []
    
    # Load platform agents
    try:
        platform_agents = client.get_list_of_apps()
        for agent in platform_agents:
            agents_list.append({
                'type': 'platform',
                'name': agent['name'],
                'source': agent['name'],
                'description': agent.get('description', '')[:60]
            })
    except Exception as e:
        logger.debug(f"Failed to load platform agents: {e}")
    
    # Load local agents
    agents_dir = config.agents_dir
    search_dir = Path(agents_dir)
    
    if search_dir.exists():
        for pattern in ['*.agent.md', '*.agent.yaml', '*.agent.yml', '*.agent.json']:
            for file_path in search_dir.rglob(pattern):
                try:
                    agent_def = load_agent_definition(str(file_path))
                    agents_list.append({
                        'type': 'local',
                        'name': agent_def.get('name', file_path.stem),
                        'source': str(file_path),
                        'description': agent_def.get('description', '')[:60]
                    })
                except Exception as e:
                    logger.debug(f"Failed to load {file_path}: {e}")
    
    # Display agents with numbers using rich (starting from 3 since 1-2 are built-in)
    for i, agent in enumerate(agents_list, 3):
        agent_type = "📦 Platform" if agent['type'] == 'platform' else "📁 Local"
        console.print(f"{i}. [[bold]{agent_type}[/bold]] [cyan]{agent['name']}[/cyan]")
        if agent['description']:
            console.print(f"   [dim]{agent['description']}[/dim]")
    
    console.print(f"\n[dim]0. Cancel[/dim]")
    
    # Get user selection using styled input
    while True:
        try:
            choice = styled_selection_input("Select agent number")
            
            if choice == '0':
                return None
            
            if choice == '1':
                console.print(f"✓ [green]Selected:[/green] [bold]Alita[/bold]")
                return '__direct__'
            
            if choice == '2':
                console.print(f"✓ [green]Selected:[/green] [bold]Inventory[/bold]")
                return '__inventory__'
            
            idx = int(choice) - 3  # Offset by 3 since 1-2 are built-in agents
            if 0 <= idx < len(agents_list):
                selected = agents_list[idx]
                console.print(f"✓ [green]Selected:[/green] [bold]{selected['name']}[/bold]")
                return selected['source']
            else:
                console.print(f"[yellow]Invalid selection. Please enter a number between 0 and {len(agents_list) + 2}[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a valid number[/yellow]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled.[/dim]")
            return None


@click.group()
def agent():
    """Agent testing and interaction commands."""
    pass


@agent.command('list')
@click.option('--local', is_flag=True, help='List local agent definition files')
@click.option('--directory', default=None, help='Directory to search for local agents (defaults to AGENTS_DIR from .env)')
@click.pass_context
def agent_list(ctx, local: bool, directory: Optional[str]):
    """
    List available agents.
    
    By default, lists agents from the platform.
    Use --local to list agent definition files in the local directory.
    """
    formatter = ctx.obj['formatter']
    config = ctx.obj['config']
    
    try:
        if local:
            # List local agent definition files
            if directory is None:
                directory = config.agents_dir
            search_dir = Path(directory)
            
            if not search_dir.exists():
                console.print(f"[red]Directory not found: {directory}[/red]")
                return
            
            agents = []
            
            # Find agent definition files
            for pattern in ['*.agent.md', '*.agent.yaml', '*.agent.yml', '*.agent.json']:
                for file_path in search_dir.rglob(pattern):
                    try:
                        agent_def = load_agent_definition(str(file_path))
                        # Use relative path if already relative, otherwise make it relative to cwd
                        try:
                            display_path = str(file_path.relative_to(Path.cwd()))
                        except ValueError:
                            display_path = str(file_path)
                        
                        agents.append({
                            'name': agent_def.get('name', file_path.stem),
                            'file': display_path,
                            'description': agent_def.get('description', '')[:80]
                        })
                    except Exception as e:
                        logger.debug(f"Failed to load {file_path}: {e}")
            
            if not agents:
                console.print(f"\n[yellow]No agent definition files found in {directory}[/yellow]")
                return
            
            # Display local agents in a table
            table = Table(
                title=f"Local Agent Definitions in {directory}",
                show_header=True,
                header_style="bold cyan",
                border_style="cyan",
                box=box.ROUNDED
            )
            table.add_column("Name", style="bold cyan", no_wrap=True)
            table.add_column("File", style="dim")
            table.add_column("Description", style="white")
            
            for agent_info in sorted(agents, key=lambda x: x['name']):
                table.add_row(
                    agent_info['name'],
                    agent_info['file'],
                    agent_info['description'] or "-"
                )
            
            console.print("\n")
            console.print(table)
            console.print(f"\n[green]Total: {len(agents)} local agents[/green]")
            
        else:
            # List platform agents
            client = get_client(ctx)
            
            agents = client.get_list_of_apps()
            
            if formatter.__class__.__name__ == 'JSONFormatter':
                click.echo(formatter._dump({'agents': agents, 'total': len(agents)}))
            else:
                table = Table(
                    title="Available Platform Agents",
                    show_header=True,
                    header_style="bold cyan",
                    border_style="cyan",
                    box=box.ROUNDED
                )
                table.add_column("ID", style="yellow", no_wrap=True)
                table.add_column("Name", style="bold cyan")
                table.add_column("Description", style="white")
                
                for agent_info in agents:
                    table.add_row(
                        str(agent_info['id']),
                        agent_info['name'],
                        agent_info.get('description', '')[:80] or "-"
                    )
                
                console.print("\n")
                console.print(table)
                console.print(f"\n[green]Total: {len(agents)} agents[/green]")
        
    except Exception as e:
        logger.exception("Failed to list agents")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()


@agent.command('show')
@click.argument('agent_source')
@click.option('--version', help='Agent version (for platform agents)')
@click.pass_context
def agent_show(ctx, agent_source: str, version: Optional[str]):
    """
    Show agent details.
    
    AGENT_SOURCE can be:
    - Platform agent ID or name (e.g., "123" or "my-agent")
    - Path to local agent file (e.g., ".github/agents/sdk-dev.agent.md")
    """
    formatter = ctx.obj['formatter']
    
    try:
        # Check if it's a file path
        if Path(agent_source).exists():
            # Local agent file
            agent_def = load_agent_definition(agent_source)
            
            if formatter.__class__.__name__ == 'JSONFormatter':
                click.echo(formatter._dump(agent_def))
            else:
                # Create details panel
                details = Text()
                details.append("File: ", style="bold")
                details.append(f"{agent_source}\n", style="cyan")
                
                if agent_def.get('description'):
                    details.append("\nDescription: ", style="bold")
                    details.append(f"{agent_def['description']}\n", style="white")
                
                if agent_def.get('model'):
                    details.append("Model: ", style="bold")
                    details.append(f"{agent_def['model']}\n", style="cyan")
                
                if agent_def.get('tools'):
                    details.append("Tools: ", style="bold")
                    details.append(f"{', '.join(agent_def['tools'])}\n", style="cyan")
                
                if agent_def.get('temperature') is not None:
                    details.append("Temperature: ", style="bold")
                    details.append(f"{agent_def['temperature']}\n", style="cyan")
                
                panel = Panel(
                    details,
                    title=f"Local Agent: {agent_def.get('name', 'Unknown')}",
                    title_align="left",
                    border_style="cyan",
                    box=box.ROUNDED
                )
                console.print("\n")
                console.print(panel)
                
                if agent_def.get('system_prompt'):
                    console.print("\n[bold]System Prompt:[/bold]")
                    console.print(Panel(agent_def['system_prompt'][:500] + "...", border_style="dim", box=box.ROUNDED))
        
        else:
            # Platform agent
            client = get_client(ctx)
            
            # Try to find agent by ID or name
            agents = client.get_list_of_apps()
            
            agent = None
            try:
                agent_id = int(agent_source)
                agent = next((a for a in agents if a['id'] == agent_id), None)
            except ValueError:
                agent = next((a for a in agents if a['name'] == agent_source), None)
            
            if not agent:
                raise click.ClickException(f"Agent '{agent_source}' not found")
            
            # Get details
            details = client.get_app_details(agent['id'])
            
            if formatter.__class__.__name__ == 'JSONFormatter':
                click.echo(formatter._dump(details))
            else:
                # Create platform agent details panel
                content = Text()
                content.append("ID: ", style="bold")
                content.append(f"{details['id']}\n", style="yellow")
                
                if details.get('description'):
                    content.append("\nDescription: ", style="bold")
                    content.append(f"{details['description']}\n", style="white")
                
                panel = Panel(
                    content,
                    title=f"Agent: {details['name']}",
                    title_align="left",
                    border_style="cyan",
                    box=box.ROUNDED
                )
                console.print("\n")
                console.print(panel)
                
                # Display versions in a table
                if details.get('versions'):
                    console.print("\n[bold]Versions:[/bold]")
                    versions_table = Table(box=box.ROUNDED, border_style="dim")
                    versions_table.add_column("Name", style="cyan")
                    versions_table.add_column("ID", style="yellow")
                    for ver in details.get('versions', []):
                        versions_table.add_row(ver['name'], str(ver['id']))
                    console.print(versions_table)
    
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to show agent details")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()


@agent.command('chat')
@click.argument('agent_source', required=False)
@click.option('--version', help='Agent version (for platform agents)')
@click.option('--toolkit-config', multiple=True, type=click.Path(exists=True),
              help='Toolkit configuration files (can specify multiple)')
@click.option('--inventory', 'inventory_path', type=str,
              help='Load inventory/knowledge graph from JSON file (e.g., alita.json or .alita/inventory/alita.json)')
@click.option('--thread-id', help='Continue existing conversation thread')
@click.option('--model', help='Override LLM model')
@click.option('--temperature', type=float, help='Override temperature')
@click.option('--max-tokens', type=int, help='Override max tokens')
@click.option('--dir', 'work_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='Grant agent filesystem access to this directory')
@click.option('--verbose', '-v', type=click.Choice(['quiet', 'default', 'debug']), default='default',
              help='Output verbosity level: quiet (final output only), default (tool calls + outputs), debug (all including LLM calls)')
@click.option('--recursion-limit', type=int, default=50,
              help='Maximum number of tool execution steps per turn')
@click.pass_context
def agent_chat(ctx, agent_source: Optional[str], version: Optional[str], 
               toolkit_config: tuple, inventory_path: Optional[str], thread_id: Optional[str],
               model: Optional[str], temperature: Optional[float], 
               max_tokens: Optional[int], work_dir: Optional[str],
               verbose: str, recursion_limit: Optional[int]):
    """Start interactive chat with an agent.
    
    \b
    Examples:
      alita chat                      # Interactive agent selection
      alita chat my-agent             # Chat with platform agent
      alita chat ./agent.md           # Chat with local agent file
      alita chat --inventory alita.json
      alita chat my-agent --dir ./src
      alita chat my-agent --thread-id abc123
      alita chat my-agent -v quiet    # Hide tool calls
      alita chat my-agent -v debug    # Show all LLM calls
      alita chat __inventory__ --toolkit-config jira.json
    """
    formatter = ctx.obj['formatter']
    config = ctx.obj['config']
    client = get_client(ctx)
    
    # Setup verbose level
    show_verbose = verbose != 'quiet'
    debug_mode = verbose == 'debug'
    
    try:
        # If no agent specified, start with direct chat by default
        if not agent_source:
            agent_source = '__direct__'
        
        # Check for built-in agent modes
        is_direct = agent_source == '__direct__'
        is_inventory = agent_source == '__inventory__'
        is_builtin = is_direct or is_inventory
        is_local = not is_builtin and Path(agent_source).exists()
        
        # Get defaults from config
        default_model = config.default_model or 'gpt-4o'
        default_temperature = config.default_temperature if config.default_temperature is not None else 0.1
        default_max_tokens = config.default_max_tokens or 4096
        
        # Initialize variables for dynamic updates
        current_model = model
        current_temperature = temperature
        current_max_tokens = max_tokens
        added_mcp_configs = []
        added_toolkit_configs = list(toolkit_config) if toolkit_config else []
        mcp_session_manager = None
        llm = None
        agent_executor = None
        agent_def = {}
        filesystem_tools = None
        terminal_tools = None
        planning_tools = None
        plan_state = None
        
        # Handle --inventory option: add inventory toolkit config at startup
        if inventory_path:
            inventory_config = _build_inventory_config(inventory_path, work_dir)
            if inventory_config:
                added_toolkit_configs.append(inventory_config)
                console.print(f"[dim]✓ Loading inventory: {inventory_config['toolkit_name']} ({inventory_config['graph_path']})[/dim]")
            else:
                console.print(f"[yellow]Warning: Inventory file not found: {inventory_path}[/yellow]")
                console.print("[dim]Searched in current directory and .alita/inventory/[/dim]")
        
        # Approval mode: 'always' (confirm each tool), 'auto' (no confirmation), 'yolo' (no safety checks)
        approval_mode = 'always'
        allowed_directories = [work_dir] if work_dir else []  # Track allowed directories for /dir command
        current_agent_file = agent_source if is_local else None  # Track agent file for /reload command
        
        if is_direct:
            # Direct chat mode - no agent, just LLM with Alita instructions
            agent_name = "Alita"
            agent_type = "Direct LLM"
            alita_prompt = _get_alita_system_prompt(config)
            agent_def = {
                'model': model or default_model,
                'temperature': temperature if temperature is not None else default_temperature,
                'max_tokens': max_tokens or default_max_tokens,
                'system_prompt': alita_prompt
            }
        elif is_inventory:
            # Inventory agent mode - knowledge graph builder with inventory toolkit
            agent_name = "Inventory"
            agent_type = "Built-in Agent"
            inventory_prompt = _get_inventory_system_prompt(config)
            agent_def = {
                'name': 'inventory-agent',
                'model': model or default_model,
                'temperature': temperature if temperature is not None else 0.3,
                'max_tokens': max_tokens or default_max_tokens,
                'system_prompt': inventory_prompt,
                # Include inventory toolkit by default
                'toolkit_configs': [
                    {'type': 'inventory', 'graph_path': './knowledge_graph.json'}
                ]
            }
        elif is_local:
            agent_def = load_agent_definition(agent_source)
            agent_name = agent_def.get('name', Path(agent_source).stem)
            agent_type = "Local Agent"
        else:
            # Platform agent - find it
            agents = client.get_list_of_apps()
            agent = None
            
            try:
                agent_id = int(agent_source)
                agent = next((a for a in agents if a['id'] == agent_id), None)
            except ValueError:
                agent = next((a for a in agents if a['name'] == agent_source), None)
            
            if not agent:
                raise click.ClickException(f"Agent '{agent_source}' not found")
            
            agent_name = agent['name']
            agent_type = "Platform Agent"
        
        # Get model and temperature for welcome banner
        llm_model_display = current_model or agent_def.get('model', default_model)
        llm_temperature_display = current_temperature if current_temperature is not None else agent_def.get('temperature', default_temperature)
        
        # Print nice welcome banner
        print_welcome(agent_name, llm_model_display, llm_temperature_display, approval_mode)
        
        # Initialize conversation
        chat_history = []
        
        # Initialize session for persistence (memory + plan)
        from .tools import generate_session_id, create_session_memory, save_session_metadata, to_portable_path
        current_session_id = generate_session_id()
        plan_state = {'session_id': current_session_id}
        
        # Create persistent memory for agent (stored in session directory)
        memory = create_session_memory(current_session_id)
        
        # Save session metadata with agent source for session resume
        agent_source_portable = to_portable_path(current_agent_file) if current_agent_file else None
        # Filter out transient inventory configs (dicts) - only save file paths
        serializable_toolkit_configs = [tc for tc in added_toolkit_configs if isinstance(tc, str)]
        # Extract inventory graph path if present
        inventory_graph = None
        for tc in added_toolkit_configs:
            if isinstance(tc, dict) and tc.get('type') == 'inventory':
                inventory_graph = tc.get('graph_path')
                break
        save_session_metadata(current_session_id, {
            'agent_name': agent_name,
            'agent_type': agent_type if 'agent_type' in dir() else 'Direct LLM',
            'agent_source': agent_source_portable,
            'model': llm_model_display,
            'temperature': llm_temperature_display,
            'work_dir': work_dir,
            'is_direct': is_direct,
            'is_local': is_local,
            'is_inventory': is_inventory,
            'added_toolkit_configs': serializable_toolkit_configs,
            'inventory_graph': inventory_graph,
            'added_mcps': [m if isinstance(m, str) else m.get('name') for m in agent_def.get('mcps', [])],
        })
        console.print(f"[dim]Session: {current_session_id}[/dim]")
        
        # Initialize context manager for chat history management
        context_config = config.context_management
        ctx_manager = CLIContextManager(
            session_id=current_session_id,
            max_context_tokens=context_config.get('max_context_tokens', 8000),
            preserve_recent=context_config.get('preserve_recent_messages', 5),
            pruning_method=context_config.get('pruning_method', 'oldest_first'),
            enable_summarization=context_config.get('enable_summarization', True),
            summary_trigger_ratio=context_config.get('summary_trigger_ratio', 0.8),
            summaries_limit=context_config.get('summaries_limit_count', 5),
            llm=None  # Will be set after LLM creation
        )
        
        # Purge old sessions on startup (cleanup task)
        try:
            purge_context_sessions(
                sessions_dir=config.sessions_dir,
                max_age_days=context_config.get('session_max_age_days', 30),
                max_sessions=context_config.get('max_sessions', 100)
            )
        except Exception as e:
            logger.debug(f"Session cleanup failed: {e}")
        
        # Create agent executor
        if is_direct or is_local or is_inventory:
            # Setup local agent executor (handles all config, tools, MCP, etc.)
            try:
                agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                    client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, work_dir, plan_state
                )
            except Exception:
                return
        else:
            # Platform agent
            details = client.get_app_details(agent['id'])
            
            if version:
                version_obj = next((v for v in details['versions'] if v['name'] == version), None)
                if not version_obj:
                    raise click.ClickException(f"Version '{version}' not found")
                version_id = version_obj['id']
            else:
                # Use first version
                version_id = details['versions'][0]['id']
            
            # Display configuration
            console.print()
            console.print("✓ [green]Connected to platform agent[/green]")
            console.print()
            
            agent_executor = client.application(
                application_id=agent['id'],
                application_version_id=version_id,
                memory=memory,
                chat_history=chat_history
            )
            llm = None  # Platform agents don't use direct LLM
        
        # Set LLM on context manager for summarization
        if llm is not None:
            ctx_manager.llm = llm
        
        # Initialize input handler for readline support
        input_handler = get_input_handler()
        
        # Set up toolkit names callback for tab completion
        from .input_handler import set_toolkit_names_callback, set_inventory_files_callback
        set_toolkit_names_callback(lambda: _list_available_toolkits(config))
        
        # Set up inventory files callback for /inventory tab completion
        set_inventory_files_callback(lambda: _get_inventory_json_files(allowed_directories[0] if allowed_directories else None))
        
        # Interactive chat loop
        while True:
            try:
                # Get context info for the UI indicator
                context_info = ctx_manager.get_context_info()
                
                # Get input with styled prompt (prompt is part of input() for proper readline handling)
                user_input = styled_input(context_info=context_info).strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['exit', 'quit']:
                    # Save final session state before exiting
                    try:
                        from .tools import update_session_metadata, to_portable_path
                        update_session_metadata(current_session_id, {
                            'agent_source': to_portable_path(current_agent_file) if current_agent_file else None,
                            'model': current_model or llm_model_display,
                            'temperature': current_temperature if current_temperature is not None else llm_temperature_display,
                            'allowed_directories': allowed_directories,
                            'added_toolkit_configs': list(added_toolkit_configs),
                            'added_mcps': [m if isinstance(m, str) else m.get('name') for m in agent_def.get('mcps', [])],
                        })
                    except Exception as e:
                        logger.debug(f"Failed to save session state on exit: {e}")
                    console.print("\n[bold cyan]👋 Goodbye![/bold cyan]\n")
                    break
                
                if user_input == '/clear':
                    chat_history = []
                    ctx_manager.clear()
                    console.print("[green]✓ Conversation history cleared.[/green]")
                    continue
                
                if user_input == '/history':
                    if not chat_history:
                        console.print("[yellow]No conversation history yet.[/yellow]")
                    else:
                        console.print("\n[bold cyan]── Conversation History ──[/bold cyan]")
                        for i, msg in enumerate(chat_history, 1):
                            role = msg.get('role', 'unknown')
                            content = msg.get('content', '')
                            role_color = 'blue' if role == 'user' else 'green'
                            included_marker = "" if ctx_manager.is_message_included(i - 1) else " [dim](pruned)[/dim]"
                            console.print(f"\n[bold {role_color}]{i}. {role.upper()}:[/bold {role_color}] {content[:100]}...{included_marker}")
                    continue
                
                if user_input == '/save':
                    console.print("[yellow]Save to file (default: conversation.json):[/yellow] ", end="")
                    filename = input().strip()
                    filename = filename or "conversation.json"
                    with open(filename, 'w') as f:
                        json.dump({'history': chat_history}, f, indent=2)
                    console.print(f"[green]✓ Conversation saved to {filename}[/green]")
                    continue
                
                if user_input == '/help':
                    print_help()
                    continue
                
                # /model command - switch model
                if user_input == '/model':
                    if not (is_direct or is_local):
                        console.print("[yellow]Model switching is only available for local agents and direct chat.[/yellow]")
                        continue
                    
                    selected_model = _select_model_interactive(client)
                    if selected_model:
                        current_model = selected_model['name']
                        agent_def['model'] = current_model
                        
                        # Recreate LLM and agent executor - use session memory to preserve history
                        from .tools import create_session_memory, update_session_metadata
                        memory = create_session_memory(current_session_id)
                        try:
                            agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                            )
                            # Persist model change to session
                            update_session_metadata(current_session_id, {
                                'model': current_model,
                                'temperature': current_temperature if current_temperature is not None else agent_def.get('temperature', 0.7)
                            })
                            console.print(Panel(
                                f"[cyan]ℹ Model switched to [bold]{current_model}[/bold]. Agent state reset, chat history preserved.[/cyan]",
                                border_style="cyan",
                                box=box.ROUNDED
                            ))
                        except Exception as e:
                            console.print(f"[red]Error switching model: {e}[/red]")
                    continue
                
                # /reload command - reload agent definition from file
                if user_input == '/reload':
                    if not is_local:
                        if is_direct or is_inventory:
                            console.print("[yellow]Cannot reload built-in agent mode - no agent file to reload.[/yellow]")
                        else:
                            console.print("[yellow]Reload is only available for local agents (file-based).[/yellow]")
                        continue
                    
                    if not current_agent_file or not Path(current_agent_file).exists():
                        console.print("[red]Agent file not found. Cannot reload.[/red]")
                        continue
                    
                    try:
                        # Reload agent definition from file
                        new_agent_def = load_agent_definition(current_agent_file)
                        
                        # Preserve runtime additions (MCPs, tools added via commands)
                        if 'mcps' in agent_def and agent_def['mcps']:
                            # Merge MCPs: file MCPs + runtime added MCPs
                            file_mcps = new_agent_def.get('mcps', [])
                            for mcp in agent_def['mcps']:
                                mcp_name = mcp if isinstance(mcp, str) else mcp.get('name')
                                file_mcp_names = [m if isinstance(m, str) else m.get('name') for m in file_mcps]
                                if mcp_name not in file_mcp_names:
                                    file_mcps.append(mcp)
                            new_agent_def['mcps'] = file_mcps
                        
                        # Update agent_def with new values (preserving model/temp overrides)
                        old_system_prompt = agent_def.get('system_prompt', '')
                        new_system_prompt = new_agent_def.get('system_prompt', '')
                        
                        agent_def.update(new_agent_def)
                        
                        # Restore runtime overrides
                        if current_model:
                            agent_def['model'] = current_model
                        if current_temperature is not None:
                            agent_def['temperature'] = current_temperature
                        if current_max_tokens:
                            agent_def['max_tokens'] = current_max_tokens
                        
                        # Recreate agent executor with reloaded definition
                        from .tools import create_session_memory
                        memory = create_session_memory(current_session_id)
                        agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                            client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                        )
                        
                        # Show what changed
                        prompt_changed = old_system_prompt != new_system_prompt
                        agent_name = agent_def.get('name', Path(current_agent_file).stem)
                        
                        if prompt_changed:
                            console.print(Panel(
                                f"[green]✓ Reloaded agent: [bold]{agent_name}[/bold][/green]\n"
                                f"[dim]System prompt updated ({len(new_system_prompt)} chars)[/dim]",
                                border_style="green",
                                box=box.ROUNDED
                            ))
                        else:
                            console.print(Panel(
                                f"[cyan]ℹ Reloaded agent: [bold]{agent_name}[/bold][/cyan]\n"
                                f"[dim]No changes detected in system prompt[/dim]",
                                border_style="cyan",
                                box=box.ROUNDED
                            ))
                    except Exception as e:
                        console.print(f"[red]Error reloading agent: {e}[/red]")
                    continue
                
                # /add_mcp command - add MCP server
                if user_input == '/add_mcp':
                    if not (is_direct or is_local or is_inventory):
                        console.print("[yellow]Adding MCP is only available for local agents and built-in agents.[/yellow]")
                        continue
                    
                    selected_mcp = _select_mcp_interactive(config)
                    if selected_mcp:
                        mcp_name = selected_mcp['name']
                        # Add MCP to agent definition
                        if 'mcps' not in agent_def:
                            agent_def['mcps'] = []
                        if mcp_name not in [m if isinstance(m, str) else m.get('name') for m in agent_def.get('mcps', [])]:
                            agent_def['mcps'].append(mcp_name)
                        
                        # Recreate agent executor with new MCP - use session memory to preserve history
                        from .tools import create_session_memory, update_session_metadata
                        memory = create_session_memory(current_session_id)
                        try:
                            agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                            )
                            # Persist added MCPs to session
                            update_session_metadata(current_session_id, {
                                'added_mcps': [m if isinstance(m, str) else m.get('name') for m in agent_def.get('mcps', [])]
                            })
                            console.print(Panel(
                                f"[cyan]ℹ Added MCP: [bold]{mcp_name}[/bold]. Agent state reset, chat history preserved.[/cyan]",
                                border_style="cyan",
                                box=box.ROUNDED
                            ))
                        except Exception as e:
                            console.print(f"[red]Error adding MCP: {e}[/red]")
                    continue
                
                # /add_toolkit command - add toolkit
                if user_input == '/add_toolkit' or user_input.startswith('/add_toolkit '):
                    if not (is_direct or is_local or is_inventory):
                        console.print("[yellow]Adding toolkit is only available for local agents and built-in agents.[/yellow]")
                        continue
                    
                    parts = user_input.split(maxsplit=1)
                    if len(parts) == 2:
                        # Direct toolkit selection by name
                        toolkit_name_arg = parts[1].strip()
                        selected_toolkit = _find_toolkit_by_name(config, toolkit_name_arg)
                        if not selected_toolkit:
                            console.print(f"[yellow]Toolkit '{toolkit_name_arg}' not found.[/yellow]")
                            # Show available toolkits
                            available = _list_available_toolkits(config)
                            if available:
                                console.print(f"[dim]Available toolkits: {', '.join(available)}[/dim]")
                            continue
                    else:
                        # Interactive selection
                        selected_toolkit = _select_toolkit_interactive(config)
                    
                    if selected_toolkit:
                        toolkit_name = selected_toolkit['name']
                        toolkit_file = selected_toolkit['file']
                        
                        # Add toolkit config path
                        if toolkit_file not in added_toolkit_configs:
                            added_toolkit_configs.append(toolkit_file)
                        
                        # Recreate agent executor with new toolkit - use session memory to preserve history
                        from .tools import create_session_memory, update_session_metadata
                        memory = create_session_memory(current_session_id)
                        try:
                            agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                            )
                            # Persist added toolkits to session
                            update_session_metadata(current_session_id, {
                                'added_toolkit_configs': list(added_toolkit_configs)
                            })
                            console.print(Panel(
                                f"[cyan]ℹ Added toolkit: [bold]{toolkit_name}[/bold]. Agent state reset, chat history preserved.[/cyan]",
                                border_style="cyan",
                                box=box.ROUNDED
                            ))
                        except Exception as e:
                            console.print(f"[red]Error adding toolkit: {e}[/red]")
                    continue
                
                # /rm_mcp command - remove MCP server
                if user_input == '/rm_mcp' or user_input.startswith('/rm_mcp '):
                    if not (is_direct or is_local or is_inventory):
                        console.print("[yellow]Removing MCP is only available for local agents and built-in agents.[/yellow]")
                        continue
                    
                    current_mcps = agent_def.get('mcps', [])
                    if not current_mcps:
                        console.print("[yellow]No MCP servers are currently loaded.[/yellow]")
                        continue
                    
                    # Get list of MCP names
                    mcp_names = [m if isinstance(m, str) else m.get('name') for m in current_mcps]
                    
                    parts = user_input.split(maxsplit=1)
                    if len(parts) == 2:
                        # Direct removal by name
                        mcp_name_to_remove = parts[1].strip()
                        if mcp_name_to_remove not in mcp_names:
                            console.print(f"[yellow]MCP '{mcp_name_to_remove}' not found.[/yellow]")
                            console.print(f"[dim]Loaded MCPs: {', '.join(mcp_names)}[/dim]")
                            continue
                    else:
                        # Interactive selection
                        console.print("\n🔌 [bold cyan]Remove MCP Server[/bold cyan]\n")
                        for i, name in enumerate(mcp_names, 1):
                            console.print(f"  [bold]{i}[/bold]. {name}")
                        console.print(f"  [bold]0[/bold]. [dim]Cancel[/dim]")
                        console.print()
                        
                        try:
                            choice = int(input("Select MCP to remove: ").strip())
                            if choice == 0:
                                continue
                            if 1 <= choice <= len(mcp_names):
                                mcp_name_to_remove = mcp_names[choice - 1]
                            else:
                                console.print("[yellow]Invalid selection.[/yellow]")
                                continue
                        except (ValueError, KeyboardInterrupt):
                            continue
                    
                    # Remove the MCP
                    agent_def['mcps'] = [m for m in current_mcps if (m if isinstance(m, str) else m.get('name')) != mcp_name_to_remove]
                    
                    # Recreate agent executor without the MCP
                    from .tools import create_session_memory, update_session_metadata
                    memory = create_session_memory(current_session_id)
                    try:
                        agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                            client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                        )
                        # Persist updated MCPs to session
                        update_session_metadata(current_session_id, {
                            'added_mcps': [m if isinstance(m, str) else m.get('name') for m in agent_def.get('mcps', [])]
                        })
                        console.print(Panel(
                            f"[cyan]ℹ Removed MCP: [bold]{mcp_name_to_remove}[/bold]. Agent state reset, chat history preserved.[/cyan]",
                            border_style="cyan",
                            box=box.ROUNDED
                        ))
                    except Exception as e:
                        console.print(f"[red]Error removing MCP: {e}[/red]")
                    continue
                
                # /rm_toolkit command - remove toolkit
                if user_input == '/rm_toolkit' or user_input.startswith('/rm_toolkit '):
                    if not (is_direct or is_local or is_inventory):
                        console.print("[yellow]Removing toolkit is only available for local agents and built-in agents.[/yellow]")
                        continue
                    
                    if not added_toolkit_configs:
                        console.print("[yellow]No toolkits are currently loaded.[/yellow]")
                        continue
                    
                    # Get toolkit names from config files
                    toolkit_info = []  # List of (name, file_path)
                    for toolkit_file in added_toolkit_configs:
                        try:
                            with open(toolkit_file, 'r') as f:
                                tk_config = json.load(f)
                                tk_name = tk_config.get('toolkit_name', Path(toolkit_file).stem)
                                toolkit_info.append((tk_name, toolkit_file))
                        except Exception:
                            toolkit_info.append((Path(toolkit_file).stem, toolkit_file))
                    
                    parts = user_input.split(maxsplit=1)
                    if len(parts) == 2:
                        # Direct removal by name
                        toolkit_name_to_remove = parts[1].strip()
                        matching = [(name, path) for name, path in toolkit_info if name == toolkit_name_to_remove]
                        if not matching:
                            console.print(f"[yellow]Toolkit '{toolkit_name_to_remove}' not found.[/yellow]")
                            console.print(f"[dim]Loaded toolkits: {', '.join(name for name, _ in toolkit_info)}[/dim]")
                            continue
                        toolkit_file_to_remove = matching[0][1]
                    else:
                        # Interactive selection
                        console.print("\n🔧 [bold cyan]Remove Toolkit[/bold cyan]\n")
                        for i, (name, _) in enumerate(toolkit_info, 1):
                            console.print(f"  [bold]{i}[/bold]. {name}")
                        console.print(f"  [bold]0[/bold]. [dim]Cancel[/dim]")
                        console.print()
                        
                        try:
                            choice = int(input("Select toolkit to remove: ").strip())
                            if choice == 0:
                                continue
                            if 1 <= choice <= len(toolkit_info):
                                toolkit_name_to_remove, toolkit_file_to_remove = toolkit_info[choice - 1]
                            else:
                                console.print("[yellow]Invalid selection.[/yellow]")
                                continue
                        except (ValueError, KeyboardInterrupt):
                            continue
                    
                    # Remove the toolkit
                    added_toolkit_configs.remove(toolkit_file_to_remove)
                    
                    # Recreate agent executor without the toolkit
                    from .tools import create_session_memory, update_session_metadata
                    memory = create_session_memory(current_session_id)
                    try:
                        agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                            client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                        )
                        # Persist updated toolkits to session
                        update_session_metadata(current_session_id, {
                            'added_toolkit_configs': list(added_toolkit_configs)
                        })
                        console.print(Panel(
                            f"[cyan]ℹ Removed toolkit: [bold]{toolkit_name_to_remove}[/bold]. Agent state reset, chat history preserved.[/cyan]",
                            border_style="cyan",
                            box=box.ROUNDED
                        ))
                    except Exception as e:
                        console.print(f"[red]Error removing toolkit: {e}[/red]")
                    continue
                
                # /mode command - set approval mode
                if user_input == '/mode' or user_input.startswith('/mode '):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) == 1:
                        # Show current mode and options
                        mode_info = {
                            'always': ('yellow', 'Confirm before each tool execution'),
                            'auto': ('green', 'Execute tools without confirmation'),
                            'yolo': ('red', 'No confirmations, skip safety warnings')
                        }
                        console.print("\n🔧 [bold cyan]Approval Mode:[/bold cyan]\n")
                        for mode_name, (color, desc) in mode_info.items():
                            marker = "●" if mode_name == approval_mode else "○"
                            console.print(f"  [{color}]{marker}[/{color}] [bold]{mode_name}[/bold] - {desc}")
                        console.print(f"\n[dim]Usage: /mode <always|auto|yolo>[/dim]")
                    else:
                        new_mode = parts[1].lower().strip()
                        if new_mode in ['always', 'auto', 'yolo']:
                            approval_mode = new_mode
                            mode_colors = {'always': 'yellow', 'auto': 'green', 'yolo': 'red'}
                            console.print(f"✓ [green]Mode set to[/green] [{mode_colors[new_mode]}][bold]{new_mode}[/bold][/{mode_colors[new_mode]}]")
                        else:
                            console.print(f"[yellow]Unknown mode: {new_mode}. Use: always, auto, or yolo[/yellow]")
                    continue
                
                # /dir command - manage allowed directories
                if user_input == '/dir' or user_input.startswith('/dir '):
                    parts = user_input.split()
                    
                    if len(parts) == 1:
                        # /dir - list all allowed directories
                        if allowed_directories:
                            console.print("📁 [bold cyan]Allowed directories:[/bold cyan]")
                            for i, d in enumerate(allowed_directories):
                                marker = "●" if i == 0 else "○"
                                label = " [dim](primary)[/dim]" if i == 0 else ""
                                console.print(f"  {marker} {d}{label}")
                        else:
                            console.print("[yellow]No directories allowed.[/yellow]")
                        console.print("[dim]Usage: /dir [add|rm|remove] /path/to/directory[/dim]")
                        continue
                    
                    action = parts[1].lower()
                    
                    # Handle /dir add /path or /dir /path (add is default)
                    if action in ['add', 'rm', 'remove']:
                        if len(parts) < 3:
                            console.print(f"[yellow]Missing path. Usage: /dir {action} /path/to/directory[/yellow]")
                            continue
                        dir_path = parts[2]
                    else:
                        # /dir /path - default to add
                        action = 'add'
                        dir_path = parts[1]
                    
                    dir_path = str(Path(dir_path).expanduser().resolve())
                    
                    if action == 'add':
                        if not Path(dir_path).exists():
                            console.print(f"[red]Directory not found: {dir_path}[/red]")
                            continue
                        if not Path(dir_path).is_dir():
                            console.print(f"[red]Not a directory: {dir_path}[/red]")
                            continue
                        
                        if dir_path in allowed_directories:
                            console.print(f"[yellow]Directory already allowed: {dir_path}[/yellow]")
                            continue
                        
                        allowed_directories.append(dir_path)
                        
                        # Recreate agent executor with updated directories
                        if is_direct or is_local or is_inventory:
                            from .tools import create_session_memory
                            memory = create_session_memory(current_session_id)
                            try:
                                agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                    client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                                )
                                console.print(Panel(
                                    f"[cyan]✓ Added directory: [bold]{dir_path}[/bold]\n   Total allowed: {len(allowed_directories)}[/cyan]",
                                    border_style="cyan",
                                    box=box.ROUNDED
                                ))
                            except Exception as e:
                                allowed_directories.remove(dir_path)  # Rollback
                                console.print(f"[red]Error adding directory: {e}[/red]")
                        else:
                            console.print("[yellow]Directory mounting is only available for local agents and built-in agents.[/yellow]")
                    
                    elif action in ['rm', 'remove']:
                        if dir_path not in allowed_directories:
                            console.print(f"[yellow]Directory not in allowed list: {dir_path}[/yellow]")
                            if allowed_directories:
                                console.print("[dim]Currently allowed:[/dim]")
                                for d in allowed_directories:
                                    console.print(f"[dim]  - {d}[/dim]")
                            continue
                        
                        if len(allowed_directories) == 1:
                            console.print("[yellow]Cannot remove the last directory. Use /dir add first to add another.[/yellow]")
                            continue
                        
                        allowed_directories.remove(dir_path)
                        
                        # Recreate agent executor with updated directories
                        if is_direct or is_local or is_inventory:
                            from .tools import create_session_memory
                            memory = create_session_memory(current_session_id)
                            try:
                                agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                    client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                                )
                                console.print(Panel(
                                    f"[cyan]✓ Removed directory: [bold]{dir_path}[/bold]\n   Remaining: {len(allowed_directories)}[/cyan]",
                                    border_style="cyan",
                                    box=box.ROUNDED
                                ))
                            except Exception as e:
                                allowed_directories.append(dir_path)  # Rollback
                                console.print(f"[red]Error removing directory: {e}[/red]")
                        else:
                            console.print("[yellow]Directory mounting is only available for local agents and built-in agents.[/yellow]")
                    continue
                
                # /inventory command - load inventory/knowledge graph from path
                if user_input == '/inventory' or user_input.startswith('/inventory '):
                    if not (is_direct or is_local or is_inventory):
                        console.print("[yellow]Loading inventory is only available for local agents and built-in agents.[/yellow]")
                        continue
                    
                    parts = user_input.split(maxsplit=1)
                    if len(parts) == 1:
                        # Show current inventory and available files
                        current_inventory = None
                        for tc in added_toolkit_configs:
                            if isinstance(tc, dict) and tc.get('type') == 'inventory':
                                current_inventory = tc.get('graph_path')
                                break
                            elif isinstance(tc, str):
                                try:
                                    with open(tc, 'r') as f:
                                        cfg = json.load(f)
                                        if cfg.get('type') == 'inventory':
                                            current_inventory = cfg.get('graph_path')
                                            break
                                except Exception:
                                    pass
                        
                        if current_inventory:
                            console.print(f"📊 [bold cyan]Current inventory:[/bold cyan] {current_inventory}")
                        else:
                            console.print("[yellow]No inventory loaded.[/yellow]")
                        
                        # Show available .json files
                        primary_dir = allowed_directories[0] if allowed_directories else None
                        available = _get_inventory_json_files(primary_dir)
                        if available:
                            console.print(f"[dim]Available files: {', '.join(available[:10])}")
                            if len(available) > 10:
                                console.print(f"[dim]  ... and {len(available) - 10} more[/dim]")
                        console.print("[dim]Usage: /inventory <path/to/graph.json>[/dim]")
                    else:
                        inventory_path = parts[1].strip()
                        
                        # Build inventory config from path
                        primary_dir = allowed_directories[0] if allowed_directories else None
                        inventory_config = _build_inventory_config(inventory_path, primary_dir)
                        if not inventory_config:
                            console.print(f"[red]Inventory file not found: {inventory_path}[/red]")
                            # Show search locations
                            console.print("[dim]Searched in:[/dim]")
                            console.print(f"[dim]  - {Path.cwd()}[/dim]")
                            console.print(f"[dim]  - {Path.cwd() / '.alita' / 'inventory'}[/dim]")
                            if primary_dir:
                                console.print(f"[dim]  - {primary_dir}[/dim]")
                                console.print(f"[dim]  - {Path(primary_dir) / '.alita' / 'inventory'}[/dim]")
                            continue
                        
                        # Remove any existing inventory toolkit configs
                        new_toolkit_configs = []
                        removed_inventory = None
                        for tc in added_toolkit_configs:
                            if isinstance(tc, dict) and tc.get('type') == 'inventory':
                                removed_inventory = tc.get('toolkit_name', 'inventory')
                                continue  # Skip existing inventory
                            elif isinstance(tc, str):
                                try:
                                    with open(tc, 'r') as f:
                                        cfg = json.load(f)
                                        if cfg.get('type') == 'inventory':
                                            removed_inventory = cfg.get('toolkit_name', Path(tc).stem)
                                            continue  # Skip existing inventory
                                except Exception:
                                    pass
                            new_toolkit_configs.append(tc)
                        
                        # Add new inventory config
                        new_toolkit_configs.append(inventory_config)
                        added_toolkit_configs = new_toolkit_configs
                        
                        # Recreate agent executor with new inventory
                        from .tools import create_session_memory, update_session_metadata
                        memory = create_session_memory(current_session_id)
                        try:
                            agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                            )
                            # Persist updated toolkits to session (exclude transient inventory configs)
                            serializable_configs = [tc for tc in added_toolkit_configs if isinstance(tc, str)]
                            update_session_metadata(current_session_id, {
                                'added_toolkit_configs': serializable_configs,
                                'inventory_graph': inventory_config.get('graph_path')  # Save just the graph path
                            })
                            
                            toolkit_name = inventory_config['toolkit_name']
                            graph_path = inventory_config['graph_path']
                            if removed_inventory:
                                console.print(Panel(
                                    f"[cyan]ℹ Replaced inventory [bold]{removed_inventory}[/bold] with [bold]{toolkit_name}[/bold]\n"
                                    f"   Graph: {graph_path}[/cyan]",
                                    border_style="cyan",
                                    box=box.ROUNDED
                                ))
                            else:
                                console.print(Panel(
                                    f"[cyan]✓ Loaded inventory: [bold]{toolkit_name}[/bold]\n"
                                    f"   Graph: {graph_path}[/cyan]",
                                    border_style="cyan",
                                    box=box.ROUNDED
                                ))
                        except Exception as e:
                            console.print(f"[red]Error loading inventory: {e}[/red]")
                    continue
                
                # /session command - list or resume sessions
                if user_input == '/session' or user_input.startswith('/session '):
                    from .tools import list_sessions, PlanState
                    parts = user_input.split(maxsplit=2)
                    
                    if len(parts) == 1 or parts[1] == 'list':
                        # List all sessions with plans
                        sessions = list_sessions()
                        if not sessions:
                            console.print("[dim]No saved sessions found.[/dim]")
                            console.print("[dim]Sessions are created when you start chatting.[/dim]")
                        else:
                            console.print("\n📋 [bold cyan]Saved Sessions:[/bold cyan]\n")
                            from datetime import datetime
                            for i, sess in enumerate(sessions[:10], 1):  # Show last 10
                                modified = datetime.fromtimestamp(sess['modified']).strftime('%Y-%m-%d %H:%M')
                                
                                # Build session info line
                                agent_info = sess.get('agent_name', 'unknown')
                                model_info = sess.get('model', '')
                                if model_info:
                                    agent_info = f"{agent_info} ({model_info})"
                                
                                # Check if this is current session
                                is_current = sess['session_id'] == current_session_id
                                current_marker = " [green]◀ current[/green]" if is_current else ""
                                
                                # Plan progress if available
                                if sess.get('steps_total', 0) > 0:
                                    progress = f"[{sess['steps_completed']}/{sess['steps_total']}]"
                                    status = "✓" if sess['steps_completed'] == sess['steps_total'] else "○"
                                    plan_info = f" - {sess.get('title', 'Untitled')} {progress}"
                                else:
                                    status = "●"
                                    plan_info = ""
                                
                                console.print(f"  {status} [cyan]{sess['session_id']}[/cyan]{plan_info}")
                                console.print(f"      [dim]{agent_info} • {modified}[/dim]{current_marker}")
                            console.print(f"\n[dim]Usage: /session resume <session_id>[/dim]")
                    
                    elif parts[1] == 'resume' and len(parts) > 2:
                        session_id = parts[2].strip()
                        from .tools import load_session_metadata, create_session_memory, from_portable_path
                        
                        # Check if session exists (either plan or metadata)
                        loaded_state = PlanState.load(session_id)
                        session_metadata = load_session_metadata(session_id)
                        
                        if loaded_state or session_metadata:
                            # Update current session to use this session_id
                            current_session_id = session_id
                            
                            # Restore memory from session SQLite (reuses existing memory.db file)
                            memory = create_session_memory(session_id)
                            
                            # Update plan state if available
                            if loaded_state:
                                plan_state.update(loaded_state.to_dict())
                                resume_info = f"\n\n{loaded_state.render()}"
                            else:
                                plan_state['session_id'] = session_id
                                resume_info = ""
                            
                            # Restore agent source and reload agent definition if available
                            restored_agent = False
                            if session_metadata:
                                agent_source = session_metadata.get('agent_source')
                                if agent_source:
                                    agent_file_path = from_portable_path(agent_source)
                                    if Path(agent_file_path).exists():
                                        try:
                                            agent_def = load_agent_definition(agent_file_path)
                                            current_agent_file = agent_file_path
                                            agent_name = agent_def.get('name', Path(agent_file_path).stem)
                                            is_local = True
                                            is_direct = False
                                            restored_agent = True
                                        except Exception as e:
                                            console.print(f"[yellow]Warning: Could not reload agent from {agent_source}: {e}[/yellow]")
                                
                                # Restore added toolkit configs
                                restored_toolkit_configs = session_metadata.get('added_toolkit_configs', [])
                                if restored_toolkit_configs:
                                    added_toolkit_configs.clear()
                                    added_toolkit_configs.extend(restored_toolkit_configs)
                                
                                # Restore added MCPs to agent_def
                                restored_mcps = session_metadata.get('added_mcps', [])
                                if restored_mcps and restored_agent:
                                    if 'mcps' not in agent_def:
                                        agent_def['mcps'] = []
                                    for mcp_name in restored_mcps:
                                        if mcp_name not in [m if isinstance(m, str) else m.get('name') for m in agent_def.get('mcps', [])]:
                                            agent_def['mcps'].append(mcp_name)
                                
                                # Restore model/temperature overrides
                                if session_metadata.get('model'):
                                    current_model = session_metadata['model']
                                    if restored_agent:
                                        agent_def['model'] = current_model
                                if session_metadata.get('temperature') is not None:
                                    current_temperature = session_metadata['temperature']
                                    if restored_agent:
                                        agent_def['temperature'] = current_temperature
                                
                                # Restore allowed directories
                                if session_metadata.get('allowed_directories'):
                                    allowed_directories = session_metadata['allowed_directories']
                                elif session_metadata.get('work_dir'):
                                    # Backward compatibility with old sessions
                                    allowed_directories = [session_metadata['work_dir']]
                            
                            # Reinitialize context manager with resumed session_id to load chat history
                            ctx_manager = CLIContextManager(
                                session_id=session_id,
                                max_context_tokens=context_config.get('max_context_tokens', 8000),
                                preserve_recent=context_config.get('preserve_recent_messages', 5),
                                pruning_method=context_config.get('pruning_method', 'oldest_first'),
                                enable_summarization=context_config.get('enable_summarization', True),
                                summary_trigger_ratio=context_config.get('summary_trigger_ratio', 0.8),
                                summaries_limit=context_config.get('summaries_limit_count', 5),
                                llm=llm if 'llm' in dir() else None
                            )
                            
                            # Show session info
                            agent_info = session_metadata.get('agent_name', 'unknown') if session_metadata else 'unknown'
                            model_info = session_metadata.get('model', '') if session_metadata else ''
                            
                            console.print(Panel(
                                f"[green]✓ Resumed session:[/green] [bold]{session_id}[/bold]\n"
                                f"[dim]Agent: {agent_info}" + (f" • Model: {model_info}" if model_info else "") + f"[/dim]"
                                f"{resume_info}",
                                border_style="green",
                                box=box.ROUNDED
                            ))
                            
                            # Display restored chat history
                            chat_history_export = ctx_manager.export_chat_history(include_only=False)
                            if chat_history_export:
                                preserve_recent = context_config.get('preserve_recent_messages', 5)
                                total_messages = len(chat_history_export)
                                
                                if total_messages > preserve_recent:
                                    console.print(f"\n[dim]... {total_messages - preserve_recent} earlier messages in context[/dim]")
                                    messages_to_show = chat_history_export[-preserve_recent:]
                                else:
                                    messages_to_show = chat_history_export
                                
                                for msg in messages_to_show:
                                    role = msg.get('role', 'user')
                                    content = msg.get('content', '')[:200]  # Truncate for display
                                    if len(msg.get('content', '')) > 200:
                                        content += '...'
                                    role_color = 'cyan' if role == 'user' else 'green'
                                    role_label = 'You' if role == 'user' else 'Assistant'
                                    console.print(f"[dim][{role_color}]{role_label}:[/{role_color}] {content}[/dim]")
                                console.print()
                            
                            # Recreate agent executor with restored tools if we have a local/built-in agent
                            if (is_direct or is_local or is_inventory) and restored_agent:
                                try:
                                    agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                        client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                                    )
                                    ctx_manager.llm = llm  # Update LLM for summarization
                                    
                                    # Warn about MCP state loss
                                    if restored_mcps:
                                        console.print("[yellow]Note: MCP connections re-initialized (stateful server state like browser sessions are lost)[/yellow]")
                                except Exception as e:
                                    console.print(f"[red]Error recreating agent executor: {e}[/red]")
                                    console.print("[yellow]Session state loaded but agent not fully restored. Some tools may not work.[/yellow]")
                            elif is_direct or is_local or is_inventory:
                                # Just update planning tools if we couldn't restore agent
                                try:
                                    from .tools import get_planning_tools
                                    if loaded_state:
                                        planning_tools, _ = get_planning_tools(loaded_state)
                                except Exception as e:
                                    console.print(f"[yellow]Warning: Could not reload planning tools: {e}[/yellow]")
                        else:
                            console.print(f"[red]Session not found: {session_id}[/red]")
                    else:
                        console.print("[dim]Usage: /session [list] or /session resume <session_id>[/dim]")
                    continue
                
                # /agent command - switch to a different agent
                if user_input == '/agent':
                    selected_agent = _select_agent_interactive(client, config)
                    if selected_agent and selected_agent != '__direct__' and selected_agent != '__inventory__':
                        # Load the new agent
                        new_is_local = Path(selected_agent).exists()
                        
                        if new_is_local:
                            agent_def = load_agent_definition(selected_agent)
                            agent_name = agent_def.get('name', Path(selected_agent).stem)
                            agent_type = "Local Agent"
                            is_local = True
                            is_direct = False
                            is_inventory = False
                            current_agent_file = selected_agent  # Track for /reload
                        else:
                            # Platform agent
                            agents = client.get_list_of_apps()
                            new_agent = None
                            try:
                                agent_id = int(selected_agent)
                                new_agent = next((a for a in agents if a['id'] == agent_id), None)
                            except ValueError:
                                new_agent = next((a for a in agents if a['name'] == selected_agent), None)
                            
                            if new_agent:
                                agent_name = new_agent['name']
                                agent_type = "Platform Agent"
                                is_local = False
                                is_direct = False
                                current_agent_file = None  # No file for platform agents
                                
                                # Setup platform agent
                                details = client.get_app_details(new_agent['id'])
                                version_id = details['versions'][0]['id']
                                agent_executor = client.application(
                                    application_id=new_agent['id'],
                                    application_version_id=version_id,
                                    memory=memory,
                                    chat_history=chat_history
                                )
                                console.print(Panel(
                                    f"[cyan]ℹ Switched to agent: [bold]{agent_name}[/bold] ({agent_type}). Chat history preserved.[/cyan]",
                                    border_style="cyan",
                                    box=box.ROUNDED
                                ))
                                continue
                        
                        # For local agents, recreate executor
                        if new_is_local:
                            from .tools import create_session_memory
                            memory = create_session_memory(current_session_id)
                            added_toolkit_configs = []
                            try:
                                agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                    client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                                )
                                console.print(Panel(
                                    f"[cyan]ℹ Switched to agent: [bold]{agent_name}[/bold] ({agent_type}). Agent state reset, chat history preserved.[/cyan]",
                                    border_style="cyan",
                                    box=box.ROUNDED
                                ))
                            except Exception as e:
                                console.print(f"[red]Error switching agent: {e}[/red]")
                    elif selected_agent == '__direct__':
                        # Switch back to direct mode
                        is_direct = True
                        is_local = False
                        is_inventory = False
                        current_agent_file = None  # No file for direct mode
                        agent_name = "Alita"
                        agent_type = "Direct LLM"
                        alita_prompt = _get_alita_system_prompt(config)
                        agent_def = {
                            'model': current_model or default_model,
                            'temperature': current_temperature if current_temperature is not None else default_temperature,
                            'max_tokens': current_max_tokens or default_max_tokens,
                            'system_prompt': alita_prompt
                        }
                        from .tools import create_session_memory
                        memory = create_session_memory(current_session_id)
                        try:
                            agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                            )
                            console.print(Panel(
                                f"[cyan]ℹ Switched to [bold]Alita[/bold]. Agent state reset, chat history preserved.[/cyan]",
                                border_style="cyan",
                                box=box.ROUNDED
                            ))
                        except Exception as e:
                            console.print(f"[red]Error switching to direct mode: {e}[/red]")
                    elif selected_agent == '__inventory__':
                        # Switch to inventory mode
                        is_direct = False
                        is_local = False
                        is_inventory = True
                        current_agent_file = None  # No file for inventory mode
                        agent_name = "Inventory"
                        agent_type = "Built-in Agent"
                        inventory_prompt = _get_inventory_system_prompt(config)
                        agent_def = {
                            'name': 'inventory-agent',
                            'model': current_model or default_model,
                            'temperature': current_temperature if current_temperature is not None else 0.3,
                            'max_tokens': current_max_tokens or default_max_tokens,
                            'system_prompt': inventory_prompt,
                            'toolkit_configs': [
                                {'type': 'inventory', 'graph_path': './knowledge_graph.json'}
                            ]
                        }
                        from .tools import create_session_memory
                        memory = create_session_memory(current_session_id)
                        try:
                            agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, allowed_directories, plan_state
                            )
                            console.print(Panel(
                                f"[cyan]ℹ Switched to [bold]Inventory[/bold] agent. Use /add_toolkit to add source toolkits.[/cyan]",
                                border_style="cyan",
                                box=box.ROUNDED
                            ))
                        except Exception as e:
                            console.print(f"[red]Error switching to inventory mode: {e}[/red]")
                    continue
                
                # Execute agent
                # Track if history was already added during continuation handling
                history_already_added = False
                original_user_input = user_input  # Preserve for history tracking
                
                if (is_direct or is_local or is_inventory) and agent_executor is None:
                    # Local agent without tools: use direct LLM call with streaming
                    system_prompt = agent_def.get('system_prompt', '')
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    
                    # Build pruned context from context manager
                    context_messages = ctx_manager.build_context()
                    for msg in context_messages:
                        messages.append(msg)
                    
                    # Add user message
                    messages.append({"role": "user", "content": user_input})
                    
                    try:
                        # Try streaming if available
                        if hasattr(llm, 'stream'):
                            output_chunks = []
                            first_chunk = True
                            
                            # Show spinner until first token arrives
                            status = console.status("[yellow]Thinking...[/yellow]", spinner="dots")
                            status.start()
                            
                            # Stream the response token by token
                            for chunk in llm.stream(messages):
                                if hasattr(chunk, 'content'):
                                    token = chunk.content
                                else:
                                    token = str(chunk)
                                
                                if token:
                                    # Stop spinner and show agent name on first token
                                    if first_chunk:
                                        status.stop()
                                        console.print(f"\n[bold bright_cyan]{agent_name}:[/bold bright_cyan]\n", end="")
                                        first_chunk = False
                                    
                                    console.print(token, end="", markup=False)
                                    output_chunks.append(token)
                            
                            # Stop status if still running (no tokens received)
                            if first_chunk:
                                status.stop()
                                console.print(f"\n[bold bright_cyan]{agent_name}:[/bold bright_cyan]\n", end="")
                            
                            output = ''.join(output_chunks)
                            console.print()  # New line after streaming
                        else:
                            # Fallback to non-streaming with spinner
                            with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                                response = llm.invoke(messages)
                                if hasattr(response, 'content'):
                                    output = response.content
                                else:
                                    output = str(response)
                            
                            # Display response after spinner stops
                            console.print(f"\n[bold bright_cyan]{agent_name}:[/bold bright_cyan]")
                            if any(marker in output for marker in ['```', '**', '##', '- ', '* ']):
                                console.print(Markdown(output))
                            else:
                                console.print(output)
                    except Exception as e:
                        console.print(f"\n[red]✗ Error: {e}[/red]\n")
                        continue
                else:
                    # Agent with tools or platform agent: use agent executor
                    # Setup callback for verbose output
                    from langchain_core.runnables import RunnableConfig
                    from langgraph.errors import GraphRecursionError
                    
                    # Initialize invoke_config with thread_id for checkpointing
                    # This ensures the same thread is used across continuations
                    invoke_config = RunnableConfig(
                        configurable={"thread_id": current_session_id}
                    )
                    # always proceed with continuation enabled
                    invoke_config["should_continue"] = True
                    # Set recursion limit for tool executions
                    logger.debug(f"Setting tool steps limit to {recursion_limit}")
                    invoke_config["recursion_limit"] = recursion_limit
                    cli_callback = None
                    if show_verbose:
                        cli_callback = create_cli_callback(verbose=True, debug=debug_mode)
                        invoke_config["callbacks"] = [cli_callback]
                    
                    # Track recursion continuation state
                    continue_from_recursion = False
                    recursion_attempts = 0
                    tool_limit_attempts = 0  # Track tool limit continuation attempts
                    max_recursion_continues = 5  # Prevent infinite continuation loops
                    output = None  # Initialize output before loop
                    result = None  # Initialize result before loop
                    
                    while True:
                        try:
                            # Always start with a thinking spinner
                            status = console.status("[yellow]Thinking...[/yellow]", spinner="dots")
                            status.start()
                            
                            # Pass status to callback so it can stop it when tool calls start
                            if cli_callback:
                                cli_callback.status = status
                            
                            try:
                                result = agent_executor.invoke(
                                    {
                                        "input": [user_input] if not is_local else user_input,
                                        "chat_history": ctx_manager.build_context()
                                    },
                                    config=invoke_config
                                )
                            finally:
                                # Make sure spinner is stopped
                                try:
                                    status.stop()
                                except Exception:
                                    pass
                            
                            # Extract output from result
                            if result is not None:
                                output = extract_output_from_result(result)
                            
                            # Check if max tool iterations were reached and prompt user
                            if output and "Maximum tool execution iterations" in output and "reached" in output:
                                tool_limit_attempts += 1
                                
                                console.print()
                                console.print(Panel(
                                    f"[yellow]⚠ Tool execution limit reached[/yellow]\n\n"
                                    f"The agent has executed the maximum number of tool calls in a single turn.\n"
                                    f"This usually happens with complex tasks that require many sequential operations.\n\n"
                                    f"[dim]Attempt {tool_limit_attempts}/{max_recursion_continues}[/dim]",
                                    title="Tool Limit Reached",
                                    border_style="yellow",
                                    box=box.ROUNDED
                                ))
                                
                                if tool_limit_attempts >= max_recursion_continues:
                                    console.print("[red]Maximum continuation attempts reached. Please break down your request into smaller tasks.[/red]")
                                    break
                                
                                console.print("\nWhat would you like to do?")
                                console.print("  [bold cyan]c[/bold cyan] - Continue execution (tell agent to resume)")
                                console.print("  [bold cyan]s[/bold cyan] - Stop and keep partial results")
                                console.print("  [bold cyan]n[/bold cyan] - Start a new request")
                                console.print()
                                
                                try:
                                    choice = input_handler.get_input("Choice [c/s/n]: ").strip().lower()
                                except (KeyboardInterrupt, EOFError):
                                    choice = 's'
                                
                                if choice == 'c':
                                    # Continue - send a follow-up message to resume
                                    console.print("\n[cyan]Continuing execution...[/cyan]\n")
                                    
                                    # Clean up the output - remove the tool limit warning message
                                    clean_output = output
                                    if "Maximum tool execution iterations" in output:
                                        # Strip the warning from the end of the output
                                        lines = output.split('\n')
                                        clean_lines = [l for l in lines if "Maximum tool execution iterations" not in l and "Stopping tool execution" not in l]
                                        clean_output = '\n'.join(clean_lines).strip()
                                    
                                    # Add current output to history first (without the warning)
                                    # Use original user input for first continuation, current for subsequent
                                    history_input = original_user_input if not history_already_added else user_input
                                    if clean_output:
                                        chat_history.append({"role": "user", "content": history_input})
                                        chat_history.append({"role": "assistant", "content": clean_output})
                                        ctx_manager.add_message("user", history_input)
                                        ctx_manager.add_message("assistant", clean_output)
                                        history_already_added = True
                                    
                                    # CRITICAL: Use a new thread_id when continuing to avoid corrupted
                                    # checkpoint state. The tool limit may have left the checkpoint with
                                    # an AIMessage containing tool_calls without corresponding ToolMessages.
                                    # Using a new thread_id starts fresh with our clean context manager state.
                                    import uuid
                                    continuation_thread_id = f"{current_session_id}-cont-{uuid.uuid4().hex[:8]}"
                                    invoke_config = RunnableConfig(
                                        configurable={"thread_id": continuation_thread_id}
                                    )
                                    invoke_config["should_continue"] = True
                                    invoke_config["recursion_limit"] = recursion_limit
                                    if cli_callback:
                                        invoke_config["callbacks"] = [cli_callback]
                                    
                                    # Set new input to continue with a more explicit continuation message
                                    # Include context about the task limit to help the agent understand
                                    user_input = (
                                        "The previous response was interrupted due to reaching the tool execution limit. "
                                        "Continue from where you left off and complete the remaining steps of the original task. "
                                        "Focus on what still needs to be done - do not repeat completed work."
                                    )
                                    continue  # Retry the invoke in this inner loop
                                    
                                elif choice == 's':
                                    console.print("\n[yellow]Stopped. Partial work has been completed.[/yellow]")
                                    break  # Exit retry loop and show output
                                    
                                else:  # 'n' or anything else
                                    console.print("\n[dim]Skipped. Enter a new request.[/dim]")
                                    output = None
                                    break  # Exit retry loop
                            
                            # Success - exit the retry loop
                            break
                            
                        except GraphRecursionError as e:
                            recursion_attempts += 1
                            step_limit = getattr(e, 'recursion_limit', 25)
                            
                            console.print()
                            console.print(Panel(
                                f"[yellow]⚠ Step limit reached ({step_limit} steps)[/yellow]\n\n"
                                f"The agent has executed the maximum number of steps allowed.\n"
                                f"This usually happens with complex tasks that require many tool calls.\n\n"
                                f"[dim]Attempt {recursion_attempts}/{max_recursion_continues}[/dim]",
                                title="Step Limit Reached",
                                border_style="yellow",
                                box=box.ROUNDED
                            ))
                            
                            if recursion_attempts >= max_recursion_continues:
                                console.print("[red]Maximum continuation attempts reached. Please break down your request into smaller tasks.[/red]")
                                output = f"[Step limit reached after {recursion_attempts} continuation attempts. The task may be too complex - please break it into smaller steps.]"
                                break
                            
                            # Prompt user for action
                            console.print("\nWhat would you like to do?")
                            console.print("  [bold cyan]c[/bold cyan] - Continue execution (agent will resume from checkpoint)")
                            console.print("  [bold cyan]s[/bold cyan] - Stop and get partial results")
                            console.print("  [bold cyan]n[/bold cyan] - Start a new request")
                            console.print()
                            
                            try:
                                choice = input_handler.get_input("Choice [c/s/n]: ").strip().lower()
                            except (KeyboardInterrupt, EOFError):
                                choice = 's'
                            
                            if choice == 'c':
                                # Continue - Use a new thread_id to avoid corrupted checkpoint state.
                                # GraphRecursionError may have left the checkpoint with an AIMessage
                                # containing tool_calls without corresponding ToolMessages.
                                # Using a new thread_id starts fresh with our clean context manager state.
                                continue_from_recursion = True
                                console.print("\n[cyan]Continuing with fresh context...[/cyan]\n")
                                
                                # Add current progress to history if we have it
                                # (GraphRecursionError doesn't give us partial output, but context may have been updated)
                                history_input = original_user_input if not history_already_added else user_input
                                ctx_manager.add_message("user", history_input)
                                ctx_manager.add_message("assistant", "[Previous task interrupted - continuing...]")
                                history_already_added = True
                                
                                # Create new thread_id to avoid corrupted checkpoint
                                import uuid
                                continuation_thread_id = f"{current_session_id}-cont-{uuid.uuid4().hex[:8]}"
                                invoke_config = RunnableConfig(
                                    configurable={"thread_id": continuation_thread_id}
                                )
                                if cli_callback:
                                    invoke_config["callbacks"] = [cli_callback]
                                
                                # More explicit continuation message
                                user_input = (
                                    "The previous response was interrupted due to reaching the step limit. "
                                    "Continue from where you left off and complete the remaining steps of the original task. "
                                    "Focus on what still needs to be done - do not repeat completed work."
                                )
                                continue  # Retry the invoke
                                
                            elif choice == 's':
                                # Stop and try to extract partial results
                                console.print("\n[yellow]Stopped. Attempting to extract partial results...[/yellow]")
                                output = "[Task stopped due to step limit. Partial work may have been completed - check any files or state that were modified.]"
                                break
                                
                            else:  # 'n' or anything else
                                console.print("\n[dim]Skipped. Enter a new request.[/dim]")
                                output = None
                                break
                    
                    # Skip chat history update if we bailed out (no result)
                    if output is None:
                        continue
                    
                    # Display response in a clear format
                    console.print()  # Add spacing
                    console.print(f"[bold bright_cyan]{agent_name}:[/bold bright_cyan]")
                    console.print()  # Add spacing before response
                    if any(marker in output for marker in ['```', '**', '##', '- ', '* ']):
                        console.print(Markdown(output))
                    else:
                        console.print(output)
                    console.print()  # Add spacing after response
                
                # Update chat history and context manager (skip if already added during continuation)
                if not history_already_added:
                    chat_history.append({"role": "user", "content": original_user_input})
                    chat_history.append({"role": "assistant", "content": output})
                    
                    # Add messages to context manager for token tracking and pruning
                    ctx_manager.add_message("user", original_user_input)
                    ctx_manager.add_message("assistant", output)
                else:
                    # During continuation, add the final response with continuation message
                    chat_history.append({"role": "user", "content": user_input})
                    chat_history.append({"role": "assistant", "content": output})
                    ctx_manager.add_message("user", user_input)
                    ctx_manager.add_message("assistant", output)
                
            except KeyboardInterrupt:
                console.print("\n\n[yellow]Interrupted. Type 'exit' to quit or continue chatting.[/yellow]")
                continue
            except EOFError:
                # Save final session state before exiting
                try:
                    from .tools import update_session_metadata, to_portable_path
                    update_session_metadata(current_session_id, {
                        'agent_source': to_portable_path(current_agent_file) if current_agent_file else None,
                        'model': current_model or llm_model_display,
                        'temperature': current_temperature if current_temperature is not None else llm_temperature_display,
                        'allowed_directories': allowed_directories,
                        'added_toolkit_configs': list(added_toolkit_configs),
                        'added_mcps': [m if isinstance(m, str) else m.get('name') for m in agent_def.get('mcps', [])],
                    })
                except Exception as e:
                    logger.debug(f"Failed to save session state on exit: {e}")
                console.print("\n\n[bold cyan]Goodbye! 👋[/bold cyan]")
                break
    
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to start chat")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()


@agent.command('run')
@click.argument('agent_source')
@click.argument('message')
@click.option('--version', help='Agent version (for platform agents)')
@click.option('--toolkit-config', multiple=True, type=click.Path(exists=True),
              help='Toolkit configuration files')
@click.option('--model', help='Override LLM model')
@click.option('--temperature', type=float, help='Override temperature')
@click.option('--max-tokens', type=int, help='Override max tokens')
@click.option('--save-thread', help='Save thread ID to file for continuation')
@click.option('--dir', 'work_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='Grant agent filesystem access to this directory')
@click.option('--verbose', '-v', type=click.Choice(['quiet', 'default', 'debug']), default='default',
              help='Output verbosity level: quiet (final output only), default (tool calls + outputs), debug (all including LLM calls)')
@click.pass_context
def agent_run(ctx, agent_source: str, message: str, version: Optional[str],
              toolkit_config: tuple, model: Optional[str], 
              temperature: Optional[float], max_tokens: Optional[int],
              save_thread: Optional[str], work_dir: Optional[str],
              verbose: str):
    """Run agent with a single message (handoff mode).
    
    \b
    AGENT_SOURCE can be:
      - Platform agent ID or name
      - Path to local agent file
    
    MESSAGE is the input message to send to the agent.
    
    \b
    Examples:
      alita run my-agent "What is the status of JIRA-123?"
      alita run ./agent.md "Create a new toolkit for Stripe API"
      alita -o json run my-agent "Search for bugs" --toolkit-config jira.json
      alita run my-agent "Analyze code" --dir ./myproject
      alita run my-agent "Start task" --save-thread thread.txt
      alita run my-agent "Query" -v quiet
      alita run my-agent "Query" -v debug
    """
    formatter = ctx.obj['formatter']
    client = get_client(ctx)
    
    # Setup verbose level
    show_verbose = verbose != 'quiet'
    debug_mode = verbose == 'debug'
    
    try:
        # Load agent
        is_local = Path(agent_source).exists()
        
        if is_local:
            agent_def = load_agent_definition(agent_source)
            agent_name = agent_def.get('name', Path(agent_source).stem)
            
            # Create memory for agent
            from langgraph.checkpoint.sqlite import SqliteSaver
            memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
            
            # Setup local agent executor (reuses same logic as agent_chat)
            try:
                agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                    client, agent_def, toolkit_config, ctx.obj['config'], model, temperature, max_tokens, memory, work_dir, {}
                )
            except Exception as e:
                error_panel = Panel(
                    f"Failed to setup agent: {e}",
                    title="Error",
                    border_style="red",
                    box=box.ROUNDED
                )
                console.print(error_panel, style="red")
                raise click.Abort()
            
            # Execute agent
            if agent_executor:
                # Setup callback for verbose output
                from langchain_core.runnables import RunnableConfig
                from langgraph.errors import GraphRecursionError
                
                invoke_config = None
                if show_verbose:
                    cli_callback = create_cli_callback(verbose=True, debug=debug_mode)
                    invoke_config = RunnableConfig(callbacks=[cli_callback])
                
                try:
                    # Execute with spinner for non-JSON output
                    if formatter.__class__.__name__ == 'JSONFormatter':
                        # JSON output: always quiet, no callbacks
                        with console.status("[yellow]Processing...[/yellow]", spinner="dots"):
                            result = agent_executor.invoke({
                                "input": message,
                                "chat_history": []
                            })
                        
                        click.echo(formatter._dump({
                            'agent': agent_name,
                            'message': message,
                            'response': extract_output_from_result(result),
                            'full_result': result
                        }))
                    else:
                        # Show status only when not verbose (verbose shows its own progress)
                        if not show_verbose:
                            with console.status("[yellow]Processing...[/yellow]", spinner="dots"):
                                result = agent_executor.invoke(
                                    {
                                        "input": message,
                                        "chat_history": []
                                    },
                                    config=invoke_config
                                )
                        else:
                            console.print()  # Add spacing before tool calls
                            result = agent_executor.invoke(
                                {
                                    "input": message,
                                    "chat_history": []
                                },
                                config=invoke_config
                            )
                        
                        # Extract and display output
                        output = extract_output_from_result(result)
                        display_output(agent_name, message, output)
                        
                except GraphRecursionError as e:
                    step_limit = getattr(e, 'recursion_limit', 25)
                    console.print()
                    console.print(Panel(
                        f"[yellow]⚠ Step limit reached ({step_limit} steps)[/yellow]\n\n"
                        f"The agent exceeded the maximum number of steps.\n"
                        f"This task may be too complex for a single run.\n\n"
                        f"[bold]Suggestions:[/bold]\n"
                        f"• Use [cyan]alita agent chat[/cyan] for interactive continuation\n"
                        f"• Break the task into smaller, focused requests\n"
                        f"• Check if partial work was completed (files created, etc.)",
                        title="Step Limit Reached",
                        border_style="yellow",
                        box=box.ROUNDED
                    ))
                    if formatter.__class__.__name__ == 'JSONFormatter':
                        click.echo(formatter._dump({
                            'agent': agent_name,
                            'message': message,
                            'error': 'step_limit_reached',
                            'step_limit': step_limit,
                            'response': f'Step limit of {step_limit} reached. Task may be too complex.'
                        }))
            else:
                # Simple LLM mode without tools
                system_prompt = agent_def.get('system_prompt', '')
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": message})
                
                # Execute with spinner for non-JSON output
                if formatter.__class__.__name__ == 'JSONFormatter':
                    response = llm.invoke(messages)
                    if hasattr(response, 'content'):
                        output = response.content
                    else:
                        output = str(response)
                    
                    click.echo(formatter._dump({
                        'agent': agent_name,
                        'message': message,
                        'response': output
                    }))
                else:
                    # Show spinner while executing
                    with console.status("[yellow]Processing...[/yellow]", spinner="dots"):
                        response = llm.invoke(messages)
                        if hasattr(response, 'content'):
                            output = response.content
                        else:
                            output = str(response)
                    
                    # Display output
                    display_output(agent_name, message, output)
        
        else:
            # Platform agent
            agents = client.get_list_of_apps()
            agent = None
            
            try:
                agent_id = int(agent_source)
                agent = next((a for a in agents if a['id'] == agent_id), None)
            except ValueError:
                agent = next((a for a in agents if a['name'] == agent_source), None)
            
            if not agent:
                raise click.ClickException(f"Agent '{agent_source}' not found")
            
            # Get version
            details = client.get_app_details(agent['id'])
            
            if version:
                version_obj = next((v for v in details['versions'] if v['name'] == version), None)
                if not version_obj:
                    raise click.ClickException(f"Version '{version}' not found")
                version_id = version_obj['id']
            else:
                version_id = details['versions'][0]['id']
            
            # Load toolkit configs from CLI options
            toolkit_configs = []
            if toolkit_config:
                for config_path in toolkit_config:
                    toolkit_configs.append(load_toolkit_config(config_path))
            
            # Create memory
            from langgraph.checkpoint.sqlite import SqliteSaver
            memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
            
            # Create agent executor
            agent_executor = client.application(
                application_id=agent['id'],
                application_version_id=version_id,
                memory=memory
            )
            
            # Setup callback for verbose output
            from langchain_core.runnables import RunnableConfig
            from langgraph.errors import GraphRecursionError
            
            invoke_config = None
            if show_verbose:
                cli_callback = create_cli_callback(verbose=True, debug=debug_mode)
                invoke_config = RunnableConfig(callbacks=[cli_callback])
            
            try:
                # Execute with spinner for non-JSON output
                if formatter.__class__.__name__ == 'JSONFormatter':
                    result = agent_executor.invoke({
                        "input": [message],
                        "chat_history": []
                    })
                    
                    click.echo(formatter._dump({
                        'agent': agent['name'],
                        'message': message,
                        'response': result.get('output', ''),
                        'full_result': result
                    }))
                else:
                    # Show status only when not verbose
                    if not show_verbose:
                        with console.status("[yellow]Processing...[/yellow]", spinner="dots"):
                            result = agent_executor.invoke(
                                {
                                    "input": [message],
                                    "chat_history": []
                                },
                                config=invoke_config
                            )
                    else:
                        console.print()  # Add spacing before tool calls
                        result = agent_executor.invoke(
                            {
                                "input": [message],
                                "chat_history": []
                            },
                            config=invoke_config
                        )
                    
                    # Display output
                    response = result.get('output', 'No response')
                    display_output(agent['name'], message, response)
                
                # Save thread if requested
                if save_thread:
                    thread_data = {
                        'agent_id': agent['id'],
                        'agent_name': agent['name'],
                        'version_id': version_id,
                        'thread_id': result.get('thread_id'),
                        'last_message': message
                    }
                    with open(save_thread, 'w') as f:
                        json.dump(thread_data, f, indent=2)
                    logger.info(f"Thread saved to {save_thread}")
                    
            except GraphRecursionError as e:
                step_limit = getattr(e, 'recursion_limit', 25)
                console.print()
                console.print(Panel(
                    f"[yellow]⚠ Step limit reached ({step_limit} steps)[/yellow]\n\n"
                    f"The agent exceeded the maximum number of steps.\n"
                    f"This task may be too complex for a single run.\n\n"
                    f"[bold]Suggestions:[/bold]\n"
                    f"• Use [cyan]alita agent chat[/cyan] for interactive continuation\n"
                    f"• Break the task into smaller, focused requests\n"
                    f"• Check if partial work was completed (files created, etc.)",
                    title="Step Limit Reached",
                    border_style="yellow",
                    box=box.ROUNDED
                ))
                if formatter.__class__.__name__ == 'JSONFormatter':
                    click.echo(formatter._dump({
                        'agent': agent['name'],
                        'message': message,
                        'error': 'step_limit_reached',
                        'step_limit': step_limit,
                        'response': f'Step limit of {step_limit} reached. Task may be too complex.'
                    }))
    
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to run agent")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()


@agent.command('execute-test-cases')
@click.argument('agent_source')
@click.option('--test-cases-dir', required=True, type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='Directory containing test case files')
@click.option('--results-dir', required=True, type=click.Path(file_okay=False, dir_okay=True),
              help='Directory where test results will be saved')
@click.option('--test-case', 'test_case_files', multiple=True,
              help='Specific test case file(s) to execute (e.g., TC-001.md). Can specify multiple times. If not specified, executes all test cases.')
@click.option('--model', help='Override LLM model')
@click.option('--temperature', type=float, help='Override temperature')
@click.option('--max-tokens', type=int, help='Override max tokens')
@click.option('--dir', 'work_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='Grant agent filesystem access to this directory')
@click.option('--data-generator', type=click.Path(exists=True),
              help='Path to test data generator agent definition file')
@click.option('--validator', type=click.Path(exists=True),
              help='Path to test validator agent definition file (default: .alita/agents/test-validator.agent.md)')
@click.option('--skip-data-generation', is_flag=True,
              help='Skip test data generation step')
@click.pass_context
def execute_test_cases(ctx, agent_source: str, test_cases_dir: str, results_dir: str,
                      test_case_files: tuple, model: Optional[str], temperature: Optional[float], 
                      max_tokens: Optional[int], work_dir: Optional[str],
                      data_generator: Optional[str], validator: Optional[str], 
                      skip_data_generation: bool):
    """
    Execute test cases from a directory and save results.
    
    This command:
    1. (Optional) Executes test data generator agent to provision test data
    2. Scans TEST_CASES_DIR for test case markdown files (TC-*.md)
    3. For each test case:
       - Parses the test case to extract config, steps, and expectations
       - Loads the agent with the toolkit config specified in the test case
       - Executes each test step
       - Validates output against expectations
       - Generates a test result file
    4. Saves all results to RESULTS_DIR
    
    AGENT_SOURCE: Path to agent definition file (e.g., .github/agents/test-runner.agent.md)
    
    \b
    Examples:
      alita execute-test-cases ./agent.json --test-cases-dir ./tests --results-dir ./results
      alita execute-test-cases ./agent.json --test-cases-dir ./tests --results-dir ./results \
          --data-generator ./data-gen.json
      alita execute-test-cases ./agent.json --test-cases-dir ./tests --results-dir ./results \
          --test-case TC-001.md --test-case TC-002.md
      alita execute-test-cases ./agent.json --test-cases-dir ./tests --results-dir ./results \
          --skip-data-generation --model gpt-4o
    """
    # Import dependencies at function start
    import sqlite3
    import uuid
    from langgraph.checkpoint.sqlite import SqliteSaver
    
    config = ctx.obj['config']
    client = get_client(ctx)
    
    try:        
        # Load agent definition
        if not Path(agent_source).exists():
            raise click.ClickException(f"Agent definition not found: {agent_source}")
        
        agent_def = load_agent_definition(agent_source)
        agent_name = agent_def.get('name', Path(agent_source).stem)
        
        # Find all test case files (recursively search subdirectories)
        test_cases_path = Path(test_cases_dir)
        
        # Filter test cases based on --test-case options
        if test_case_files:
            # User specified specific test case files
            test_case_files_set = set(test_case_files)
            all_test_cases = sorted(test_cases_path.rglob('TC-*.md'))
            test_case_files_list = [
                tc for tc in all_test_cases 
                if tc.name in test_case_files_set
            ]
            
            # Check if all specified files were found
            found_names = {tc.name for tc in test_case_files_list}
            not_found = test_case_files_set - found_names
            if not_found:
                console.print(f"[yellow]⚠ Warning: Test case files not found: {', '.join(not_found)}[/yellow]")
        else:
            # Execute all test cases
            test_case_files_list = sorted(test_cases_path.rglob('TC-*.md'))
        
        if not test_case_files_list:
            if test_case_files:
                console.print(f"[yellow]No matching test case files found in {test_cases_dir}[/yellow]")
            else:
                console.print(f"[yellow]No test case files found in {test_cases_dir}[/yellow]")
            return
        
        console.print(f"\n[bold cyan]🧪 Test Execution Started[/bold cyan]")
        console.print(f"Agent: [bold]{agent_name}[/bold]")
        console.print(f"Test Cases: {len(test_case_files_list)}")
        if test_case_files:
            console.print(f"Selected: [cyan]{', '.join(test_case_files)}[/cyan]")
        console.print(f"Results Directory: {results_dir}\n")
        
        data_gen_def = None
        if data_generator and not skip_data_generation:
            try:
                data_gen_def = load_agent_definition(data_generator)
                data_gen_name = data_gen_def.get('name', Path(data_generator).stem)
                console.print(f"Data Generator Agent: [bold]{data_gen_name}[/bold]\n")
            except Exception as e:
                console.print(f"[yellow]⚠ Warning: Failed to setup data generator: {e}[/yellow]")
                console.print("[yellow]Continuing with test execution...[/yellow]\n")
                logger.debug(f"Data generator setup error: {e}", exc_info=True)
        
        # Load validator agent definition
        validator_def = None
        validator_agent_name = "Default Validator"
        
        # Try to load validator from specified path or default location
        validator_path = validator
        if not validator_path:
            # Default to .alita/agents/test-validator.agent.md
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
        
        # Store bulk data generation chat history to pass to test executors
        bulk_gen_chat_history = []
        
        # Parse all test cases upfront for bulk data generation
        parsed_test_cases = []
        for test_file in test_case_files_list:
            try:
                test_case = parse_test_case(str(test_file))
                parsed_test_cases.append({
                    'file': test_file,
                    'data': test_case
                })
            except Exception as e:
                console.print(f"[yellow]⚠ Warning: Failed to parse {test_file.name}: {e}[/yellow]")
                logger.debug(f"Parse error for {test_file.name}: {e}", exc_info=True)
        
        # Filter test cases that need data generation
        test_cases_needing_data_gen = [
            tc for tc in parsed_test_cases 
            if tc['data'].get('generate_test_data', True)
        ]
        
        # Bulk test data generation (if enabled)
        if data_gen_def and not skip_data_generation and test_cases_needing_data_gen:
            console.print(f"\n[bold yellow]🔧 Bulk Test Data Generation[/bold yellow]")
            console.print(f"Generating test data for {len(test_cases_needing_data_gen)} test cases...\n")
            console.print(f"[dim]Skipping {len(parsed_test_cases) - len(test_cases_needing_data_gen)} test cases with generateTestData: false[/dim]\n")
            
            bulk_data_gen_prompt = _build_bulk_data_gen_prompt(test_cases_needing_data_gen)
            
            console.print(f"Executing test data generation prompt {bulk_data_gen_prompt}\n")

            try:
                # Setup data generator agent
                bulk_memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
                
                # Use first test case's config or empty tuple
                first_config_path = None
                if parsed_test_cases:
                    first_tc = parsed_test_cases[0]
                    first_config_path = resolve_toolkit_config_path(
                        first_tc['data'].get('config_path', ''),
                        first_tc['file'],
                        test_cases_path
                    )
                
                data_gen_config_tuple = (first_config_path,) if first_config_path else ()
                data_gen_executor, _, _, _, _, _, _ = _setup_local_agent_executor(
                    client, data_gen_def, data_gen_config_tuple, config,
                    model, temperature, max_tokens, bulk_memory, work_dir
                )
                
                if data_gen_executor:
                    with console.status("[yellow]Generating test data for all test cases...[/yellow]", spinner="dots"):
                        bulk_gen_result = data_gen_executor.invoke({
                            "input": bulk_data_gen_prompt,
                            "chat_history": []
                        })
                    bulk_gen_output = extract_output_from_result(bulk_gen_result)
                    console.print(f"[green]✓ Bulk test data generation completed[/green]")
                    console.print(f"[dim]{bulk_gen_output}...[/dim]\n")
                    
                    # Store chat history from data generation to pass to test executors
                    bulk_gen_chat_history = [
                        {"role": "user", "content": bulk_data_gen_prompt},
                        {"role": "assistant", "content": bulk_gen_output}
                    ]
                else:
                    console.print(f"[yellow]⚠ Warning: Data generator has no executor[/yellow]\n")
            except Exception as e:
                console.print(f"[yellow]⚠ Warning: Bulk data generation failed: {e}[/yellow]")
                console.print("[yellow]Continuing with test execution...[/yellow]\n")
                logger.debug(f"Bulk data generation error: {e}", exc_info=True)
        
        # Execute test cases sequentially with executor caching
        if not parsed_test_cases:
            console.print("[yellow]No test cases to execute[/yellow]")
            return
        
        console.print(f"\n[bold yellow]📋 Executing test cases sequentially...[/bold yellow]\n")
        
        # Show data generation context availability
        if bulk_gen_chat_history:
            console.print(f"[dim]✓ Data generation history available ({len(bulk_gen_chat_history)} messages) - shared with all test cases[/dim]\n")
        else:
            console.print(f"[dim]ℹ No data generation history (skipped or disabled)[/dim]\n")
        
        # Executor cache: key = toolkit_config_path, value = (agent_executor, memory, mcp_session_manager)
        executor_cache = {}
        
        # Validation executor cache: separate isolated executors for validation
        # key = toolkit_config_path, value = (agent_executor, memory, mcp_session_manager)
        validation_executor_cache = {}
        
        # Execute each test case sequentially
        test_results = []
        total_tests = len(parsed_test_cases)
        
        for idx, tc_info in enumerate(parsed_test_cases, 1):
            test_case = tc_info['data']
            test_file = tc_info['file']
            test_name = test_case['name']
            
            # Display progress
            console.print(f"[bold cyan]Test Case {idx}/{total_tests} - {test_name}[/bold cyan]")
            
            try:
                # Resolve toolkit config path for this test case
                toolkit_config_path = resolve_toolkit_config_path(
                    test_case.get('config_path', ''),
                    test_file,
                    test_cases_path
                )
                
                # Use cache key (None if no config)
                cache_key = toolkit_config_path if toolkit_config_path else '__no_config__'
                thread_id = f"test_case_{idx}_{uuid.uuid4().hex[:8]}"
                
                # Get or create executor from cache
                agent_executor, memory, mcp_session_manager = _create_executor_from_cache(
                    executor_cache, cache_key, client, agent_def, toolkit_config_path,
                    config, model, temperature, max_tokens, work_dir
                )
                
                # Build execution prompt for single test case
                execution_prompt = _build_single_test_execution_prompt(tc_info, idx)
                console.print(f"[dim]Executing with {len(bulk_gen_chat_history)} history messages[/dim]")
                
                # Execute test case
                execution_output = ""
                if agent_executor:
                    with console.status(f"[yellow]Executing test case...[/yellow]", spinner="dots"):
                        exec_result = agent_executor.invoke({
                            "input": execution_prompt,
                            "chat_history": bulk_gen_chat_history  # ONLY data gen history, no accumulation
                        }, config={"configurable": {"thread_id": thread_id}})
                    execution_output = extract_output_from_result(exec_result)
                    
                    console.print(f"[green]✓ Test case executed[/green]")
                    console.print(f"[dim]{execution_output}[/dim]\n")
                    
                    # No history accumulation - each test case is independent
                else:
                    console.print(f"[red]✗ No agent executor available[/red]")
                    # Create fallback result for this test
                    test_results.append({
                        'title': test_name,
                        'passed': False,
                        'file': test_file.name,
                        'step_results': []
                    })
                    continue
                
                # Validate test case using ISOLATED validation executor
                validation_prompt = _build_single_test_validation_prompt(tc_info, idx, execution_output)
                
                console.print(f"[bold yellow]🔍 Validating test case (isolated context)...[/bold yellow]")
                
                # Create or retrieve isolated validation executor
                validation_cache_key = f"{cache_key}_validation"
                validation_agent_def = validator_def if validator_def else agent_def
                
                validation_executor, validation_memory, validation_mcp_session = _create_executor_from_cache(
                    validation_executor_cache, validation_cache_key, client, validation_agent_def,
                    toolkit_config_path, config, model, temperature, max_tokens, work_dir
                )
                
                if validation_cache_key not in validation_executor_cache:
                    console.print(f"[dim]Created new isolated validation executor[/dim]")
                else:
                    console.print(f"[dim]Using cached validation executor[/dim]")
                
                # For validation, use a separate thread with NO chat history (isolated from data gen)
                # This prevents the agent from using tools and encourages direct JSON output
                validation_thread_id = f"validation_{idx}_{uuid.uuid4().hex[:8]}"
                
                validation_output = ""
                if validation_executor:
                    with console.status(f"[yellow]Validating test case...[/yellow]", spinner="dots"):
                        validation_result = validation_executor.invoke({
                            "input": validation_prompt,
                            "chat_history": []  # ISOLATED: No data gen history for validation
                        }, {"configurable": {"thread_id": validation_thread_id}})
                    
                    validation_output = extract_output_from_result(validation_result)
                else:
                    console.print(f"[red]✗ No validation executor available[/red]")
                    validation_output = "{}"
                
                console.print(f"[bold cyan]Full LLM Validation Response:[/bold cyan]")
                console.print(f"[dim]{validation_output}[/dim]\n")
                
                # No history update - validation is isolated from test execution
                
                # Parse validation JSON
                try:
                    validation_json = _extract_json_from_text(validation_output)
                    step_results = validation_json.get('steps', [])
                    
                    # Determine if test passed (all steps must pass)
                    test_passed = all(step.get('passed', False) for step in step_results) if step_results else False
                    
                    if test_passed:
                        console.print(f"[bold green]✅ Test PASSED: {test_name}[/bold green]")
                    else:
                        console.print(f"[bold red]❌ Test FAILED: {test_name}[/bold red]")
                    
                    # Display individual step results
                    for step_result in step_results:
                        step_num = step_result.get('step_number')
                        step_title = step_result.get('title', '')
                        passed = step_result.get('passed', False)
                        details = step_result.get('details', '')
                        
                        if passed:
                            console.print(f"  [green]✓ Step {step_num}: {step_title}[/green]")
                            console.print(f"  [dim]{details}[/dim]")
                        else:
                            console.print(f"  [red]✗ Step {step_num}: {step_title}[/red]")
                            console.print(f"  [dim]{details}[/dim]")
                    
                    console.print()
                    
                    # Store result
                    test_results.append({
                        'title': test_name,
                        'passed': test_passed,
                        'file': test_file.name,
                        'step_results': step_results
                    })
                    
                except Exception as e:
                    logger.debug(f"Validation parsing failed for {test_name}: {e}", exc_info=True)
                    console.print(f"[yellow]⚠ Warning: Could not parse validation results for {test_name}[/yellow]")
                    console.print(f"[yellow]Error: {str(e)}[/yellow]")
                    
                    # Enhanced diagnostic output
                    _print_validation_diagnostics(validation_output)
                    
                    # Generate fallback result using helper function
                    console.print(f"\n[yellow]🔄 Generating fallback validation result...[/yellow]")
                    fallback_result = _create_fallback_result_for_test(
                        test_case,
                        test_file,
                        f'Validation failed - could not parse validator output: {str(e)}'
                    )
                    console.print(f"[dim]Created {len(fallback_result['step_results'])} fallback step results[/dim]\n")
                    
                    test_results.append(fallback_result)
                    console.print()
                    
            except Exception as e:
                logger.debug(f"Test execution failed for {test_name}: {e}", exc_info=True)
                console.print(f"[red]✗ Test execution failed: {e}[/red]")
                
                # Create fallback result using helper function
                fallback_result = _create_fallback_result_for_test(
                    test_case,
                    test_file,
                    f'Test execution failed: {str(e)}'
                )
                test_results.append(fallback_result)
                console.print()
        
        # Cleanup: Close executor cache resources
        _cleanup_executor_cache(executor_cache, "executor")
        _cleanup_executor_cache(validation_executor_cache, "validation executor")
        
        # Calculate totals
        total_tests = len(test_results)
        passed_tests = sum(1 for r in test_results if r['passed'])
        failed_tests = total_tests - passed_tests
                
        # Generate summary report
        console.print(f"\n[bold]{'='*60}[/bold]")
        console.print(f"[bold cyan]📊 Test Execution Summary[/bold cyan]")
        console.print(f"[bold]{'='*60}[/bold]\n")
        
        summary_table = Table(box=box.ROUNDED, border_style="cyan")
        summary_table.add_column("Metric", style="bold")
        summary_table.add_column("Value", justify="right")
        
        summary_table.add_row("Total Tests", str(total_tests))
        summary_table.add_row("Passed", f"[green]{passed_tests}[/green]")
        summary_table.add_row("Failed", f"[red]{failed_tests}[/red]")
        
        if total_tests > 0:
            pass_rate = (passed_tests / total_tests) * 100
            summary_table.add_row("Pass Rate", f"{pass_rate:.1f}%")
        
        console.print(summary_table)
        
        # Generate structured JSON report
        overall_result = "pass" if failed_tests == 0 else "fail"
        
        structured_report = {
            "test_cases": [
                {
                    "title": r['title'], 
                    "passed": r['passed'],
                    "steps": r.get('step_results', [])
                } 
                for r in test_results
            ],
            "overall_result": overall_result,
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "pass_rate": f"{pass_rate:.1f}%" if total_tests > 0 else "0%"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Save structured report
        results_path = Path(results_dir)
        results_path.mkdir(parents=True, exist_ok=True)
        summary_file = results_path / "test_execution_summary.json"
        
        console.print(f"\n[bold yellow]💾 Saving test execution summary...[/bold yellow]")
        with open(summary_file, 'w') as f:
            json.dump(structured_report, f, indent=2)
        console.print(f"[green]✓ Summary saved to {summary_file}[/green]\n")
        
        # Exit with error code if any tests failed
        if failed_tests > 0:
            sys.exit(1)
    
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to execute test cases")
        error_panel = Panel(
            str(e),
            title="Error",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(error_panel, style="red")
        raise click.Abort()

