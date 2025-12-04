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


def _build_bulk_execution_prompt(parsed_test_cases: list) -> str:
    """Build consolidated prompt for bulk test execution."""
    parts = []
    
    for idx, tc_info in enumerate(parsed_test_cases, 1):
        test_case = tc_info['data']
        test_file = tc_info['file']
        
        parts.append(f"\n{'='*80}\nTEST CASE #{idx}: {test_case['name']}\nFile: {test_file.name}\n{'='*80}")
        
        if test_case['steps']:
            for step in test_case['steps']:
                parts.append(f"\nStep {step['number']}: {step['title']}\n{step['instruction']}")
                if step['expectation']:
                    parts.append(f"Expected Result: {step['expectation']}")
        else:
            parts.append("\n(No steps defined)")
    
    return "\n".join(parts)


def _build_validation_prompt(parsed_test_cases: list, execution_output: str) -> str:
    """Build prompt for bulk validation of test results."""
    parts = ["You are a test validator. Review the test execution results and validate each test case.\n\nTest Cases to Validate:\n"]
    
    for idx, tc_info in enumerate(parsed_test_cases, 1):
        test_case = tc_info['data']
        parts.append(f"\nTest Case #{idx}: {test_case['name']}")
        if test_case['steps']:
            for step in test_case['steps']:
                parts.append(f"  Step {step['number']}: {step['title']}")
                if step['expectation']:
                    parts.append(f"  Expected: {step['expectation']}")
    
    parts.append(f"\n\nActual Execution Results:\n{execution_output}\n")
    parts.append(f"""\nBased on the execution results above, validate each test case.

Respond with valid JSON in this EXACT format:
{{
  "test_cases": [
    {{
      "test_number": 1,
      "test_name": "<test case name>",
      "steps": [
        {{"step_number": 1, "title": "<step title>", "passed": true/false, "details": "<brief explanation>"}},
        {{"step_number": 2, "title": "<step title>", "passed": true/false, "details": "<brief explanation>"}}
      ]
    }},
    {{
      "test_number": 2,
      "test_name": "<test case name>",
      "steps": [...]
    }}
  ]
}}

Validate all {len(parsed_test_cases)} test cases and their steps.""")
    
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


