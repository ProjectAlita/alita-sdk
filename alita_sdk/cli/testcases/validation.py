"""
Validation utilities for test execution.

Handles JSON extraction, fallback results, and diagnostics.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


def extract_json_from_text(text: str) -> dict:
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


def create_fallback_result_for_test(test_case: Dict[str, Any], test_file: Path, reason: str = 'Validation failed') -> Dict[str, Any]:
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


def print_validation_diagnostics(validation_output: str) -> None:
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
