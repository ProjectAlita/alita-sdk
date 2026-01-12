"""
Test case parsing utilities.

Handles parsing of test case markdown files and resolving configuration paths.
"""

import re
from pathlib import Path
from typing import Optional, Dict, Any


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
    
    # Extract Test Data Configuration section as a raw fenced code block string
    # NOTE: We intentionally store the entire section as a single string rather than parsing
    # individual table rows. This preserves the original formatting for downstream tools
    # which may prefer the raw markdown block.
    test_data_config = None
    config_section_match = re.search(r'##\s+Test Data Configuration\s*\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
    if config_section_match:
        config_section = config_section_match.group(1).strip()
        # Store as a fenced code block to make it clear this is a raw block of text
        test_data_config = f"\n{config_section}\n"
    
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
