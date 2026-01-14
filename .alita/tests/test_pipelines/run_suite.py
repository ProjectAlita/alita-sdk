#!/usr/bin/env python3
"""
Execute a suite of pipelines and report aggregated results.

Usage:
    python run_suite.py <suite_folder> [options]
    python run_suite.py --pattern "GH*" [options]

Examples:
    # Run all pipelines in a folder
    python run_suite.py github_toolkit

    # Run pipelines matching a pattern
    python run_suite.py --pattern "GH1*" --pattern "GH2*"

    # Run specific pipeline IDs
    python run_suite.py --ids 267 268 269

    # JSON output for CI/CD
    python run_suite.py github_toolkit --json

    # Parallel execution
    python run_suite.py github_toolkit --parallel 4
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

import requests
import yaml

# Import from run_pipeline module
from run_pipeline import (
    load_from_env,
    get_auth_headers,
    get_pipeline_by_id,
    execute_pipeline,
    PipelineResult
)


def load_config(suite_folder: Path) -> dict | None:
    """Load pipeline.yaml (or config.yaml for backwards compatibility) from a suite folder if it exists."""
    # Try pipeline.yaml first (new convention)
    config_path = suite_folder / "pipeline.yaml"
    if not config_path.exists():
        # Fall back to config.yaml for backwards compatibility
        config_path = suite_folder / "config.yaml"
        if not config_path.exists():
            return None

    with open(config_path) as f:
        return yaml.safe_load(f)


def resolve_env_value(value: Any, env_vars: dict) -> Any:
    """Resolve environment variable references in a value."""
    if isinstance(value, str):
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'

        def replacer(match):
            var_name = match.group(1)
            default = match.group(2)

            if var_name in env_vars:
                return str(env_vars[var_name])
            env_value = load_from_env(var_name)
            if env_value:
                return env_value
            if default is not None:
                return default
            return match.group(0)

        return re.sub(pattern, replacer, value)
    elif isinstance(value, dict):
        return {k: resolve_env_value(v, env_vars) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_value(v, env_vars) for v in value]
    return value


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
    verbose: bool = False
) -> dict:
    """Invoke a composable pipeline for a hook.

    Args:
        base_url: Platform base URL
        project_id: Project ID
        pipeline_id: The composable pipeline ID to invoke
        hook_input: Input data for the pipeline
        headers: Auth headers
        timeout: Execution timeout
        verbose: Verbose output

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
        verbose=verbose
    )

    if not result.success:
        return {"success": False, "error": result.error}

    # Extract output from chat_history messages
    # Composable pipelines output to messages, which appear in chat_history
    output_data = result.output
    extracted_output = {}

    if verbose:
        print(f"    RCA output_data type: {type(output_data).__name__}")
        if isinstance(output_data, dict):
            print(f"    RCA output_data keys: {list(output_data.keys())}")

    if isinstance(output_data, dict):
        # Check if output is already the data we need
        if "rca_result" in output_data or "rca_summary" in output_data:
            extracted_output = output_data
        # Otherwise extract from chat_history
        elif "chat_history" in output_data:
            chat_history = output_data.get("chat_history", [])
            if verbose:
                print(f"    RCA chat_history length: {len(chat_history)}")
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
                                if verbose:
                                    print(f"    RCA extracted from JSON string, keys: {list(parsed.keys())}")
                                break
                        except json.JSONDecodeError:
                            pass
                    # Or if content is already a dict
                    elif isinstance(content, dict):
                        extracted_output = content
                        if verbose:
                            print(f"    RCA extracted from dict content, keys: {list(content.keys())}")
                        break

    # Unwrap 'result' envelope if present (from code nodes)
    if isinstance(extracted_output, dict) and "result" in extracted_output:
        if isinstance(extracted_output["result"], dict):
            extracted_output = extracted_output["result"]
            if verbose:
                print(f"    RCA unwrapped 'result' envelope, keys: {list(extracted_output.keys())}")

    if verbose:
        print(f"    RCA extracted_output keys: {list(extracted_output.keys()) if extracted_output else 'None'}")
    return {"success": True, "output": extracted_output}


