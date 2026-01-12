"""
Bulk test data generation utilities.

Handles executing the data generator agent to provision test data.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from langgraph.checkpoint.sqlite import SqliteSaver

from langchain_core.runnables import RunnableConfig

from ..callbacks import create_cli_callback

logger = logging.getLogger(__name__)


def execute_bulk_data_generation(
    data_gen_def: Dict[str, Any],
    test_cases_needing_data_gen: List[Dict[str, Any]],
    parsed_test_cases: List[Dict[str, Any]],
    test_cases_path: Path,
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
) -> List[Dict[str, str]]:
    """Execute bulk test data generation.
    
    Args:
        data_gen_def: Data generator agent definition
        test_cases_needing_data_gen: Test cases requiring data generation
        parsed_test_cases: All parsed test cases
        test_cases_path: Path to test cases directory
        client: API client
        config: CLI configuration
        model: Model override
        temperature: Temperature override
        max_tokens: Max tokens override
        work_dir: Working directory
        master_log: Log capture instance
        setup_executor_func: Function to setup executor
        
    Returns:
        Chat history list from data generation
    """
    from .parser import resolve_toolkit_config_path
    from .prompts import build_bulk_data_gen_prompt
    from ..agent_ui import extract_output_from_result
    
    master_log.print(f"\n[bold yellow]🔧 Bulk Test Data Generation[/bold yellow]")
    master_log.print(f"Generating test data for {len(test_cases_needing_data_gen)} test cases...\n")
    master_log.print(f"[dim]Skipping {len(parsed_test_cases) - len(test_cases_needing_data_gen)} test cases with generateTestData: false[/dim]\n")
    
    bulk_data_gen_prompt = build_bulk_data_gen_prompt(test_cases_needing_data_gen)
    master_log.print(f"Executing test data generation prompt \n{bulk_data_gen_prompt}\n")

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
        data_gen_executor, _, _, _, _, _, _ = setup_executor_func(
            client, data_gen_def, data_gen_config_tuple, config,
            model, temperature, max_tokens, bulk_memory, work_dir
        )
        
        if data_gen_executor:
            master_log.print("\n" + "=" * 80)
            master_log.print("[bold yellow]📋 BULK DATA GENERATION[/bold yellow]")
            master_log.print("=" * 80 + "\n")
            invoke_config = None
            if verbose:
                cli_callback = create_cli_callback(verbose=True, debug=debug)
                invoke_config = RunnableConfig(callbacks=[cli_callback])
            with master_log.status("[yellow]Generating test data for all test cases...[/yellow]", spinner="dots"):
                bulk_gen_result = data_gen_executor.invoke(
                    {
                        "input": bulk_data_gen_prompt,
                        "chat_history": [],
                    },
                    config=invoke_config,
                )
            bulk_gen_output = extract_output_from_result(bulk_gen_result)
            master_log.print(f"[green]✓ Bulk test data generation completed[/green]")
            master_log.print(f"\n{bulk_gen_output}\n")
            
            # Store chat history from data generation to pass to test executors
            return [
                {"role": "user", "content": bulk_data_gen_prompt},
                {"role": "assistant", "content": bulk_gen_output}
            ]
        else:
            master_log.print(f"[yellow]⚠ Warning: Data generator has no executor[/yellow]\n")
            return []
            
    except Exception as e:
        master_log.print(f"[yellow]⚠ Warning: Bulk data generation failed: {e}[/yellow]")
        master_log.print("[yellow]Continuing with test execution...[/yellow]\n")
        logger.debug(f"Bulk data generation error: {e}", exc_info=True)
        return []
