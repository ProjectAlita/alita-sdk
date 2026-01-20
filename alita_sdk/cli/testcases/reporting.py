"""
Test result reporting and summary generation.

Handles generating test reports and displaying summaries.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def generate_summary_report(test_results: List[Dict[str, Any]]) -> Table:
    """Generate a summary table for test results.
    
    Args:
        test_results: List of test result dicts
        
    Returns:
        Rich Table with summary statistics
    """
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r['passed'])
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    summary_table = Table(box=box.ROUNDED, border_style="cyan")
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")
    
    summary_table.add_row("Total Tests", str(total_tests))
    summary_table.add_row("Passed", f"[green]{passed_tests}[/green]")
    summary_table.add_row("Failed", f"[red]{failed_tests}[/red]")
    summary_table.add_row("Pass Rate", f"{pass_rate:.1f}%")
    
    return summary_table


def save_structured_report(
    test_results: List[Dict[str, Any]],
    results_dir: str,
    log_file: Path = None
) -> Path:
    """Save structured JSON report of test results.
    
    Args:
        test_results: List of test result dicts
        results_dir: Directory to save report
        log_file: Optional path to log file
        
    Returns:
        Path to saved report file
    """
    results_path = Path(results_dir)
    results_path.mkdir(parents=True, exist_ok=True)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r['passed'])
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
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
            "pass_rate": f"{pass_rate:.1f}%"
        },
        "timestamp": datetime.now().isoformat(),
        "log_file": str(log_file) if log_file else None
    }
    
    summary_file = results_path / "test_execution_summary.json"
    
    console.print(f"\n[bold yellow]💾 Saving test execution summary...[/bold yellow]")
    with open(summary_file, 'w') as f:
        json.dump(structured_report, f, indent=2)
    console.print(f"[green]✓ Summary saved to {summary_file}[/green]\n")
    
    return summary_file


def print_test_execution_summary(
    test_results: List[Dict[str, Any]],
    results_dir: str,
    session_name: str
) -> None:
    """Print test execution summary to console.
    
    Args:
        test_results: List of test result dicts
        results_dir: Directory where results are saved
        session_name: Session name for finding log file
    """
    console.print(f"\n[bold]{'='*60}[/bold]")
    console.print(f"[bold cyan]📊 Test Execution Summary[/bold cyan]")
    console.print(f"[bold]{'='*60}[/bold]\n")
    
    summary_table = generate_summary_report(test_results)
    console.print(summary_table)
    
    # Show log file location
    results_path = Path(results_dir)
    toolkit_name = session_name.replace('test-execution-', '')
    toolkit_dir = results_path / toolkit_name
    log_files = sorted(toolkit_dir.glob(f"*{session_name}.txt")) if toolkit_dir.exists() else []
    
    console.print(f"\n[bold cyan]📁 Log File[/bold cyan]")
    if log_files:
        console.print(f"  [dim]{log_files[0]}[/dim]")
