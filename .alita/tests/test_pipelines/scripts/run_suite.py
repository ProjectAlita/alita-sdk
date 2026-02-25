#!/usr/bin/env python3
"""
Execute a suite of pipelines and report aggregated results.

Usage:
    python run_suite.py <suite_folder> [options]
    python run_suite.py <suite_folder>:<pipeline_file.yaml> [options]
    python run_suite.py --pattern "GH*" [options]

Examples:
    # Run all pipelines in a folder (uses pipeline.yaml)
    python run_suite.py github_toolkit

    # Run specific pipeline config from a folder
    python run_suite.py github_toolkit_negative:pipeline_validation.yaml

    # Run pipelines matching a pattern
    python run_suite.py --pattern "GH1*" --pattern "GH2*"

    # Run specific pipeline IDs
    python run_suite.py --ids 267 268 269

    # JSON output for CI/CD
    python run_suite.py github_toolkit --json

    # Parallel execution
    python run_suite.py github_toolkit --parallel 4

Suite Specification Format:
    - 'suite_name' - Uses default pipeline.yaml in the suite folder
    - 'suite_name:pipeline_file.yaml' - Uses specific pipeline config file
      e.g., 'github_toolkit_negative:pipeline_validation.yaml'
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone

# Import shared pattern matching utilities
from pattern_matcher import matches_any_pattern

import requests
import yaml

# Force UTF-8 encoding for Windows compatibility
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # Python < 3.7
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Import from run_pipeline module
from run_pipeline import (
    get_auth_headers,
    get_pipeline_by_id,
    execute_pipeline,
    PipelineResult
)

# Import shared utilities
from utils_common import (
    load_config,
    parse_suite_spec,
    resolve_env_value,
    load_from_env,
    load_token_from_env,
    load_base_url_from_env,
    load_project_id_from_env,
    apply_session_to_pipeline_name,
)

from logger import TestLogger

from utils_local import (
    IsolatedPipelineTestRunner,
    find_tests_in_suite,
    configure_file_logging,
)

# Import setup utilities for local execution
from setup import execute_setup, SetupContext
from setup_strategy import LocalSetupStrategy

# Import ReportPortal reporter (optional)
try:
    from rp_reporter import create_reporter
    RP_AVAILABLE = True
except ImportError:
    RP_AVAILABLE = False
    create_reporter = None


def load_test_description(test_file: Path) -> str:
    """Load description from test YAML file."""
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            test_data = yaml.safe_load(f)
            return test_data.get('description', '')
    except Exception:
        return ''


def evaluate_condition(condition: str, result: dict) -> bool:
    """Evaluate a hook condition against test result.

    The condition is a Python expression that has access to:
    - result: The test result dictionary

    Example conditions:
    - "not result.get('test_passed', True)"
    - "result.get('error') is not None"
    """
    if not condition:
        return True

    try:
        # Safely evaluate the condition
        return eval(condition, {"__builtins__": {}}, {"result": result})
    except Exception as e:
        print(f"  Warning: Failed to evaluate condition '{condition}': {e}")
        return False


def build_hook_input(input_mapping: dict, result: dict) -> dict:
    """Build hook pipeline input from test result using input_mapping.

    Each key in input_mapping maps to a pipeline input variable,
    and the value is a Python expression to extract from result.

    Example:
        input_mapping:
          test_name: "result['name']"
          test_results: "result['test_results']"
    """
    hook_input = {}

    for target_key, source_expr in input_mapping.items():
        try:
            value = eval(source_expr, {"__builtins__": {}}, {"result": result})
            hook_input[target_key] = value
        except Exception as e:
            print(f"  Warning: Failed to extract {target_key}: {e}")
            hook_input[target_key] = None

    return hook_input


def merge_hook_output(result: dict, output: dict, output_mapping: dict) -> dict:
    """Merge hook pipeline output back into test result.

    output_mapping maps source (hook output key) to target (result path).

    Example:
        output_mapping:
          "result['test_results']['rca']": "rca_result"
    """
    if not output_mapping:
        return result

    for target_path, source_key in output_mapping.items():
        if source_key not in output:
            continue

        # Simple nested key assignment
        # e.g., "result['test_results']['rca']" -> assign to result['test_results']['rca']
        try:
            # Parse target path like result['key1']['key2']
            exec(f"{target_path} = output['{source_key}']", {"result": result, "output": output})
        except Exception as e:
            print(f"  Warning: Failed to merge {source_key} to {target_path}: {e}")

    return result


def invoke_hook_pipeline(
        base_url: str,
        project_id: int,
        pipeline_id: int,
        hook_input: dict,
        headers: dict,
        timeout: int = 120,
        logger: Optional[TestLogger] = None
) -> dict:
    """Invoke a composable pipeline for a hook.

    Args:
        base_url: Platform base URL
        project_id: Project ID
        pipeline_id: The composable pipeline ID to invoke
        hook_input: Input data for the pipeline
        headers: Auth headers
        timeout: Execution timeout
        logger: Optional TestLogger instance

    Returns:
        dict with success status and output
    """
    # Get pipeline details
    pipeline = get_pipeline_by_id(base_url, project_id, pipeline_id, headers)
    if not pipeline:
        return {"success": False, "error": f"Pipeline {pipeline_id} not found"}

    # Execute the pipeline with the hook input
    result = execute_pipeline(
        base_url=base_url,
        project_id=project_id,
        pipeline=pipeline,
        input_message=json.dumps(hook_input),
        timeout=timeout,
        logger=logger
    )

    if not result.success:
        return {"success": False, "error": result.error}

    # Extract output from chat_history messages
    # Composable pipelines output to messages, which appear in chat_history
    output_data = result.output
    extracted_output = {}

    if logger:
        logger.debug(f"RCA output_data type: {type(output_data).__name__}")
        if isinstance(output_data, dict):
            logger.debug(f"RCA output_data keys: {list(output_data.keys())}")

    if isinstance(output_data, dict):
        # Check if output is already the data we need
        if "rca_result" in output_data or "rca_summary" in output_data:
            extracted_output = output_data
        # Otherwise extract from chat_history
        elif "chat_history" in output_data:
            chat_history = output_data.get("chat_history", [])
            if logger:
                logger.debug(f"RCA chat_history length: {len(chat_history)}")
            # Look for the last message with our output
            for msg in reversed(chat_history):
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    # Try to parse as JSON
                    if isinstance(content, str) and content.strip().startswith("{"):
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict):
                                extracted_output = parsed
                                if logger:
                                    logger.debug(f"RCA extracted from JSON string, keys: {list(parsed.keys())}")
                                break
                        except json.JSONDecodeError:
                            pass
                    # Or if content is already a dict
                    elif isinstance(content, dict):
                        extracted_output = content
                        if logger:
                            logger.debug(f"RCA extracted from dict content, keys: {list(content.keys())}")
                        break

    # Unwrap 'result' envelope if present (from code nodes)
    if isinstance(extracted_output, dict) and "result" in extracted_output:
        if isinstance(extracted_output["result"], dict):
            extracted_output = extracted_output["result"]
            if logger:
                logger.debug(f"RCA unwrapped 'result' envelope, keys: {list(extracted_output.keys())}")

    if logger:
        logger.debug(f"RCA extracted_output keys: {list(extracted_output.keys()) if extracted_output else 'None'}")
    return {"success": True, "output": extracted_output}


def run_post_test_hooks(
        base_url: str,
        project_id: int,
        result: dict,
        hooks_config: list,
        env_vars: dict,
        headers: dict,
        timeout: int = 120,
        logger: Optional[TestLogger] = None
) -> dict:
    """Run post-test hooks for a test result.

    Args:
        base_url: Platform base URL
        project_id: Project ID
        result: Test result dictionary
        hooks_config: List of hook configurations from config.yaml
        env_vars: Environment variables for substitution
        headers: Auth headers
        timeout: Execution timeout
        logger: Optional TestLogger instance

    Returns:
        Updated test result with hook outputs merged
    """

    for hook in hooks_config:
        hook_name = hook.get("name", "unnamed")
        condition = hook.get("condition", "")
        pipeline_id = resolve_env_value(hook.get("pipeline_id"), env_vars, env_loader=load_from_env)

        if not pipeline_id:
            if logger:
                logger.debug(f"Skipping hook '{hook_name}': no pipeline_id")
            continue

        # Evaluate condition
        if not evaluate_condition(condition, result):
            if logger:
                logger.debug(f"Skipping hook '{hook_name}': condition not met")
            continue

        if logger:
            logger.debug(f"Running hook: {hook_name}")

        # Build input from result
        input_mapping = hook.get("input_mapping", {})
        hook_input = build_hook_input(input_mapping, result)

        # Invoke the hook pipeline
        try:
            pipeline_id_int = int(pipeline_id)
        except (ValueError, TypeError):
            if logger:
                logger.debug(f"Warning: Invalid pipeline_id '{pipeline_id}'")
            continue

        hook_result = invoke_hook_pipeline(
            base_url=base_url,
            project_id=project_id,
            pipeline_id=pipeline_id_int,
            hook_input=hook_input,
            headers=headers,
            timeout=timeout,
            logger=logger
        )

        if hook_result.get("success"):
            # Merge output back to result
            output_mapping = hook.get("output_mapping", {})
            result = merge_hook_output(result, hook_result.get("output", {}), output_mapping)
            if logger:
                logger.debug(f"Hook '{hook_name}' completed successfully")
        else:
            if logger:
                logger.debug(f"Hook '{hook_name}' failed: {hook_result.get('error')}")

    return result


@dataclass
class SuiteResult:
    """Aggregated results from suite execution."""
    suite_name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    execution_time: float = 0.0
    results: List[dict] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100

    @property
    def all_passed(self) -> bool:
        return self.passed == self.total and self.total > 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["success_rate"] = self.success_rate
        d["all_passed"] = self.all_passed
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_summary(self, results_file: str = None) -> str:
        """Generate human-readable summary.

        Args:
            results_file: Optional path to results.json file for reference in error messages
        """
        lines = [
            f"\n{'=' * 60}",
            f"Suite: {self.suite_name}",
            f"{'=' * 60}",
            f"Total: {self.total} | Passed: {self.passed} | Failed: {self.failed} | Errors: {self.errors} | Skipped: {self.skipped}",
            f"Success Rate: {self.success_rate:.1f}%",
            f"Execution Time: {self.execution_time:.2f}s",
            f"{'=' * 60}",
            "",
            "Results:",
        ]

        for r in self.results:
            status = "✓" if r.get("test_passed") else ("✗" if r.get("test_passed") is False else "?")
            name = r.get("pipeline_name", "Unknown")
            time_str = f"{r.get('execution_time', 0):.1f}s"

            # Extract error from multiple sources
            error_msg = r.get("error")
            if not error_msg and r.get("test_passed") is False:
                # Check output for error details
                output = r.get("output", {})
                if isinstance(output, dict):
                    result = output.get("result", {})
                    if isinstance(result, dict):
                        error_msg = result.get("tool_response") or result.get("error")

            # Display truncated error with note about full details
            if error_msg:
                if len(error_msg) > 200:
                    results_ref = f" in {results_file}" if results_file else " in results.json"
                    error = f"\n      Error: {error_msg[:200]}...\n      (See full error{results_ref})"
                else:
                    error = f"\n      Error: {error_msg}"
            else:
                error = ""
            lines.append(f"  {status} {name} ({time_str}){error}")

        lines.append(f"\n{'=' * 60}")
        return "\n".join(lines)


def get_pipelines_from_folder(
        base_url: str,
        project_id: int,
        folder_name: str,
        headers: dict,
        pipeline_file: str | None = None,
        session_id: str | None = None,
) -> List[dict]:
    """Get pipelines that match the folder's test case names.

    Args:
        base_url: Platform base URL
        project_id: Project ID
        folder_name: Name of the suite folder
        headers: Auth headers
        pipeline_file: Optional specific pipeline config file (e.g., 'pipeline_validation.yaml')
        session_id: Session ID for parallel execution isolation (matches prefixed names)
    """
    # Read YAML files to get pipeline names
    # Go up from scripts/ to test_pipelines/ directory
    folder_path = Path(__file__).parent.parent / folder_name
    if not folder_path.exists():
        return []

    import yaml

    # Check if there's a pipeline config with test_directory setting
    test_dir = folder_path
    config_file = pipeline_file or "pipeline.yaml"
    config_path = folder_path / config_file
    if not config_path.exists() and pipeline_file:
        # Specified file doesn't exist
        return []
    if not config_path.exists():
        # Try fallback
        config_path = folder_path / "config.yaml"

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
                if config and "execution" in config:
                    test_subdir = config["execution"].get("test_directory")
                    if test_subdir:
                        test_dir = folder_path / test_subdir
        except Exception:
            pass

    pipeline_names = []
    # Look for test files in the appropriate directory
    # Support both standard test cases and negative test cases
    # Use recursive glob (**/) to find tests in subdirectories
    yaml_files = []
    for pattern in ["**/test_case_*.yaml", "**/test_neg_*.yaml"]:
        yaml_files.extend(test_dir.glob(pattern))
    # Also check for files directly in test_dir (non-recursive)
    for pattern in ["test_case_*.yaml", "test_neg_*.yaml"]:
        yaml_files.extend(test_dir.glob(pattern))
    # Remove duplicates
    yaml_files = list(set(yaml_files))
    for yaml_file in sorted(yaml_files):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if data and "name" in data:
                    # Apply session prefix to match session-scoped pipelines on platform
                    pipeline_names.append(apply_session_to_pipeline_name(data["name"], session_id))
        except Exception:
            continue

    if not pipeline_names:
        return []

    # Get all pipelines and filter by name
    url = f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}?limit=500"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []

    all_pipelines = response.json().get("rows", [])
    matched = []

    for name in pipeline_names:
        for p in all_pipelines:
            # Use pattern matching for fuzzy matching (case-insensitive, space/underscore agnostic)
            if matches_any_pattern(p.get("name", ""), [name]):
                # Get full pipeline details
                full = get_pipeline_by_id(base_url, project_id, p["id"], headers)
                if full:
                    matched.append(full)
                break

    return matched


def get_pipelines_by_pattern(
        base_url: str,
        project_id: int,
        patterns: List[str],
        headers: dict,
        use_wildcards: bool = False
) -> List[dict]:
    """Get pipelines matching name patterns (substring match, case-insensitive, underscore/space agnostic)."""
    url = f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}?limit=500"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []

    all_pipelines = response.json().get("rows", [])
    matched = []

    for p in all_pipelines:
        name = p.get("name", "")
        # Use shared pattern matching utility
        if matches_any_pattern(name, patterns, use_wildcards):
            full = get_pipeline_by_id(base_url, project_id, p["id"], headers)
            if full:
                matched.append(full)

    return matched


def get_pipelines_by_ids(
        base_url: str,
        project_id: int,
        ids: List[int],
        headers: dict
) -> List[dict]:
    """Get pipelines by their IDs."""
    pipelines = []
    for pid in ids:
        p = get_pipeline_by_id(base_url, project_id, pid, headers)
        if p:
            pipelines.append(p)
    return pipelines


def run_suite(
        base_url: str,
        project_id: int,
        pipelines: List[dict],
        suite_name: str,
        input_message: str = "",
        timeout: int = 120,
        parallel: int = 1,
        logger: Optional[TestLogger] = None,
        config: dict = None,
        env_vars: dict = None,
        headers: dict = None,
        reporter = None,  # ReportPortalReporter instance
) -> SuiteResult:
    """Execute multiple pipelines and aggregate results.

    Args:
        base_url: Platform base URL
        project_id: Project ID
        pipelines: List of pipeline dictionaries to execute
        suite_name: Name of the test suite
        input_message: Input message for pipelines
        timeout: Execution timeout per pipeline
        parallel: Number of parallel executions
        logger: Optional TestLogger instance for logging
        config: Suite config.yaml (optional, for hooks)
        env_vars: Environment variables for hook substitution
        headers: Auth headers (for hook pipeline invocation)
        reporter: Optional ReportPortal reporter instance
    """
    start_time = time.time()
    suite = SuiteResult(suite_name=suite_name, total=len(pipelines))
    env_vars = env_vars or {}
    headers = headers or get_auth_headers()

    # Get post-test hooks from config
    post_test_hooks = []
    if config:
        hooks = config.get("hooks", {})
        post_test_hooks = hooks.get("post_test", [])
        if post_test_hooks and logger:
            logger.debug(f"Post-test hooks configured: {len(post_test_hooks)}")

    # ReportPortal: Report tests directly to launch (no suite nesting)
    rp_suite_id = None

    def execute_one(pipeline: dict) -> PipelineResult:
        return execute_pipeline(
            base_url=base_url,
            project_id=project_id,
            pipeline=pipeline,
            input_message=input_message,
            timeout=timeout,
            logger=logger
        )

    results = []

    if parallel > 1:
        # Parallel execution (hooks not supported during parallel execution yet)
        if logger:
            logger.info(f"Starting parallel execution with {parallel} workers...")
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {executor.submit(execute_one, p): p for p in pipelines}
            if logger:
                logger.info(f"Submitted {len(futures)} tests to thread pool")
            for future in as_completed(futures):
                pipeline = futures[future]
                pipeline_name = pipeline.get('name', f"ID: {pipeline.get('id')}")
                
                # Start ReportPortal test
                rp_test_id = None
                if reporter and reporter.active:
                    description = pipeline.get('description', '')
                    rp_test_id = reporter.start_test(
                        name=pipeline_name,
                        description=description
                    )
                
                try:
                    result = future.result()
                    # Convert to dict immediate and add timestamp
                    r_dict = result.to_dict()
                    r_dict['timestamp'] = datetime.now(timezone.utc).isoformat()
                    
                    # Report to ReportPortal
                    if reporter and reporter.active and rp_test_id:
                        reporter.log_result(rp_test_id, r_dict)
                        reporter.finish_test(rp_test_id, r_dict)
                    
                    results.append(r_dict)

                    if logger and logger.verbose:
                        status = "PASS" if result.test_passed else "FAIL"
                        logger.info(f"[{status}] {result.pipeline_name}")
                    elif logger and not logger.quiet:
                        status = "\033[92m✓\033[0m" if result.test_passed else "\033[91m✗\033[0m"
                        print(f"{status} {result.pipeline_name}", flush=True)
                except Exception as e:
                    error_result = {
                        'success': False,
                        'pipeline_id': pipeline.get("id", 0),
                        'pipeline_name': pipeline_name,
                        'error': str(e),
                        'test_passed': False,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Report error to ReportPortal
                    if reporter and reporter.active and rp_test_id:
                        reporter.log_result(rp_test_id, error_result)
                        reporter.finish_test(rp_test_id, error_result)
                    
                    results.append(error_result)
    else:
        # Sequential execution
        for pipeline in pipelines:
            pipeline_name = pipeline.get('name', f"ID: {pipeline.get('id')}")

            if logger:
                logger.debug(f"Running: {pipeline_name}...")
            elif logger and not logger.quiet:
                sys.stdout.write(f"▶ {pipeline_name}...\r")
                sys.stdout.flush()

            # Start ReportPortal test
            rp_test_id = None
            if reporter and reporter.active:
                description = pipeline.get('description', '')
                rp_test_id = reporter.start_test(
                    name=pipeline_name,
                    description=description
                )

            # 1. Execute Pipeline
            result = execute_one(pipeline)

            # 2. Run post-test hooks immediately (e.g. RCA)
            result_dict = result.to_dict()
            result_dict['timestamp'] = datetime.now(timezone.utc).isoformat()
            rca_info = ""

            if post_test_hooks:
                result_dict = run_post_test_hooks(
                    base_url=base_url,
                    project_id=project_id,
                    result=result_dict,
                    hooks_config=post_test_hooks,
                    env_vars=env_vars,
                    headers=headers,
                    timeout=timeout,
                    logger=logger
                )
                # Check if RCA added any results
                # Assuming RCA hook output is merged into result['test_results']['rca'] or similar
                # This depends on output_mapping in config.yaml
                # But generic check: if result was fail, and now we have extra info?
                if not result.test_passed:
                    # Try to find RCA output. Common pattern is 'rca' key.
                    # Or check for 'hook_results' if we added that (we didn't yet).
                    pass

            # Report to ReportPortal
            if reporter and reporter.active and rp_test_id:
                reporter.log_result(rp_test_id, result_dict)
                reporter.finish_test(rp_test_id, result_dict)

            results.append(result_dict)  # Store dictionary with hook results

            # 3. Print Result
            if logger and logger.verbose:
                status = "PASS" if result.test_passed else "FAIL"
                logger.debug(f"[{status}] {result.execution_time:.1f}s")
            elif logger and not logger.quiet:
                # Clear running line
                sys.stdout.write("\033[2K\r")
                sys.stdout.flush()

                if result.test_passed:
                    status = "\033[92m✓\033[0m"  # Green check
                    print(f"{status} {pipeline.get('name')} ({result.execution_time:.1f}s)", flush=True)
                else:
                    status = "\033[91m✗\033[0m"  # Red x
                    print(f"{status} {pipeline.get('name')} ({result.execution_time:.1f}s)", flush=True)

                    # Print RCA info if available in result_dict
                    rca_summary = result_dict.get('rca_summary')
                    if rca_summary:
                        print(f"    \033[33mRCA Analysis:\033[0m {rca_summary}", flush=True)

                    rca_details = result_dict.get('rca')
                    if rca_details and rca_details != rca_summary:
                        # Print specific details if they exist and are different
                        # Often 'rca' is the main text block
                        lines = str(rca_details).split('\n')
                        print(f"    \033[33mRCA Detail:\033[0m", flush=True)
                        for line in lines:
                            print(f"      {line}", flush=True)

    # Aggregate results (results list now contains dicts for sequential, objects for parallel)
    for res in results:
        # Normalize to dict
        if hasattr(res, 'to_dict'):
            r = res.to_dict()
        else:
            r = res  # Already a dict from sequential loop

        # (Hooks already run for sequential, need to run for parallel if we supported it)

        suite.results.append(r)

        if r.get('error'):
            suite.errors += 1
        elif r.get('test_passed') is True:
            suite.passed += 1
        elif r.get('test_passed') is False:
            suite.failed += 1
        else:
            suite.skipped += 1

    suite.execution_time = time.time() - start_time
    return suite


def validate_and_get_log_level(local_arg: Any) -> tuple:
    """
    Validate --local argument and extract log level.

    Args:
        local_arg: Value from args.local (None, True, or string level)

    Returns:
        (is_local: bool, log_level: str or None)

    Examples:
        None -> (False, None)              # Not local mode
        True -> (True, 'error')            # Local mode, default log level
        'warning' -> (True, 'warning')     # Local mode, explicit level
        'invalid' -> raises ValueError
    """
    if local_arg is None:
        return False, None

    if local_arg is True:
        return True, 'error'  # Default to error level

    # Must be a string log level
    valid_levels = {'debug', 'info', 'warning', 'error'}
    level = str(local_arg).lower()

    if level not in valid_levels:
        raise ValueError(
            f"Invalid log level '{local_arg}'. "
            f"Must be one of: {', '.join(sorted(valid_levels))}"
        )

    return True, level


def run_suite_local(
        suite_folder: Path,
        config: dict,
        test_files: List[Path],
        suite_name: str = "Local",
        input_message: str = "",
        timeout: int = 120,
        parallel: int = 1,
        logger: Optional[TestLogger] = None,
        sdk_log_level: str = 'error',
        reporter = None,  # ReportPortalReporter instance
) -> SuiteResult:
    """
    Run a suite of pipelines locally without backend.

    Uses LocalSetupStrategy to execute setup steps locally, then runs
    test pipelines using IsolatedPipelineTestRunner.

    Args:
        suite_folder: Path to suite folder
        config: Suite configuration dict
        test_files: List of test file paths to execute
        suite_name: Name for the suite
        input_message: Input message for pipelines
        timeout: Execution timeout per pipeline
        parallel: Number of parallel executions
        logger: Optional TestLogger instance for logging
        sdk_log_level: Log level for alita_sdk loggers (debug, info, warning, error)
        reporter: Optional ReportPortal reporter instance

    Returns:
        SuiteResult with aggregated results
    """
    start_time = time.time()
    suite = SuiteResult(
        suite_name=suite_name,
        total=len(test_files),
    )
    
    # ReportPortal: Report tests directly to launch (no suite nesting)
    rp_suite_id = None

    # Configure file logging for DEBUG-level trace
    # Log file goes to test_results/suites/<suite_name>/run.log
    # Strip 'suites/' prefix from suite_name if present to avoid double path
    log_suite_name = suite_name.replace('suites/', '', 1) if suite_name.startswith('suites/') else suite_name
    log_file = f"test_results/suites/{log_suite_name}/run.log"
    verbose_mode = logger.verbose if logger else False
    configure_file_logging(log_file, sdk_log_level, verbose=verbose_mode)

    if logger:
        logger.debug(f"Configured DEBUG-level file logging to: {log_file}")

    # Create local setup strategy
    local_strategy = LocalSetupStrategy()

    # Create a minimal SetupContext for local execution
    # No backend auth needed, but we need env_vars for substitution
    # Pass logger so setup output appears when verbose=True
    ctx = SetupContext(
        base_url="local://",  # Placeholder, not used in local mode
        project_id=0,  # Placeholder, not used in local mode
        bearer_token="",  # Not needed for local
        verbose=logger.verbose if logger else False,
        dry_run=False,
        logger=logger,  # Pass logger for proper output routing
    )

    # Load env_mapping values before setup
    if config:
        for key, value in config.get("env_mapping", {}).items():
            resolved_value = resolve_env_value(value, ctx.env_vars, env_loader=load_from_env)
            ctx.env_vars[key] = resolved_value
            if logger:
                logger.debug(f"Loaded env_mapping: {key}={resolved_value}")

    # Execute setup steps using local strategy
    # Logger will route output based on verbose flag (verbose=True shows progress)
    if logger:
        logger.section("Executing local setup...")

    setup_result = execute_setup(
        config=config,
        ctx=ctx,
        base_path=suite_folder,
        strategy=local_strategy,
    )

    if not setup_result.get("success"):
        if logger:
            logger.error(f"Local setup failed: {setup_result}")
        suite.errors = 1
        suite.execution_time = time.time() - start_time
        return suite

    # Get env_vars from setup (includes toolkit IDs, names, etc.)
    env_vars = setup_result.get("env_vars", {})

    # Merge and resolve execution.substitutions from pipeline config into env_vars
    # Substitutions can reference setup variables, .env variables, or have defaults
    execution_config = config.get("execution", {})
    substitutions = execution_config.get("substitutions", {})
    if substitutions:
        # Resolve each substitution value using setup vars + env_loader (for .env access)
        for key, value in substitutions.items():
            if isinstance(value, str):
                # Resolve ${VAR} references using both setup env_vars and .env
                resolved = resolve_env_value(value, env_vars, env_loader=load_from_env)
                env_vars[key] = resolved
            else:
                env_vars[key] = value

    # Get tools created by local strategy
    tools = local_strategy.get_tools()

    if logger:
        logger.info(f"Setup completed. Env vars: {list(env_vars.keys())}")
        logger.info(f"Created {len(tools)} toolkit tools")

    if not tools:
        if logger:
            logger.warning("No toolkit tools were created during setup")

    # Create runner with pre-created tools from strategy
    # Pass verbose flag directly from logger (controlled by -v flag)
    runner = IsolatedPipelineTestRunner(
        tools=tools,  # Pass pre-created tools from strategy
        env_vars=env_vars,  # Pass setup env_vars for substitution
        verbose=logger.verbose if logger else False,
        sdk_log_level=sdk_log_level,  # Control alita_sdk logging verbosity
    )

    # Define test execution function for both sequential and parallel modes
    def execute_one_local(test_file: Path) -> dict:
        """Execute a single test and return result dict."""
        result = runner.run_test(
            test_yaml_path=str(test_file),
            input_message=input_message or 'execute',
            timeout=timeout,
            dry_run=False,
        )
        return result.to_dict()

    # Run all tests (sequential or parallel)
    if parallel > 1:
        # Parallel execution
        if logger:
            logger.info(f"Starting parallel execution with {parallel} workers...")
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {executor.submit(execute_one_local, tf): tf for tf in test_files}
            if logger:
                logger.debug(f"Submitted {len(futures)} tests to thread pool")
            
            for future in as_completed(futures):
                test_file = futures[future]
                
                # Start ReportPortal test
                rp_test_id = None
                if reporter and reporter.active:
                    description = load_test_description(test_file)
                    rp_test_id = reporter.start_test(
                        name=test_file.stem,
                        description=description
                    )
                
                try:
                    result_dict = future.result()
                    
                    # Report to ReportPortal
                    if reporter and reporter.active and rp_test_id:
                        reporter.log_result(rp_test_id, result_dict)
                        reporter.finish_test(rp_test_id, result_dict)
                    
                    suite.results.append(result_dict)
                    
                    # Update counters based on result
                    if result_dict.get('error') or not result_dict.get('success'):
                        suite.errors += 1
                        if logger and logger.verbose:
                            logger.error(f"[ERROR] {test_file.name}: {result_dict.get('error', 'Unknown error')}")
                        elif logger and not logger.quiet:
                            print(f"\033[91m✗\033[0m {test_file.name}", flush=True)
                    elif result_dict.get('test_passed') is False:
                        suite.failed += 1
                        if logger and logger.verbose:
                            logger.error(f"[FAIL] {test_file.name}")
                        elif logger and not logger.quiet:
                            print(f"\033[91m✗\033[0m {test_file.name}", flush=True)
                    elif result_dict.get('test_passed') is True:
                        suite.passed += 1
                        if logger and logger.verbose:
                            logger.success(f"[PASS] {test_file.name}")
                        elif logger and not logger.quiet:
                            print(f"\033[92m✓\033[0m {test_file.name}", flush=True)
                    else:
                        suite.skipped += 1
                        if logger and logger.verbose:
                            logger.info(f"[SKIP] {test_file.name}")
                
                except Exception as e:
                    suite.errors += 1
                    error_result = {
                        'success': False,
                        'error': str(e),
                        'test_passed': False,
                        'pipeline_name': test_file.name,
                    }
                    
                    # Report error to ReportPortal
                    if reporter and reporter.active and rp_test_id:
                        reporter.log_result(rp_test_id, error_result)
                        reporter.finish_test(rp_test_id, error_result)
                    
                    suite.results.append(error_result)
                    if logger:
                        logger.error(f"[ERROR] {test_file.name}: {str(e)}")
    else:
        # Sequential execution
        for test_file in test_files:
            if logger:
                logger.separator()
                logger.info(f"Running: {test_file.name}")
                logger.separator()

            # Start ReportPortal test
            rp_test_id = None
            if reporter and reporter.active:
                description = load_test_description(test_file)
                rp_test_id = reporter.start_test(
                    name=test_file.stem,
                    description=description
                )

            result = runner.run_test(
                test_yaml_path=str(test_file),
                input_message=input_message or 'execute',
                timeout=timeout,
                dry_run=False,
            )

            # Report to ReportPortal
            result_dict = result.to_dict()
            if reporter and reporter.active and rp_test_id:
                reporter.log_result(rp_test_id, result_dict)
                reporter.finish_test(rp_test_id, result_dict)

            # Use PipelineResult.to_dict() directly
            suite.results.append(result_dict)

            # Update counters
            if result.error or not result.success:
                suite.errors += 1
                if logger:
                    logger.error(f"EXECUTION ERROR: {result.error}")
            elif result.test_passed is False:
                suite.failed += 1
                if logger:
                    logger.error("TEST FAILED")
            elif result.test_passed is True:
                suite.passed += 1
                if logger:
                    logger.success("TEST PASSED")
            else:
                # success=True but test_passed=None means result cannot be evaluated, mark as skipped
                suite.skipped += 1
                if logger:
                    logger.info("TEST SKIPPED (result indeterminate)")

            if logger and result.execution_time > 0:
                logger.info(f"Execution time: {result.execution_time:.2f}s")

    suite.execution_time = time.time() - start_time
    return suite


def main():
    parser = argparse.ArgumentParser(
        description="Execute a suite of pipelines and report results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("folder", nargs="?", help="Suite folder name")
    parser.add_argument("--pattern", "-p", action="append", help="Pipeline name pattern (can repeat)")
    parser.add_argument("--ids", type=int, nargs="+", help="Specific pipeline IDs")
    parser.add_argument("--base-url", default=None, help="Base URL (default: from env)")
    parser.add_argument("--project-id", type=int, default=None, help="Project ID (default: from env)")
    parser.add_argument("--input", "-i", type=str, default="", help="Input message for pipelines")
    parser.add_argument("--timeout", "-t", type=int, default=None,
                        help="Execution timeout per pipeline (default: from config or 120)")
    parser.add_argument("--parallel", type=int, default=0,
                        help="Number of parallel executions (0=use config, 1=sequential, >1=parallel workers)")
    parser.add_argument("--output-json", help="Save JSON results to file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--exit-code", "-e", action="store_true",
                        help="Use exit code to indicate suite result (0=all pass, 1=failures)")
    parser.add_argument("--env-file", help="Load environment variables from file")
    parser.add_argument("--local", nargs='?', const=True, default=None,
                        help="Local mode: run pipelines without backend. "
                             "Optional: set alita_sdk log level (debug|info|warning|error, default: error)")
    parser.add_argument("--wildcards", "-w", action="store_true",
                        help="Use shell-style wildcards in patterns (*, ?)")
    parser.add_argument("--session-id", "--sid",
                        help="Session ID for parallel execution isolation (matches session-scoped resources)")

    args = parser.parse_args()

    # Load session ID from arg or environment
    session_id = args.session_id or load_from_env("SESSION_ID")

    # Load environment file if provided
    if args.env_file:
        from seed_pipelines import set_env_file
        env_path = Path(args.env_file)
        if not env_path.exists():
            print(f"Error: Env file not found: {args.env_file}", file=sys.stderr)
            sys.exit(1)
        set_env_file(env_path)
        if args.verbose:
            print(f"Loading environment from: {args.env_file}")

    # Validate arguments
    if not args.folder and not args.pattern and not args.ids:
        parser.error("Either folder, --pattern, or --ids is required")

    # Parse suite specification
    folder_name = None
    pipeline_file = None
    folder_path = None
    config = None
    env_vars = {}
    suite_name = "Custom"
    pipelines = []  # For remote mode
    test_files = []  # For local mode
    patterns = args.pattern if args.pattern else ["*"]

    # Remote mode variables (initialized here to avoid warnings)
    base_url = None
    project_id = None
    headers = None

    if args.folder:
        folder_name, pipeline_file = parse_suite_spec(args.folder)
        suite_name = args.folder
        folder_path = Path(__file__).parent.parent / folder_name

        if not folder_path.exists():
            error_msg = f"Suite folder not found: {folder_path}"
            print(f"Error: {error_msg}", file=sys.stderr)
            sys.exit(1)

        # Load config
        config = load_config(folder_path, pipeline_file)
        if not config:
            error_msg = f"Config not found in {folder_path}"
            print(f"Error: {error_msg}", file=sys.stderr)
            sys.exit(1)

    # ========================================
    # PIPELINE DISCOVERY: Local vs Remote
    # ========================================
    # Validate and extract log level from --local argument
    is_local, sdk_log_level = validate_and_get_log_level(args.local)

    if is_local:
        # LOCAL: Get test files from folder (stored as pipelines for unified handling)
        if not args.folder:
            parser.error("--local mode requires a folder argument")

        pipelines = find_tests_in_suite(folder_path, patterns, config, args.wildcards)
    else:
        # REMOTE: Get pipelines from folder and match with backend
        base_url = args.base_url or load_from_env("BASE_URL") or load_from_env(
            "DEPLOYMENT_URL") or "http://192.168.68.115"
        project_id = args.project_id or int(load_from_env("PROJECT_ID") or "2")
        headers = get_auth_headers()

        if not headers:
            print("Error: No authentication token found in environment", file=sys.stderr)
            sys.exit(1)

        if args.folder:
            pipelines = get_pipelines_from_folder(base_url, project_id, folder_name, headers, pipeline_file, session_id=session_id)
            if not pipelines:
                # Try to get by pattern matching folder name prefix
                if folder_path.exists():
                    test_dir = folder_path
                    if config and "execution" in config:
                        test_subdir = config["execution"].get("test_directory")
                        if test_subdir:
                            test_dir = folder_path / test_subdir

                    # Get names from YAML files in test directory
                    names = []
                    for yaml_file in sorted(test_dir.glob("test_case_*.yaml")):
                        try:
                            with open(yaml_file) as f:
                                data = yaml.safe_load(f)
                                if data and "name" in data:
                                    # Apply session prefix to match session-scoped pipelines
                                    names.append(apply_session_to_pipeline_name(data["name"], session_id))
                        except Exception:
                            continue

                    if names:
                        # Match by exact names
                        url = f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}?limit=500"
                        response = requests.get(url, headers=headers)
                        if response.status_code == 200:
                            all_pipelines = response.json().get("rows", [])
                            for name in names:
                                for p in all_pipelines:
                                    if p.get("name") == name:
                                        full = get_pipeline_by_id(base_url, project_id, p["id"], headers)
                                        if full:
                                            pipelines.append(full)
                                        break

        # If pattern is specified along with folder, filter the folder's pipelines
        # Otherwise, pattern acts as a standalone filter across all pipelines
        if args.pattern:
            if args.folder:
                # Filter already collected pipelines by pattern
                filtered_pipelines = []
                for p in pipelines:
                    name = p.get("name", "")
                    # Use shared pattern matching utility
                    if matches_any_pattern(name, args.pattern, args.wildcards):
                        filtered_pipelines.append(p)
                pipelines = filtered_pipelines
                suite_name = f"{suite_name} (filtered: {', '.join(args.pattern)})"
            else:
                # Pattern as standalone filter
                suite_name = f"Pattern: {', '.join(args.pattern)}"
                pipelines = get_pipelines_by_pattern(base_url, project_id, args.pattern, headers, args.wildcards)

        if args.ids:
            suite_name = f"IDs: {', '.join(map(str, args.ids))}"
            pipelines.extend(get_pipelines_by_ids(base_url, project_id, args.ids, headers))

        # Deduplicate pipelines by ID (in case any got added multiple times)
        seen_ids = set()
        unique_pipelines = []
        for p in pipelines:
            pid = p.get('id')
            if pid not in seen_ids:
                seen_ids.add(pid)
                unique_pipelines.append(p)
        pipelines = unique_pipelines

        # Build env_vars from environment and config (remote only)
        if config:
            # Load env from config's env_mapping section
            for key, value in config.get("env_mapping", {}).items():
                env_vars[key] = resolve_env_value(value, env_vars, env_loader=load_from_env)
            # Load composable pipeline IDs if available
            for cp in config.get("composable_pipelines", []):
                for save_item in cp.get("save_to_env", []):
                    key = save_item.get("key")
                    if key:
                        # Try to load from environment
                        env_value = load_from_env(key)
                        if env_value:
                            env_vars[key] = env_value

    # ========================================
    # VALIDATE: Common for both modes
    # ========================================
    if not pipelines:
        pattern_display = ', '.join(patterns) if patterns != ['*'] else '*'
        error_msg = f"No pipelines found matching pattern(s) '{pattern_display}'" if args.local else "No pipelines found matching criteria"
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Determine effective timeout: CLI arg > config value > default 120
    # Extract timeout from config with validation
    config_timeout = 120  # Default
    if config:
        raw_timeout = config.get("execution", {}).get("settings", {}).get("timeout")
        # Validate: must be a positive integer (not None, not blank, not zero/negative)
        if raw_timeout is not None and isinstance(raw_timeout, int) and raw_timeout > 0:
            config_timeout = raw_timeout

    effective_timeout = args.timeout if args.timeout is not None else config_timeout

    # Determine effective parallel: CLI arg > config value > default 1
    config_parallel = 1  # Default (sequential)
    if config:
        raw_parallel = config.get("execution", {}).get("settings", {}).get("parallel")
        # Validate: must be a positive integer (not None, not blank, not zero/negative)
        if raw_parallel is not None and isinstance(raw_parallel, int) and raw_parallel > 0:
            config_parallel = raw_parallel

    # Use CLI arg if explicitly provided (> 0), otherwise use config value
    effective_parallel = args.parallel if args.parallel > 0 else config_parallel

    # Create logger instance
    # Always create logger when verbose is True, otherwise None (no console output)
    logger = TestLogger(verbose=args.verbose) if args.verbose else None

    if logger:
        logger.info(f"Found {len(pipelines)} pipeline(s) to execute")
        if args.timeout is None and config:
            logger.debug(f"Using timeout from config: {effective_timeout}s")
        if args.parallel <= 0 and config_parallel > 1:
            logger.info(f"Using parallel execution from config: {effective_parallel} workers")
        elif args.parallel == 1:
            logger.info(f"Parallel execution disabled (forced sequential)")
        elif effective_parallel > 1:
            logger.info(f"Using parallel execution: {effective_parallel} workers")

    # ========================================
    # REPORTPORTAL SETUP
    # ========================================
    # Create ReportPortal reporter if enabled
    reporter = None
    if RP_AVAILABLE and create_reporter:
        reporter = create_reporter(logger)
        if reporter and reporter.active and logger:
            logger.info("ReportPortal reporting enabled")

    # ========================================
    # EXECUTION: Local vs Remote
    # ========================================
    # Wrap execution with ReportPortal launch context
    launch_name = f"Alita SDK - {suite_name}"
    launch_description = f"Test suite execution: {len(pipelines)} test(s)"
    
    # Execute with or without ReportPortal
    if reporter and reporter.active:
        with reporter.launch(launch_name, description=launch_description):
            if is_local:
                result = run_suite_local(
                    suite_folder=folder_path,
                    config=config,
                    test_files=pipelines,  # pipelines contains test file paths in local mode
                    suite_name=suite_name,
                    input_message=args.input,
                    timeout=effective_timeout,
                    parallel=effective_parallel,
                    logger=logger,
                    sdk_log_level=sdk_log_level or 'error',  # Pass log level, default to error
                    reporter=reporter,
                )
            else:
                result = run_suite(
                    base_url=base_url,
                    project_id=project_id,
                    pipelines=pipelines,
                    suite_name=suite_name,
                    input_message=args.input,
                    timeout=effective_timeout,
                    parallel=effective_parallel,
                    logger=logger,
                    config=config,
                    env_vars=env_vars,
                    headers=headers,
                    reporter=reporter,
                )
    else:
        # Execute without ReportPortal
        if is_local:
            result = run_suite_local(
                suite_folder=folder_path,
                config=config,
                test_files=pipelines,  # pipelines contains test file paths in local mode
                suite_name=suite_name,
                input_message=args.input,
                timeout=effective_timeout,
                parallel=effective_parallel,
                logger=logger,
                sdk_log_level=sdk_log_level or 'error',  # Pass log level, default to error
            )
        else:
            result = run_suite(
                base_url=base_url,
                project_id=project_id,
                pipelines=pipelines,
                suite_name=suite_name,
                input_message=args.input,
                timeout=effective_timeout,
                parallel=effective_parallel,
                logger=logger,
                config=config,
                env_vars=env_vars,
                headers=headers,
            )

    # Output results
    # Save JSON results to file if --output-json specified
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(result.to_json())

    # Always print summary to console (unless verbose mode already showed details)
    # Pass absolute path to results file for clearer error messages
    results_file_abs = str(Path(args.output_json).resolve()) if args.output_json else None
    print(result.to_summary(results_file=results_file_abs))

    # Exit code
    if args.exit_code:
        sys.exit(0 if result.all_passed else 1)


if __name__ == "__main__":
    main()