def run_post_test_hooks(
    base_url: str,
    project_id: int,
    result: dict,
    hooks_config: list,
    env_vars: dict,
    headers: dict,
    timeout: int = 120,
    verbose: bool = False
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
        verbose: Verbose output

    Returns:
        Updated test result with hook outputs merged
    """
    for hook in hooks_config:
        hook_name = hook.get("name", "unnamed")
        condition = hook.get("condition", "")
        pipeline_id = resolve_env_value(hook.get("pipeline_id"), env_vars)

        if not pipeline_id:
            if verbose:
                print(f"    Skipping hook '{hook_name}': no pipeline_id")
            continue

        # Evaluate condition
        if not evaluate_condition(condition, result):
            if verbose:
                print(f"    Skipping hook '{hook_name}': condition not met")
            continue

        if verbose:
            print(f"    Running hook: {hook_name}")

        # Build input from result
        input_mapping = hook.get("input_mapping", {})
        hook_input = build_hook_input(input_mapping, result)

        # Invoke the hook pipeline
        try:
            pipeline_id_int = int(pipeline_id)
        except (ValueError, TypeError):
            if verbose:
                print(f"    Warning: Invalid pipeline_id '{pipeline_id}'")
            continue

        hook_result = invoke_hook_pipeline(
            base_url=base_url,
            project_id=project_id,
            pipeline_id=pipeline_id_int,
            hook_input=hook_input,
            headers=headers,
            timeout=timeout,
            verbose=verbose
        )

        if hook_result.get("success"):
            # Merge output back to result
            output_mapping = hook.get("output_mapping", {})
            result = merge_hook_output(result, hook_result.get("output", {}), output_mapping)
            if verbose:
                print(f"    Hook '{hook_name}' completed successfully")
        else:
            if verbose:
                print(f"    Hook '{hook_name}' failed: {hook_result.get('error')}")

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

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"\n{'=' * 60}",
            f"Suite: {self.suite_name}",
            f"{'=' * 60}",
            f"Total: {self.total} | Passed: {self.passed} | Failed: {self.failed} | Errors: {self.errors}",
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

            error = f"\n      Error: {error_msg[:100]}..." if error_msg else ""
            lines.append(f"  {status} {name} ({time_str}){error}")

        lines.append(f"\n{'=' * 60}")
        return "\n".join(lines)


def get_pipelines_from_folder(
    base_url: str,
    project_id: int,
    folder_name: str,
    headers: dict
) -> List[dict]:
    """Get pipelines that match the folder's test case names."""
    # Read YAML files to get pipeline names
    folder_path = Path(__file__).parent / folder_name
    if not folder_path.exists():
        return []

    import yaml

    # Check if there's a pipeline.yaml with test_directory setting
    test_dir = folder_path
    config_path = folder_path / "pipeline.yaml"
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
    for yaml_file in sorted(test_dir.glob("test_case_*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if data and "name" in data:
                    pipeline_names.append(data["name"])
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
            if p.get("name") == name:
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
    headers: dict
) -> List[dict]:
    """Get pipelines matching name patterns."""
    import fnmatch

    url = f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}?limit=500"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []

    all_pipelines = response.json().get("rows", [])
    matched = []

    for p in all_pipelines:
        name = p.get("name", "")
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                full = get_pipeline_by_id(base_url, project_id, p["id"], headers)
                if full:
                    matched.append(full)
                break

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
    verbose: bool = False,
    config: dict = None,
    env_vars: dict = None,
    headers: dict = None,
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
        verbose: Verbose output
        config: Suite config.yaml (optional, for hooks)
        env_vars: Environment variables for hook substitution
        headers: Auth headers (for hook pipeline invocation)
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
        if post_test_hooks and verbose:
            print(f"Post-test hooks configured: {len(post_test_hooks)}")

    def execute_one(pipeline: dict) -> PipelineResult:
        return execute_pipeline(
            base_url=base_url,
            project_id=project_id,
            pipeline=pipeline,
            input_message=input_message,
            timeout=timeout,
            verbose=verbose
        )

    results = []

    if parallel > 1:
        # Parallel execution
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {executor.submit(execute_one, p): p for p in pipelines}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    if verbose:
                        status = "PASS" if result.test_passed else "FAIL"
                        print(f"  [{status}] {result.pipeline_name}")
                except Exception as e:
                    pipeline = futures[future]
                    results.append(PipelineResult(
                        success=False,
                        pipeline_id=pipeline.get("id", 0),
                        pipeline_name=pipeline.get("name", "Unknown"),
                        error=str(e)
                    ))
    else:
        # Sequential execution
        for pipeline in pipelines:
            if verbose:
                print(f"Running: {pipeline.get('name')}...")

            result = execute_one(pipeline)
            results.append(result)

            if verbose:
                status = "PASS" if result.test_passed else "FAIL"
                print(f"  [{status}] {result.execution_time:.1f}s")

    # Aggregate results and run post-test hooks
    for result in results:
        result_dict = result.to_dict()

        # Run post-test hooks (e.g., RCA on failure)
        if post_test_hooks:
            result_dict = run_post_test_hooks(
                base_url=base_url,
                project_id=project_id,
                result=result_dict,
                hooks_config=post_test_hooks,
                env_vars=env_vars,
                headers=headers,
                timeout=timeout,
                verbose=verbose
            )

        suite.results.append(result_dict)

        if result.error:
            suite.errors += 1
        elif result.test_passed is True:
            suite.passed += 1
        elif result.test_passed is False:
            suite.failed += 1
        else:
            suite.skipped += 1

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
    parser.add_argument("--timeout", "-t", type=int, default=120, help="Execution timeout per pipeline")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel executions")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--exit-code", "-e", action="store_true",
                        help="Use exit code to indicate suite result (0=all pass, 1=failures)")
    parser.add_argument("--env-file", help="Load environment variables from file")

    args = parser.parse_args()

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

    # Load configuration
    base_url = args.base_url or load_from_env("BASE_URL") or load_from_env("DEPLOYMENT_URL") or "http://192.168.68.115"
    project_id = args.project_id or int(load_from_env("PROJECT_ID") or "2")
    headers = get_auth_headers()

    if not headers:
        if args.json:
            print(json.dumps({"success": False, "error": "No authentication token found"}))
        else:
            print("Error: No authentication token found in environment")
        sys.exit(1)

    # Get pipelines to execute
    pipelines = []
    suite_name = "Custom"

    if args.folder:
        suite_name = args.folder
        pipelines = get_pipelines_from_folder(base_url, project_id, args.folder, headers)
        if not pipelines:
            # Try to get by pattern matching folder name prefix
            import yaml
            folder_path = Path(__file__).parent / args.folder
            if folder_path.exists():
                # Check if there's a pipeline.yaml with test_directory setting
                test_dir = folder_path
                config_path = folder_path / "pipeline.yaml"
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

                # Get names from YAML files in test directory
                names = []
                for yaml_file in sorted(test_dir.glob("test_case_*.yaml")):
                    try:
                        with open(yaml_file) as f:
                            data = yaml.safe_load(f)
                            if data and "name" in data:
                                names.append(data["name"])
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

    if args.pattern:
        suite_name = f"Pattern: {', '.join(args.pattern)}"
        pipelines.extend(get_pipelines_by_pattern(base_url, project_id, args.pattern, headers))

    if args.ids:
        suite_name = f"IDs: {', '.join(map(str, args.ids))}"
        pipelines.extend(get_pipelines_by_ids(base_url, project_id, args.ids, headers))

    if not pipelines:
        error_msg = "No pipelines found matching criteria"
        if args.json:
            print(json.dumps({"success": False, "error": error_msg}))
        else:
            print(f"Error: {error_msg}")
        sys.exit(1)

    if args.verbose:
        print(f"Found {len(pipelines)} pipeline(s) to execute")

    # Load config for hooks
    config = None
    env_vars = {}
    if args.folder:
        folder_path = Path(__file__).parent / args.folder
        config = load_config(folder_path)

        # Build env_vars from environment and config
        if config:
            # Load env from config's env_mapping section
            for key, value in config.get("env_mapping", {}).items():
                env_vars[key] = resolve_env_value(value, env_vars)
            # Load composable pipeline IDs if available
            for cp in config.get("composable_pipelines", []):
                for save_item in cp.get("save_to_env", []):
                    key = save_item.get("key")
                    if key:
                        # Try to load from environment
                        env_value = load_from_env(key)
                        if env_value:
                            env_vars[key] = env_value

    # Execute suite
    result = run_suite(
        base_url=base_url,
        project_id=project_id,
        pipelines=pipelines,
        suite_name=suite_name,
        input_message=args.input,
        timeout=args.timeout,
        parallel=args.parallel,
        verbose=args.verbose,
        config=config,
        env_vars=env_vars,
        headers=headers,
    )

    # Output results
    if args.json:
        print(result.to_json())
    else:
        print(result.to_summary())

    # Exit code
    if args.exit_code:
        sys.exit(0 if result.all_passed else 1)


if __name__ == "__main__":
    main()
