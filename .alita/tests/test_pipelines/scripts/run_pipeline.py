#!/usr/bin/env python3
"""
Execute a pipeline and return results in a structured format.

Usage:
    python run_pipeline.py <pipeline_id> [options]
    python run_pipeline.py --name "Pipeline Name" [options]

Examples:
    # Execute by ID
    python run_pipeline.py 123

    # Execute by name
    python run_pipeline.py --name "GH1 - List Branches"

    # With custom input and timeout
    python run_pipeline.py 123 --input "test message" --timeout 60

    # JSON output for scripting
    python run_pipeline.py 123 --json

    # Verbose output
    python run_pipeline.py 123 -v
"""

import argparse
import ast
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Any

import requests

# Import shared pattern matching utilities
from pattern_matcher import matches_pattern


@dataclass
class PipelineResult:
    """Structured result from pipeline execution."""
    success: bool
    pipeline_id: int
    pipeline_name: str
    version_id: Optional[int] = None
    test_passed: Optional[bool] = None
    execution_time: float = 0.0
    output: Any = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


def load_from_env(var_name: str) -> Optional[str]:
    """Load value from environment variable or .env file."""
    value = os.environ.get(var_name)
    if value:
        return value

    env_paths = [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent.parent.parent / ".env",  # alita-sdk root
        Path(__file__).parent.parent.parent.parent.parent / ".env",  # elitea root
    ]

    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{var_name}="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def get_auth_headers(include_content_type: bool = False) -> dict:
    """Get authentication headers from environment."""
    token = load_from_env("AUTH_TOKEN") or load_from_env("ELITEA_TOKEN") or load_from_env("API_KEY")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def get_pipeline_by_id(base_url: str, project_id: int, pipeline_id: int, headers: dict) -> Optional[dict]:
    """Get pipeline details by ID."""
    url = f"{base_url}/api/v2/elitea_core/application/prompt_lib/{project_id}/{pipeline_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None


def get_pipeline_by_name(base_url: str, project_id: int, name: str, headers: dict) -> Optional[dict]:
    """
    Get pipeline details by name or pattern.
    
    Supports both exact name matching and flexible pattern matching
    (case-insensitive, underscore/space/hyphen agnostic).
    """
    url = f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}?limit=500"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None

    data = response.json()
    
    # First try exact match (fast path)
    for pipeline in data.get("rows", []):
        if pipeline.get("name") == name:
            return get_pipeline_by_id(base_url, project_id, pipeline["id"], headers)
    
    # Fall back to pattern matching (flexible)
    for pipeline in data.get("rows", []):
        if matches_pattern(pipeline.get("name", ""), name):
            return get_pipeline_by_id(base_url, project_id, pipeline["id"], headers)
    
    return None


