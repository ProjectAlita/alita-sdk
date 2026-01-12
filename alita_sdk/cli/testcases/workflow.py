"""
Main workflow orchestration for test case execution.

Coordinates the entire test execution flow from parsing to reporting.
"""

import logging
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_all_test_cases(
    test_case_files_list: List[Path],
    master_log
) -> List[Dict[str, Any]]:
    """Parse all test case files.
    
    Args:
        test_case_files_list: List of test case files to parse
        master_log: Log capture instance
        
    Returns:
        List of parsed test case dicts with 'file' and 'data' keys
    """
    from .parser import parse_test_case
    
    parsed_test_cases = []
    for test_file in test_case_files_list:
        try:
            test_case = parse_test_case(str(test_file))
            parsed_test_cases.append({
                'file': test_file,
                'data': test_case
            })
        except Exception as e:
            master_log.print(f"[yellow]⚠ Warning: Failed to parse {test_file.name}: {e}[/yellow]")
            logger.debug(f"Parse error for {test_file.name}: {e}", exc_info=True)
    
    return parsed_test_cases


def filter_test_cases_needing_data_gen(
    parsed_test_cases: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Filter test cases that need data generation.
    
    Args:
        parsed_test_cases: All parsed test cases
        
    Returns:
        Filtered list of test cases that require data generation
    """
    return [
        tc for tc in parsed_test_cases 
        if tc['data'].get('generate_test_data', True)
    ]


def execute_all_test_cases(
    parsed_test_cases: List[Dict[str, Any]],
    bulk_gen_chat_history: List[Dict[str, str]],
    test_cases_path: Path,
    agent_def: Dict[str, Any],
    validator_def: Optional[Dict[str, Any]],
    client,
    config,
    model: Optional[str],
    temperature: Optional[float],
    max_tokens: Optional[int],
    work_dir: str,
    master_log,
    setup_executor_func,
    verbose: bool = True,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """Execute all test cases and return results.
    
    Args:
        parsed_test_cases: List of parsed test cases
        bulk_gen_chat_history: Chat history from data generation
        test_cases_path: Path to test cases directory
        agent_def: Test runner agent definition
        validator_def: Validator agent definition (optional)
        client: API client
        config: CLI configuration
        model: Model override
        temperature: Temperature override
        max_tokens: Max tokens override
        work_dir: Working directory
        master_log: Log capture instance
        setup_executor_func: Function to setup executor
        
    Returns:
        List of test result dicts
    """
    from .parser import resolve_toolkit_config_path
    from .utils import extract_toolkit_name
    from .executor import cleanup_executor_cache
    from .test_runner import execute_single_test_case, validate_single_test_case
    from .validation import create_fallback_result_for_test
    
    if not parsed_test_cases:
        master_log.print("[yellow]No test cases to execute[/yellow]")
        return []
    
    master_log.print(f"\n[bold yellow]📋 Executing test cases sequentially...[/bold yellow]\n")
    
    # Show data generation context availability
    if bulk_gen_chat_history:
        master_log.print(f"[dim]✓ Data generation history available ({len(bulk_gen_chat_history)} messages) - shared with all test cases[/dim]\n")
    else:
        master_log.print(f"[dim]ℹ No data generation history (skipped or disabled)[/dim]\n")
    
    # Executor caches
    executor_cache = {}
    validation_executor_cache = {}
    
    # Execute each test case sequentially
    test_results = []
    total_tests = len(parsed_test_cases)
    
    for idx, tc_info in enumerate(parsed_test_cases, 1):
        test_case = tc_info['data']
        test_file = tc_info['file']
        test_name = test_case['name']
        
        try:
            # Resolve toolkit config path
            toolkit_config_path = resolve_toolkit_config_path(
                test_case.get('config_path', ''),
                test_file,
                test_cases_path
            )
            
            # Use cache key
            cache_key = toolkit_config_path if toolkit_config_path else '__no_config__'
            
            # Execute single test case
            execution_output = execute_single_test_case(
                tc_info, idx, total_tests, bulk_gen_chat_history, test_cases_path,
                executor_cache, client, agent_def, config, model, temperature,
                max_tokens, work_dir, master_log, setup_executor_func,
                verbose=verbose,
                debug=debug,
            )
            
            if not execution_output:
                # Create fallback result for failed execution
                test_results.append({
                    'title': test_name,
                    'passed': False,
                    'file': test_file.name,
                    'step_results': []
                })
                continue
            
            # Append execution to history for validation
            from .prompts import build_single_test_execution_prompt
            validation_chat_history = bulk_gen_chat_history + [
                {"role": "user", "content": build_single_test_execution_prompt(tc_info, idx)},
                {"role": "assistant", "content": execution_output}
            ]
            
            # Validate test case
            test_result = validate_single_test_case(
                tc_info, idx, execution_output, validation_chat_history,
                validation_executor_cache, cache_key, client, validator_def,
                agent_def, toolkit_config_path, config, model, temperature,
                max_tokens, work_dir, master_log, setup_executor_func,
                verbose=verbose,
                debug=debug,
            )
            
            test_results.append(test_result)
            
        except Exception as e:
            logger.debug(f"Test execution failed for {test_name}: {e}", exc_info=True)
            master_log.print(f"[red]✗ Test execution failed: {e}[/red]")
            
            # Create fallback result
            fallback_result = create_fallback_result_for_test(
                test_case,
                test_file,
                f'Test execution failed: {str(e)}'
            )
            test_results.append(fallback_result)
            master_log.print()
    
    # Cleanup executor caches
    cleanup_executor_cache(executor_cache, "executor")
    cleanup_executor_cache(validation_executor_cache, "validation executor")
    
    return test_results
