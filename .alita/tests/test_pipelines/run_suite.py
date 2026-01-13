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
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, List, Any
from datetime import datetime, timezone

import requests

# Import from run_pipeline module
from run_pipeline import (
    load_from_env,
    get_auth_headers,
    get_pipeline_by_id,
    execute_pipeline,
    PipelineResult
)


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
    pipeline_names = []
    for yaml_file in sorted(folder_path.glob("*.yaml")):
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
    verbose: bool = False
) -> SuiteResult:
    """Execute multiple pipelines and aggregate results."""
    start_time = time.time()
    suite = SuiteResult(suite_name=suite_name, total=len(pipelines))

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

    # Aggregate results
    for result in results:
        suite.results.append(result.to_dict())

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
                # Get names from YAML files
                names = []
                for yaml_file in sorted(folder_path.glob("*.yaml")):
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

    # Execute suite
    result = run_suite(
        base_url=base_url,
        project_id=project_id,
        pipelines=pipelines,
        suite_name=suite_name,
        input_message=args.input,
        timeout=args.timeout,
        parallel=args.parallel,
        verbose=args.verbose
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