def execute_pipeline(
    base_url: str,
    project_id: int,
    pipeline: dict,
    input_message: str = "",
    timeout: int = 120,
    verbose: bool = False,
    verbose_to_stderr: bool = False
) -> PipelineResult:
    """Execute a pipeline using the v2 predict API (synchronous).
    
    Args:
        verbose_to_stderr: If True and verbose is True, write verbose output to stderr
    """
    start_time = time.time()
    headers = get_auth_headers(include_content_type=True)

    pipeline_id = pipeline["id"]
    pipeline_name = pipeline.get("name", f"Pipeline {pipeline_id}")

    # Get the latest version
    versions = pipeline.get("versions", [])
    if not versions:
        return PipelineResult(
            success=False,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            error="No versions found for pipeline"
        )

    version = versions[0]  # Latest version
    version_id = version.get("id")

    if verbose:
        output_stream = sys.stderr if verbose_to_stderr else sys.stdout
        print(f"Executing: {pipeline_name} (ID: {pipeline_id}, Version: {version_id})", file=output_stream)

    # Use v2 predict API for synchronous execution
    predict_url = f"{base_url}/api/v2/elitea_core/predict/prompt_lib/{project_id}/{version_id}"
    payload = {
        "chat_history": [],
        "user_input": input_message or "execute"
    }

    if verbose:
        output_stream = sys.stderr if verbose_to_stderr else sys.stdout
        print(f"  POST {predict_url}", file=output_stream)
        print(f"  Payload: {json.dumps(payload)}", file=output_stream)

    try:
        response = requests.post(
            predict_url,
            headers=headers,
            json=payload,
            timeout=timeout
        )
    except requests.exceptions.Timeout:
        execution_time = time.time() - start_time
        return PipelineResult(
            success=False,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            version_id=version_id,
            execution_time=execution_time,
            error=f"Request timed out after {timeout}s"
        )
    except Exception as e:
        execution_time = time.time() - start_time
        return PipelineResult(
            success=False,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            version_id=version_id,
            execution_time=execution_time,
            error=f"Request failed: {e}"
        )

    execution_time = time.time() - start_time

    if verbose:
        output_stream = sys.stderr if verbose_to_stderr else sys.stdout
        print(f"  Response: {response.status_code}", file=output_stream)

    # Handle HTTP errors
    if response.status_code not in (200, 201):
        error_text = response.text[:500] if response.text else "No response body"
        return PipelineResult(
            success=False,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            version_id=version_id,
            execution_time=execution_time,
            error=f"HTTP {response.status_code}: {error_text}"
        )

    # Parse response
    try:
        result_data = response.json()
    except json.JSONDecodeError:
        return PipelineResult(
            success=False,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            version_id=version_id,
            execution_time=execution_time,
            output=response.text,
            error="Response is not valid JSON"
        )

    # Check for error in response (only if error is non-null)
    if isinstance(result_data, dict) and result_data.get("error"):
        return PipelineResult(
            success=False,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            version_id=version_id,
            execution_time=execution_time,
            output=result_data,
            error=str(result_data.get("error"))
        )

    # Extract test_passed from result
    test_passed = None
    output = result_data
    detected_error = None  # Track user-friendly error messages

    # Check various result structures for test_passed
    if isinstance(result_data, dict):
        # Direct test_passed field
        if "test_passed" in result_data:
            test_passed = result_data.get("test_passed")
        # Nested in result field
        elif "result" in result_data:
            nested = result_data.get("result", {})
            if isinstance(nested, dict):
                if "test_passed" in nested:
                    test_passed = nested.get("test_passed")
                # Nested in result.test_results (pyodide sandbox output)
                elif "test_results" in nested:
                    test_results = nested.get("test_results", {})
                    if isinstance(test_results, dict) and "test_passed" in test_results:
                        test_passed = test_results.get("test_passed")
        # Check in chat_history (pipeline response format)
        elif "chat_history" in result_data:
            chat_history = result_data.get("chat_history", [])
            for msg in chat_history:
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    # Check for tool call error in content that indicates failure
                    if isinstance(content, str) and ("Error executing code: [Errno 7]" in content or "[Errno 7] Argument list too long" in content):
                         test_passed = False
                         detected_error = "Content too large: The data payload exceeded system limits. Consider reducing the amount of data being processed."
                         output = {"error": detected_error, "raw_content": content[:500]}
                         break

                    if isinstance(content, str) and content.startswith("{"):
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict):
                                if "test_passed" in parsed:
                                    test_passed = parsed.get("test_passed")
                                    if isinstance(output, dict):
                                        output["result"] = parsed
                                    else:
                                        output = parsed
                                    break
                                elif "result" in parsed:
                                    nested = parsed.get("result", {})
                                    if isinstance(nested, dict):
                                        if "test_passed" in nested:
                                            test_passed = nested.get("test_passed")
                                            if isinstance(output, dict):
                                                output["result"] = nested
                                            else:
                                                output = nested
                                            break
                                        # Nested in result.test_results (pyodide sandbox output)
                                        elif "test_results" in nested:
                                            test_results = nested.get("test_results", {})
                                            if isinstance(test_results, dict) and "test_passed" in test_results:
                                                test_passed = test_results.get("test_passed")
                                                if isinstance(output, dict):
                                                    output["result"] = test_results
                                                else:
                                                    output = test_results
                                                break
                        except (json.JSONDecodeError, TypeError):
                            pass
        # Check in tool_calls_dict (pipeline tool execution results)
        if test_passed is None and "tool_calls_dict" in result_data:
            tool_calls = result_data.get("tool_calls_dict", {})
            if isinstance(tool_calls, dict):
                # Get all tool calls sorted by timestamp_finish (latest first)
                sorted_calls = sorted(
                    tool_calls.values(),
                    key=lambda x: x.get("timestamp_finish", "") if isinstance(x, dict) else "",
                    reverse=True
                )
                for tool_call in sorted_calls:
                    if not isinstance(tool_call, dict):
                        continue
                    content = tool_call.get("content", "") or tool_call.get("tool_output", "")

                    # Check for error indicating test failure
                    if isinstance(content, str) and ("[Errno 7] Argument list too long" in content or "Error executing code: [Errno 7]" in content):
                        test_passed = False
                        detected_error = "Content too large: The data payload exceeded system limits. Consider reducing the amount of data being processed."
                        break

                    if isinstance(content, str) and content.startswith("{"):
                        try:
                            # Use ast.literal_eval for Python dict repr format
                            parsed = ast.literal_eval(content)
                            if isinstance(parsed, dict):
                                if "test_passed" in parsed:
                                    test_passed = parsed.get("test_passed")
                                    break
                                elif "result" in parsed:
                                    nested = parsed.get("result", {})
                                    if isinstance(nested, dict):
                                        if "test_passed" in nested:
                                            test_passed = nested.get("test_passed")
                                            break
                                        elif "test_results" in nested:
                                            test_results = nested.get("test_results", {})
                                            if isinstance(test_results, dict) and "test_passed" in test_results:
                                                test_passed = test_results.get("test_passed")
                                                break
                        except (ValueError, TypeError, SyntaxError):
                            pass

        # Check in response/output field
        if test_passed is None and "response" in result_data:
            resp = result_data.get("response")
            if isinstance(resp, dict) and "test_passed" in resp:
                test_passed = resp.get("test_passed")
            elif isinstance(resp, str):
                try:
                    parsed = json.loads(resp)
                    if isinstance(parsed, dict) and "test_passed" in parsed:
                        test_passed = parsed.get("test_passed")
                        if isinstance(output, dict):
                            output["result"] = parsed
                        else:
                            output = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

    return PipelineResult(
        success=True,
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        version_id=version_id,
        test_passed=test_passed,
        execution_time=execution_time,
        output=output,
        error=detected_error
    )


