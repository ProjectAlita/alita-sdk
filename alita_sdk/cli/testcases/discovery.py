"""
Test case discovery and filtering utilities.

Handles finding test case files and filtering based on user selections.
"""

import logging
from pathlib import Path
from typing import List, Tuple
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


def discover_test_case_files(
    test_cases_dir: str,
    test_case_files: Tuple[str, ...]
) -> List[Path]:
    """Discover and filter test case files based on user selection.
    
    Args:
        test_cases_dir: Directory containing test case files
        test_case_files: Specific test case files to execute (empty = all)
        
    Returns:
        List of test case file paths
    """
    test_cases_path = Path(test_cases_dir)
    
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
    
    return test_case_files_list


def validate_test_case_files(
    test_case_files_list: List[Path],
    test_cases_dir: str,
    test_case_files: Tuple[str, ...]
) -> bool:
    """Validate that test case files were found.
    
    Args:
        test_case_files_list: List of discovered test case files
        test_cases_dir: Directory that was searched
        test_case_files: Specific files that were requested
        
    Returns:
        True if files were found, False otherwise (prints warning)
    """
    if not test_case_files_list:
        if test_case_files:
            console.print(f"[yellow]No matching test case files found in {test_cases_dir}[/yellow]")
        else:
            console.print(f"[yellow]No test case files found in {test_cases_dir}[/yellow]")
        return False
    
    return True


def print_test_execution_header(
    agent_name: str,
    test_case_files_list: List[Path],
    test_case_files: Tuple[str, ...],
    results_dir: str
) -> None:
    """Print test execution header information.
    
    Args:
        agent_name: Name of the test runner agent
        test_case_files_list: List of test cases to execute
        test_case_files: Specific files requested (if any)
        results_dir: Directory where results will be saved
    """
    console.print(f"\n[bold cyan]🧪 Test Execution Started[/bold cyan]")
    console.print(f"Agent: [bold]{agent_name}[/bold]")
    console.print(f"Test Cases: {len(test_case_files_list)}")
    if test_case_files:
        console.print(f"Selected: [cyan]{', '.join(test_case_files)}[/cyan]")
    console.print(f"Results Directory: {results_dir}\n")
