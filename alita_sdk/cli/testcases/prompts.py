"""
Prompt building utilities for test execution.

Builds prompts for data generation, test execution, and validation.
"""

from typing import Dict, Any


def build_bulk_data_gen_prompt(parsed_test_cases: list) -> str:
    """Build consolidated requirements text for bulk test data generation."""
    requirements = []
    for idx, tc in enumerate(parsed_test_cases, 1):
        test_case = tc['data']
        test_file = tc['file']
        # Build parts for this test case (do not include separator lines here;
        # the entire block is wrapped with separators at the top-level)
        parts = [f"Test Case #{idx}: {test_case['name']}", f"File: {test_file.name}", ""]
        
        if test_case.get('test_data_config'):
            parts.append("Test Data Configuration:")
            td = test_case['test_data_config']
            raw_lines = str(td).splitlines()
            for line in raw_lines:
                parts.append(f"{line}")
    
        if test_case.get('prerequisites'):
            parts.append(f"\nPre-requisites:\n{test_case['prerequisites']}")
        
        requirements.append("\n".join(parts))
    
    # If no requirements were collected, return an empty string to avoid
    # producing a prompt with only separator lines.
    if not requirements:
        return ""

    # Use a visible divider between test cases so each entry is clearly separated
    divider = '-' * 40
    body = f"\n\n{divider}\n\n".join(requirements)
    return f"{('='*60)}\n\n{body}\n\n{('='*60)}"


def build_single_test_execution_prompt(test_case_info: Dict[str, Any], test_number: int) -> str:
    """Build execution prompt for a single test case."""
    test_case = test_case_info['data']
    test_file = test_case_info['file']
    
    parts = [
        f"\n{'='*80}",
        f"TEST CASE #{test_number}: {test_case['name']}",
        f"File: {test_file.name}",
        f"{'='*80}"
    ]
    
    if test_case['steps']:
        for step in test_case['steps']:
            parts.append(f"\nStep {step['number']}: {step['title']}")
            parts.append(step['instruction'])
    else:
        parts.append("\n(No steps defined)")
    
    return "\n".join(parts)


def build_single_test_validation_prompt(test_case_info: Dict[str, Any], test_number: int, execution_output: str) -> str:
    """Build validation prompt for a single test case."""
    test_case = test_case_info['data']
    
    parts = [
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
        {{
          "test_number": {test_number},
          "test_name": "{escaped_test_name}"
        }}
    """)
    
    return "\n".join(parts)