def main():
    parser = argparse.ArgumentParser(
        description="Execute a pipeline and return results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("pipeline_id", nargs="?", type=int, help="Pipeline ID to execute")
    parser.add_argument("--name", "-n", type=str, help="Pipeline name (alternative to ID)")
    parser.add_argument("--base-url", default=None, help="Base URL (default: from env)")
    parser.add_argument("--project-id", type=int, default=None, help="Project ID (default: from env)")
    parser.add_argument("--input", "-i", type=str, default="", help="Input message for pipeline")
    parser.add_argument("--timeout", "-t", type=int, default=120, help="Execution timeout in seconds")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--exit-code", "-e", action="store_true",
                        help="Use exit code to indicate test result (0=pass, 1=fail)")

    args = parser.parse_args()

    # Validate arguments
    if not args.pipeline_id and not args.name:
        parser.error("Either pipeline_id or --name is required")

    # Load configuration
    base_url = args.base_url or load_from_env("BASE_URL") or load_from_env("DEPLOYMENT_URL") or "http://192.168.68.115"
    project_id = args.project_id or int(load_from_env("PROJECT_ID") or "2")
    headers = get_auth_headers()

    if "Authorization" not in headers:
        if args.json:
            print(json.dumps({"success": False, "error": "No authentication token found"}))
        else:
            print("Error: No authentication token found in environment")
        sys.exit(1)

    # Get pipeline
    if args.pipeline_id:
        pipeline = get_pipeline_by_id(base_url, project_id, args.pipeline_id, headers)
    else:
        pipeline = get_pipeline_by_name(base_url, project_id, args.name, headers)

    if not pipeline:
        error_msg = f"Pipeline not found: {args.pipeline_id or args.name}"
        if args.json:
            print(json.dumps({"success": False, "error": error_msg}))
        else:
            print(f"Error: {error_msg}")
        sys.exit(1)

    # Execute pipeline
    result = execute_pipeline(
        base_url=base_url,
        project_id=project_id,
        pipeline=pipeline,
        input_message=args.input,
        timeout=args.timeout,
        verbose=args.verbose
    )

    # Output results
    if args.json:
        print(result.to_json())
    else:
        status = "PASSED" if result.test_passed else ("FAILED" if result.test_passed is False else "COMPLETED")
        print(f"\n{'=' * 60}")
        print(f"Pipeline: {result.pipeline_name} (ID: {result.pipeline_id})")
        print(f"Version: {result.version_id}")
        print(f"Status: {status}")
        print(f"Execution Time: {result.execution_time:.2f}s")

        if result.error:
            print(f"Error: {result.error}")

        if result.output:
            print(f"\nOutput:")
            if isinstance(result.output, dict):
                print(json.dumps(result.output, indent=2, default=str))
            else:
                print(result.output)

        print(f"{'=' * 60}")

    # Exit code based on test result
    if args.exit_code:
        if result.test_passed is True:
            sys.exit(0)
        elif result.test_passed is False:
            sys.exit(1)
        else:
            sys.exit(2)  # Unknown/no test result


if __name__ == "__main__":
    main()
