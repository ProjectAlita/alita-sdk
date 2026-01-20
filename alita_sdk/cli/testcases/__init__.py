"""
Test execution utilities for Alita CLI.

This package provides utilities for executing test cases, including:
- Test case parsing
- Prompt building
- Result validation
- Execution logging
- Executor cache management
- Agent setup and loading
- Test case discovery
- Test data generation
- Test execution and validation
- Result reporting
"""

from .parser import parse_test_case, resolve_toolkit_config_path
from .prompts import (
    build_bulk_data_gen_prompt,
    build_single_test_execution_prompt,
    build_single_test_validation_prompt
)
from .validation import (
    extract_json_from_text,
    create_fallback_result_for_test,
    print_validation_diagnostics
)
from .logger import TestLogCapture
from .executor import create_executor_from_cache, cleanup_executor_cache
from .utils import extract_toolkit_name
from .setup import (
    load_test_runner_agent,
    load_data_generator_agent,
    load_validator_agent
)
from .discovery import (
    discover_test_case_files,
    validate_test_case_files,
    print_test_execution_header
)
from .data_generation import execute_bulk_data_generation
from .test_runner import execute_single_test_case, validate_single_test_case
from .reporting import (
    generate_summary_report,
    save_structured_report,
    print_test_execution_summary
)
from .workflow import (
    parse_all_test_cases,
    filter_test_cases_needing_data_gen,
    execute_all_test_cases
)

__all__ = [
    # Parser
    'parse_test_case',
    'resolve_toolkit_config_path',
    # Prompts
    'build_bulk_data_gen_prompt',
    'build_single_test_execution_prompt',
    'build_single_test_validation_prompt',
    # Validation
    'extract_json_from_text',
    'create_fallback_result_for_test',
    'print_validation_diagnostics',
    # Logger
    'TestLogCapture',
    # Executor
    'create_executor_from_cache',
    'cleanup_executor_cache',
    # Utils
    'extract_toolkit_name',
    # Setup
    'load_test_runner_agent',
    'load_data_generator_agent',
    'load_validator_agent',
    # Discovery
    'discover_test_case_files',
    'validate_test_case_files',
    'print_test_execution_header',
    # Data Generation
    'execute_bulk_data_generation',
    # Test Runner
    'execute_single_test_case',
    'validate_single_test_case',
    # Reporting
    'generate_summary_report',
    'save_structured_report',
    'print_test_execution_summary',
    # Workflow
    'parse_all_test_cases',
    'filter_test_cases_needing_data_gen',
    'execute_all_test_cases',
]
