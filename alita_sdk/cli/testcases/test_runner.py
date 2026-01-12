"""
Single test case execution utilities.

Handles executing a single test case with the test runner agent.
"""

import logging
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console

from langchain_core.runnables import RunnableConfig

from ..callbacks import create_cli_callback

logger = logging.getLogger(__name__)
console = Console()


def execute_single_test_case(
    tc_info: Dict[str, Any],
    idx: int,
    total_tests: int,
    bulk_gen_chat_history: List[Dict[str, str]],
    test_cases_path: Path,
    executor_cache: Dict,
    client,
    agent_def: Dict[str, Any],
    config,
    model: Optional[str],
    temperature: Optional[float],
    max_tokens: Optional[int],
    work_dir: str,
    master_log,
    setup_executor_func,
    verbose: bool = True,
    debug: bool = False,
) -> Optional[str]:
    """Execute a single test case.
    
    Args:
        tc_info: Test case info dict with 'data' and 'file'
        idx: Test case index (1-based)
        total_tests: Total number of test cases
        bulk_gen_chat_history: Chat history from data generation
        test_cases_path: Path to test cases directory
        executor_cache: Cache of executors
        client: API client
        agent_def: Agent definition
        config: CLI configuration
        model: Model override
        temperature: Temperature override
        max_tokens: Max tokens override
        work_dir: Working directory
        master_log: Log capture instance
        setup_executor_func: Function to setup executor
        
    Returns:
        Execution output string, or None if execution failed
    """
    from .parser import resolve_toolkit_config_path
    from .prompts import build_single_test_execution_prompt
    from .utils import extract_toolkit_name
    from .executor import create_executor_from_cache
    from ..agent_ui import extract_output_from_result
    
    test_case = tc_info['data']
    test_file = tc_info['file']
    test_name = test_case['name']
    
    # Resolve toolkit config path for this test case
    toolkit_config_path = resolve_toolkit_config_path(
        test_case.get('config_path', ''),
        test_file,
        test_cases_path
    )
    
    # Extract toolkit name
    toolkit_name = extract_toolkit_name(test_case.get('config_path', ''))
    
    # Use cache key (None if no config)
    cache_key = toolkit_config_path if toolkit_config_path else '__no_config__'
    thread_id = f"test_case_{idx}_{uuid.uuid4().hex[:8]}"
    
    # Log test case header to master log
    master_log.print(f"\n\n" + "=" * 80)
    master_log.print(f"[bold cyan]Test Case {idx}/{total_tests} - {test_name}[/bold cyan]")
    master_log.print(f"[dim]Toolkit: {toolkit_name}[/dim]")
    master_log.print(f"[dim]Config: {toolkit_config_path or 'None'}[/dim]")
    master_log.print("=" * 80 + "\n")
        
    # Get or create executor from cache
    agent_executor, memory, mcp_session_manager = create_executor_from_cache(
        executor_cache, cache_key, client, agent_def, toolkit_config_path,
        config, model, temperature, max_tokens, work_dir, setup_executor_func
    )
    
    # Build execution prompt for single test case
    execution_prompt = build_single_test_execution_prompt(tc_info, idx)
    master_log.print(f"[dim]Executing with {len(bulk_gen_chat_history)} history messages[/dim]")
    master_log.print(f"[dim]Executing test case with the prompt {execution_prompt}[/dim]")
    
    # Execute test case
    if not agent_executor:
        master_log.print(f"[red]✗ No agent executor available[/red]")
        return None
    
    invoke_config = None
    if verbose:
        cli_callback = create_cli_callback(verbose=True, debug=debug)
        invoke_config = RunnableConfig(callbacks=[cli_callback], configurable={"thread_id": thread_id})

    with master_log.status(f"[yellow]Executing test case...[/yellow]", spinner="dots"):
        exec_result = agent_executor.invoke(
            {
                "input": execution_prompt,
                "chat_history": bulk_gen_chat_history,  # ONLY data gen history, no accumulation
            },
            config=invoke_config or {"configurable": {"thread_id": thread_id}},
        )
    
    execution_output = extract_output_from_result(exec_result)
    
    master_log.print(f"[green]✓ Test case executed[/green]")
    master_log.print(f"[dim]{execution_output}[/dim]\n")
    
    return execution_output