def _create_fallback_results(parsed_test_cases: list) -> tuple[list, int, int, int]:
    """Create fallback results when execution/validation fails."""
    test_results = []
    for tc_info in parsed_test_cases:
        test_results.append({
            'title': tc_info['data']['name'],
            'passed': False,
            'file': tc_info['file'].name,
            'step_results': []
        })
    return test_results, len(parsed_test_cases), 0, len(parsed_test_cases)


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
                                max_tokens: Optional[int], memory, work_dir: Optional[str],
                                plan_state: Optional[Dict] = None):
    """Setup local agent executor with all configurations.
    
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
    
    # Add filesystem tools if --dir is provided
    filesystem_tools = None
    terminal_tools = None
    if work_dir:
        from .tools import get_filesystem_tools, get_terminal_tools
        preset = agent_def.get('filesystem_tools_preset')
        include_tools = agent_def.get('filesystem_tools_include')
        exclude_tools = agent_def.get('filesystem_tools_exclude')
        filesystem_tools = get_filesystem_tools(work_dir, include_tools, exclude_tools, preset)
        
        # Also add terminal tools when work_dir is set
        terminal_tools = get_terminal_tools(work_dir)
        
        tool_count = len(filesystem_tools) + len(terminal_tools)
        access_msg = f"✓ Granted filesystem & terminal access to: {work_dir} ({tool_count} tools)"
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


def _select_agent_interactive(client, config) -> Optional[str]:
    """
    Show interactive menu to select an agent from platform and local agents.
    
    Returns:
        Agent source (name/id for platform, file path for local, '__direct__' for direct chat) or None if cancelled
    """
    from .config import CLIConfig
    
    console.print("\n🤖 [bold cyan]Select an agent to chat with:[/bold cyan]\n")
    
    # First option: Alita (direct LLM chat, no agent)
    console.print(f"1. [[bold]💬 Alita[/bold]] [cyan]Chat directly with LLM (no agent)[/cyan]")
    console.print(f"   [dim]Direct conversation with the model without agent configuration[/dim]")
    
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
    
    # Display agents with numbers using rich (starting from 2 since 1 is direct chat)
    for i, agent in enumerate(agents_list, 2):
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
            
            idx = int(choice) - 2  # Offset by 2 since 1 is direct chat
            if 0 <= idx < len(agents_list):
                selected = agents_list[idx]
                console.print(f"✓ [green]Selected:[/green] [bold]{selected['name']}[/bold]")
                return selected['source']
            else:
                console.print(f"[yellow]Invalid selection. Please enter a number between 0 and {len(agents_list) + 1}[/yellow]")
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
@click.option('--thread-id', help='Continue existing conversation thread')
@click.option('--model', help='Override LLM model')
@click.option('--temperature', type=float, help='Override temperature')
@click.option('--max-tokens', type=int, help='Override max tokens')
@click.option('--dir', 'work_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='Grant agent filesystem access to this directory')
@click.option('--verbose', '-v', type=click.Choice(['quiet', 'default', 'debug']), default='default',
              help='Output verbosity level: quiet (final output only), default (tool calls + outputs), debug (all including LLM calls)')
@click.pass_context
def agent_chat(ctx, agent_source: Optional[str], version: Optional[str], 
               toolkit_config: tuple, thread_id: Optional[str],
               model: Optional[str], temperature: Optional[float], 
               max_tokens: Optional[int], work_dir: Optional[str],
               verbose: str):
    """
    Start interactive chat with an agent.
    
    If AGENT_SOURCE is not provided, shows an interactive menu to select from
    available agents (both platform and local).
    
    AGENT_SOURCE can be:
    - Platform agent ID or name
    - Path to local agent file
    
    Examples:
    
        # Interactive selection
        alita-cli agent chat
        
        # Chat with platform agent
        alita-cli agent chat my-agent
        
        # Chat with local agent
        alita-cli agent chat .github/agents/sdk-dev.agent.md
        
        # With toolkit configurations
        alita-cli agent chat my-agent \\
            --toolkit-config jira-config.json \\
            --toolkit-config github-config.json
        
        # With filesystem access
        alita-cli agent chat my-agent --dir ./workspace
        
        # Continue previous conversation
        alita-cli agent chat my-agent --thread-id abc123
        
        # Quiet mode (hide tool calls and thinking)
        alita-cli agent chat my-agent --verbose quiet
        
        # Debug mode (show all including LLM calls)
        alita-cli agent chat my-agent --verbose debug
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
        
        # Check for direct chat mode
        is_direct = agent_source == '__direct__'
        is_local = not is_direct and Path(agent_source).exists()
        
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
        
        # Approval mode: 'always' (confirm each tool), 'auto' (no confirmation), 'yolo' (no safety checks)
        approval_mode = 'always'
        current_work_dir = work_dir  # Track work_dir for /dir command
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
        save_session_metadata(current_session_id, {
            'agent_name': agent_name,
            'agent_type': agent_type if 'agent_type' in dir() else 'Direct LLM',
            'agent_source': agent_source_portable,
            'model': llm_model_display,
            'temperature': llm_temperature_display,
            'work_dir': work_dir,
            'is_direct': is_direct,
            'is_local': is_local,
            'added_toolkit_configs': list(added_toolkit_configs),
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
        if is_direct or is_local:
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
                            'work_dir': current_work_dir,
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
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, current_work_dir, plan_state
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
                        if is_direct:
                            console.print("[yellow]Cannot reload direct chat mode - no agent file to reload.[/yellow]")
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
                            client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, current_work_dir, plan_state
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
                    if not (is_direct or is_local):
                        console.print("[yellow]Adding MCP is only available for local agents and direct chat.[/yellow]")
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
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, current_work_dir, plan_state
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
                if user_input == '/add_toolkit':
                    if not (is_direct or is_local):
                        console.print("[yellow]Adding toolkit is only available for local agents and direct chat.[/yellow]")
                        continue
                    
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
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, current_work_dir, plan_state
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
                
                # /dir command - mount workspace directory
                if user_input == '/dir' or user_input.startswith('/dir '):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) == 1:
                        if current_work_dir:
                            console.print(f"📁 [bold cyan]Current workspace:[/bold cyan] {current_work_dir}")
                        else:
                            console.print("[yellow]No workspace mounted. Usage: /dir /path/to/workspace[/yellow]")
                    else:
                        new_dir = parts[1].strip()
                        new_dir_path = Path(new_dir).expanduser().resolve()
                        
                        if not new_dir_path.exists():
                            console.print(f"[red]Directory not found: {new_dir}[/red]")
                            continue
                        if not new_dir_path.is_dir():
                            console.print(f"[red]Not a directory: {new_dir}[/red]")
                            continue
                        
                        current_work_dir = str(new_dir_path)
                        
                        # Recreate agent executor with new work_dir - use session memory
                        if is_direct or is_local:
                            from .tools import create_session_memory
                            memory = create_session_memory(current_session_id)
                            try:
                                agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                    client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, current_work_dir, plan_state
                                )
                                console.print(Panel(
                                    f"[cyan]✓ Mounted: [bold]{current_work_dir}[/bold]\n   Terminal + filesystem tools enabled.[/cyan]",
                                    border_style="cyan",
                                    box=box.ROUNDED
                                ))
                            except Exception as e:
                                console.print(f"[red]Error mounting directory: {e}[/red]")
                        else:
                            console.print("[yellow]Directory mounting is only available for local agents and direct chat.[/yellow]")
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
                                
                                # Restore work directory
                                if session_metadata.get('work_dir'):
                                    current_work_dir = session_metadata['work_dir']
                            
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
                            
                            # Recreate agent executor with restored tools if we have a local agent
                            if (is_direct or is_local) and restored_agent:
                                try:
                                    agent_executor, mcp_session_manager, llm, llm_model, filesystem_tools, terminal_tools, planning_tools = _setup_local_agent_executor(
                                        client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, current_work_dir, plan_state
                                    )
                                    ctx_manager.llm = llm  # Update LLM for summarization
                                    
                                    # Warn about MCP state loss
                                    if restored_mcps:
                                        console.print("[yellow]Note: MCP connections re-initialized (stateful server state like browser sessions are lost)[/yellow]")
                                except Exception as e:
                                    console.print(f"[red]Error recreating agent executor: {e}[/red]")
                                    console.print("[yellow]Session state loaded but agent not fully restored. Some tools may not work.[/yellow]")
                            elif is_direct or is_local:
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
                    if selected_agent and selected_agent != '__direct__':
                        # Load the new agent
                        new_is_local = Path(selected_agent).exists()
                        
                        if new_is_local:
                            agent_def = load_agent_definition(selected_agent)
                            agent_name = agent_def.get('name', Path(selected_agent).stem)
                            agent_type = "Local Agent"
                            is_local = True
                            is_direct = False
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
                                    client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, current_work_dir, plan_state
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
                                client, agent_def, tuple(added_toolkit_configs), config, current_model, current_temperature, current_max_tokens, memory, current_work_dir, plan_state
                            )
                            console.print(Panel(
                                f"[cyan]ℹ Switched to [bold]Alita[/bold]. Agent state reset, chat history preserved.[/cyan]",
                                border_style="cyan",
                                box=box.ROUNDED
                            ))
                        except Exception as e:
                            console.print(f"[red]Error switching to direct mode: {e}[/red]")
                    continue
                
                # Execute agent
                if (is_direct or is_local) and agent_executor is None:
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
                    
                    invoke_config = None
                    cli_callback = None
                    if show_verbose:
                        cli_callback = create_cli_callback(verbose=True, debug=debug_mode)
                        invoke_config = RunnableConfig(callbacks=[cli_callback])
                    
                    # Track recursion continuation state
                    continue_from_recursion = False
                    recursion_attempts = 0
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
                                # Continue - the checkpoint should preserve state
                                # We'll re-invoke with a continuation message
                                continue_from_recursion = True
                                console.print("\n[cyan]Continuing from last checkpoint...[/cyan]\n")
                                
                                # Modify the input to signal continuation
                                user_input = "Continue from where you left off. Complete the remaining steps of the task."
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
                        
                    # Extract output from result (if we have a result)
                    if result is not None:
                        output = extract_output_from_result(result)
                    
                    # Skip chat history update if we bailed out (no result)
                    if output is None:
                        continue
                    
                    # Check if max tool iterations were reached and prompt user
                    if output and "Maximum tool execution iterations" in output and "reached" in output:
                        console.print()
                        console.print(Panel(
                            f"[yellow]⚠ Tool execution limit reached[/yellow]\n\n"
                            f"The agent has executed the maximum number of tool calls in a single turn.\n"
                            f"This usually happens with complex tasks that require many sequential operations.\n",
                            title="Tool Limit Reached",
                            border_style="yellow",
                            box=box.ROUNDED
                        ))
                        
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
                            
                            # Add current output to history first
                            chat_history.append({"role": "user", "content": user_input})
                            chat_history.append({"role": "assistant", "content": output})
                            ctx_manager.add_message("user", user_input)
                            ctx_manager.add_message("assistant", output)
                            
                            # Set new input to continue and loop back
                            user_input = "Continue from where you left off. Complete the remaining steps of the task."
                            continue  # This will loop back and invoke again
                            
                        elif choice == 's':
                            console.print("\n[yellow]Stopped. Partial work has been completed.[/yellow]")
                            # Fall through to display output and save to history
                            
                        else:  # 'n' or anything else
                            console.print("\n[dim]Skipped. Enter a new request.[/dim]")
                            continue  # Skip saving this output
                    
                    # Display response in a clear format
                    console.print()  # Add spacing
                    console.print(f"[bold bright_cyan]{agent_name}:[/bold bright_cyan]")
                    console.print()  # Add spacing before response
                    if any(marker in output for marker in ['```', '**', '##', '- ', '* ']):
                        console.print(Markdown(output))
                    else:
                        console.print(output)
                    console.print()  # Add spacing after response
                
                # Update chat history and context manager
                chat_history.append({"role": "user", "content": user_input})
                chat_history.append({"role": "assistant", "content": output})
                
                # Add messages to context manager for token tracking and pruning
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
                        'work_dir': current_work_dir,
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
    """
    Run agent with a single message (handoff mode).
    
    AGENT_SOURCE can be:
    - Platform agent ID or name
    - Path to local agent file
    
    MESSAGE is the input message to send to the agent.
    
    Examples:
    
        # Simple query
        alita-cli agent run my-agent "What is the status of JIRA-123?"
        
        # With local agent
        alita-cli agent run .github/agents/sdk-dev.agent.md \\
            "Create a new toolkit for Stripe API"
        
        # With toolkit configs and JSON output
        alita-cli --output json agent run my-agent "Search for bugs" \\
            --toolkit-config jira-config.json
        
        # With filesystem access
        alita-cli agent run my-agent "Analyze the code in src/" --dir ./myproject
        
        # Save thread for continuation
        alita-cli agent run my-agent "Start task" \\
            --save-thread thread.txt
            
        # Quiet mode (hide tool calls and thinking)
        alita-cli agent run my-agent "Query" --verbose quiet
        
        # Debug mode (show all including LLM calls)
        alita-cli agent run my-agent "Query" --verbose debug
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
@click.option('--skip-data-generation', is_flag=True,
              help='Skip test data generation step')
@click.pass_context
def execute_test_cases(ctx, agent_source: str, test_cases_dir: str, results_dir: str,
                      test_case_files: tuple, model: Optional[str], temperature: Optional[float], 
                      max_tokens: Optional[int], work_dir: Optional[str],
                      data_generator: Optional[str], skip_data_generation: bool):
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
    
    Examples:
    
        # Execute all test cases with data generator
        alita-cli agent execute-test-cases \\
            .github/agents/test-runner.agent.json \\
            --test-cases-dir .github/ai_native/testcases \\
            --results-dir .github/ai_native/results \\
            --data-generator .github/agents/test-data-generator.agent.json
        
        # Execute specific test cases
        alita-cli agent execute-test-cases \\
            .github/agents/test-runner.agent.json \\
            --test-cases-dir .github/ai_native/testcases \\
            --results-dir .github/ai_native/results \\
            --test-case TC-001.md \\
            --test-case TC-002.md
        
        # Execute without data generation
        alita-cli agent execute-test-cases \\
            .github/agents/test-runner.agent.json \\
            --test-cases-dir .github/ai_native/testcases \\
            --results-dir .github/ai_native/results \\
            --skip-data-generation
        
        # With custom model and temperature
        alita-cli agent execute-test-cases \\
            .github/agents/test-runner.agent.json \\
            --test-cases-dir .github/ai_native/testcases \\
            --results-dir .github/ai_native/results \\
            --model gpt-4o \\
            --temperature 0.0
    """
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
        
        # Track overall results
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        test_results = []  # Store structured results for final report
        
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
                from langgraph.checkpoint.sqlite import SqliteSaver
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
        
        # Execute ALL test cases in one bulk operation
        if not parsed_test_cases:
            console.print("[yellow]No test cases to execute[/yellow]")
            return
        
        console.print(f"\n[bold yellow]📋 Executing ALL test cases in bulk...[/bold yellow]\n")
        
        # Use first test case's config for agent setup
        first_tc = parsed_test_cases[0]
        first_test_file = first_tc['file']
        toolkit_config_path = resolve_toolkit_config_path(
            first_tc['data'].get('config_path', ''),
            first_test_file,
            test_cases_path
        )
        toolkit_config_tuple = (toolkit_config_path,) if toolkit_config_path else ()
        
        # Create memory for bulk execution
        from langgraph.checkpoint.sqlite import SqliteSaver
        memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
        
        # Initialize chat history with bulk data generation context
        chat_history = bulk_gen_chat_history.copy()
        
        # Setup agent executor
        agent_executor, _, _, _, _, _, _ = _setup_local_agent_executor(
            client, agent_def, toolkit_config_tuple, config, model, temperature, max_tokens, memory, work_dir
        )
        
        # Build bulk execution prompt
        bulk_all_prompt = _build_bulk_execution_prompt(parsed_test_cases)

        console.print(f"Executing the prompt: {bulk_all_prompt}\n")
        
        # Execute all test cases in bulk
        test_results = []
        all_execution_output = ""
        
        try:
            if agent_executor:
                with console.status(f"[yellow]Executing {len(parsed_test_cases)} test cases in bulk...[/yellow]", spinner="dots"):
                    bulk_result = agent_executor.invoke({
                        "input": bulk_all_prompt,
                        "chat_history": chat_history
                    })
                all_execution_output = extract_output_from_result(bulk_result)
                
                console.print(f"[green]✓ All test cases executed[/green]")
                console.print(f"[dim]{all_execution_output}...[/dim]\n")
                
                # Update chat history
                chat_history.append({"role": "user", "content": bulk_all_prompt})
                chat_history.append({"role": "assistant", "content": all_execution_output})
                
                # Now validate ALL test cases in bulk
                console.print(f"[bold yellow]✅ Validating all test cases...[/bold yellow]\n")
                
                validation_prompt = _build_validation_prompt(parsed_test_cases, all_execution_output)
                
                with console.status("[yellow]Validating all results...[/yellow]", spinner="dots"):
                    validation_result = agent_executor.invoke({
                        "input": validation_prompt,
                        "chat_history": chat_history
                    })
                validation_output = extract_output_from_result(validation_result)
                
                console.print(f"[dim]Validation Response: {validation_output}...[/dim]\n")
                
                # Parse validation JSON
                try:
                    validation_json = _extract_json_from_text(validation_output)
                    test_cases_results = validation_json.get('test_cases', [])
                    
                    # Process results for each test case
                    total_tests = 0
                    passed_tests = 0
                    failed_tests = 0
                    
                    for tc_result in test_cases_results:
                        test_name = tc_result.get('test_name', f"Test #{tc_result.get('test_number', '?')}")
                        step_results = tc_result.get('steps', [])
                        
                        # Determine if test passed (all steps must pass)
                        test_passed = all(step.get('passed', False) for step in step_results) if step_results else False
                        
                        total_tests += 1
                        if test_passed:
                            passed_tests += 1
                            console.print(f"[bold green]✅ Test PASSED: {test_name}[/bold green]")
                        else:
                            failed_tests += 1
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
                            'file': parsed_test_cases[tc_result.get('test_number', 1) - 1]['file'].name if tc_result.get('test_number', 1) - 1 < len(parsed_test_cases) else 'unknown',
                            'step_results': step_results
                        })
                    
                except Exception as e:
                    logger.debug(f"Validation parsing failed: {e}")
                    console.print(f"[yellow]⚠ Warning: Could not parse validation results: {e}[/yellow]\n")
                    test_results, total_tests, passed_tests, failed_tests = _create_fallback_results(parsed_test_cases)
            else:
                console.print(f"[red]✗ No agent executor available[/red]\n")
                test_results, total_tests, passed_tests, failed_tests = _create_fallback_results(parsed_test_cases)
                    
        except Exception as e:
            console.print(f"[red]✗ Bulk execution failed: {e}[/red]\n")
            logger.debug(f"Bulk execution error: {e}", exc_info=True)
            test_results, total_tests, passed_tests, failed_tests = _create_fallback_results(parsed_test_cases)
                
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
        
        # Display structured report
        console.print(f"[bold cyan]Structured Report:[/bold cyan]")
        console.print(json.dumps(structured_report, indent=2))
        console.print()
        
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