def validate_single_test_case(
    tc_info: Dict[str, Any],
    idx: int,
    execution_output: str,
    bulk_gen_chat_history: List[Dict[str, str]],
    validation_executor_cache: Dict,
    cache_key: str,
    client,
    validator_def: Optional[Dict[str, Any]],
    agent_def: Dict[str, Any],
    toolkit_config_path: Optional[str],
    config,
    model: Optional[str],
    temperature: Optional[float],
    max_tokens: Optional[int],
    work_dir: str,
    master_log,
    setup_executor_func,
    verbose: bool = True,
    debug: bool = False,
) -> Dict[str, Any]:
    """Validate a single test case execution.
    
    Args:
        tc_info: Test case info dict
        idx: Test case index (1-based)
        execution_output: Output from test execution
        bulk_gen_chat_history: Chat history including data gen and execution
        validation_executor_cache: Cache of validation executors
        cache_key: Cache key for executor
        client: API client
        validator_def: Validator agent definition (optional)
        agent_def: Test runner agent definition (fallback)
        toolkit_config_path: Path to toolkit config
        config: CLI configuration
        model: Model override
        temperature: Temperature override
        max_tokens: Max tokens override
        work_dir: Working directory
        master_log: Log capture instance
        setup_executor_func: Function to setup executor
        
    Returns:
        Test result dict with validation results
    """
    from .prompts import build_single_test_validation_prompt
    from .validation import extract_json_from_text, print_validation_diagnostics, create_fallback_result_for_test
    from .executor import create_executor_from_cache
    from ..agent_ui import extract_output_from_result
    
    test_case = tc_info['data']
    test_file = tc_info['file']
    test_name = test_case['name']
    
    # Validate test case using validation executor with accumulated history
    validation_prompt = build_single_test_validation_prompt(tc_info, idx, execution_output)
    
    master_log.print(f"[bold yellow]🔍 Validating test case (with execution history)...[/bold yellow]")
    master_log.print(f"[dim]{validation_prompt}[/dim]\n")

    # Create or retrieve isolated validation executor
    validation_cache_key = f"{cache_key}_validation"
    validation_agent_def = validator_def if validator_def else agent_def
    
    validation_executor, validation_memory, validation_mcp_session = create_executor_from_cache(
        validation_executor_cache, validation_cache_key, client, validation_agent_def,
        toolkit_config_path, config, model, temperature, max_tokens, work_dir, setup_executor_func
    )
    
    if validation_cache_key not in validation_executor_cache:
        master_log.print(f"[dim]Created new isolated validation executor[/dim]")
    else:
        master_log.print(f"[dim]Using cached validation executor[/dim]")
    
    # For validation, use a separate thread with accumulated chat history (data gen + execution)
    validation_thread_id = f"validation_{idx}_{uuid.uuid4().hex[:8]}"
    
    if not validation_executor:
        master_log.print(f"[red]✗ No validation executor available[/red]")
        return create_fallback_result_for_test(test_case, test_file, 'No validation executor')
    
    invoke_config = None
    if verbose:
        cli_callback = create_cli_callback(verbose=True, debug=debug)
        invoke_config = RunnableConfig(callbacks=[cli_callback], configurable={"thread_id": validation_thread_id})

    master_log.print(f"[dim]Executing with {len(bulk_gen_chat_history)} history messages[/dim]")
    with master_log.status(f"[yellow]Validating test case...[/yellow]", spinner="dots"):
        validation_result = validation_executor.invoke(
            {
                "input": validation_prompt,
                "chat_history": bulk_gen_chat_history,  # Includes data gen and execution history
            },
            config=invoke_config or {"configurable": {"thread_id": validation_thread_id}},
        )
    
    validation_output = extract_output_from_result(validation_result)
    
    # Parse validation JSON
    try:
        validation_json = extract_json_from_text(validation_output)
        step_results = validation_json.get('steps', [])
        
        # Determine if test passed (all steps must pass)
        test_passed = all(step.get('passed', False) for step in step_results) if step_results else False
        
        if test_passed:
            master_log.print(f"[bold green]✅ Test PASSED: {test_name}[/bold green]")
        else:
            master_log.print(f"[bold red]❌ Test FAILED: {test_name}[/bold red]")
        
        # Display individual step results
        for step_result in step_results:
            step_num = step_result.get('step_number')
            step_title = step_result.get('title', '')
            passed = step_result.get('passed', False)
            details = step_result.get('details', '')
            
            if passed:
                master_log.print(f"  [green]✓ Step {step_num}: {step_title}[/green]")
                master_log.print(f"  [dim]{details}[/dim]")
            else:
                master_log.print(f"  [red]✗ Step {step_num}: {step_title}[/red]")
                master_log.print(f"  [dim]{details}[/dim]")
        
        master_log.print()
        
        return {
            'title': test_name,
            'passed': test_passed,
            'file': test_file.name,
            'step_results': step_results
        }
        
    except Exception as e:
        logger.debug(f"Validation parsing failed for {test_name}: {e}", exc_info=True)
        master_log.print(f"[yellow]⚠ Warning: Could not parse validation results for {test_name}[/yellow]")
        master_log.print(f"[yellow]Error: {str(e)}[/yellow]")
        
        # Enhanced diagnostic output
        print_validation_diagnostics(validation_output)
        
        # Generate fallback result
        master_log.print(f"\n[yellow]🔄 Generating fallback validation result...[/yellow]")
        fallback_result = create_fallback_result_for_test(
            test_case,
            test_file,
            f'Validation failed - could not parse validator output: {str(e)}'
        )
        master_log.print(f"[dim]Created {len(fallback_result['step_results'])} fallback step results[/dim]\n")
        
        return fallback_result
