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
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Any

import requests


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
    """Get pipeline details by name."""
    url = f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}?limit=500"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None

    data = response.json()
    for pipeline in data.get("rows", []):
        if pipeline.get("name") == name:
            return get_pipeline_by_id(base_url, project_id, pipeline["id"], headers)
    return None


def execute_pipeline(
    base_url: str,
    project_id: int,
    pipeline: dict,
    input_message: str = "",
    timeout: int = 120,
    verbose: bool = False
) -> PipelineResult:
    """Execute a pipeline using the v2 predict API (synchronous)."""
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
        print(f"Executing: {pipeline_name} (ID: {pipeline_id}, Version: {version_id})")

    # Use v2 predict API for synchronous execution
    predict_url = f"{base_url}/api/v2/elitea_core/predict/prompt_lib/{project_id}/{version_id}"
    payload = {
        "chat_history": [],
        "user_input": input_message or "execute"
    }

    if verbose:
        print(f"  POST {predict_url}")
        print(f"  Payload: {json.dumps(payload)}")

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
        print(f"  Response: {response.status_code}")

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

    # Check various result structures for test_passed
    if isinstance(result_data, dict):
        # Direct test_passed field
        if "test_passed" in result_data:
            test_passed = result_data.get("test_passed")
        # Nested in result field
        elif "result" in result_data:
            nested = result_data.get("result", {})
            if isinstance(nested, dict) and "test_passed" in nested:
                test_passed = nested.get("test_passed")
        # Check in chat_history (pipeline response format)
        elif "chat_history" in result_data:
            chat_history = result_data.get("chat_history", [])
            for msg in chat_history:
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.startswith("{"):
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict):
                                if "test_passed" in parsed:
                                    test_passed = parsed.get("test_passed")
                                    output = parsed
                                    break
                                elif "result" in parsed:
                                    nested = parsed.get("result", {})
                                    if isinstance(nested, dict) and "test_passed" in nested:
                                        test_passed = nested.get("test_passed")
                                        output = parsed
                                        break
                        except (json.JSONDecodeError, TypeError):
                            pass
        # Check in response/output field
        elif "response" in result_data:
            resp = result_data.get("response")
            if isinstance(resp, dict) and "test_passed" in resp:
                test_passed = resp.get("test_passed")
            elif isinstance(resp, str):
                try:
                    parsed = json.loads(resp)
                    if isinstance(parsed, dict) and "test_passed" in parsed:
                        test_passed = parsed.get("test_passed")
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
        output=output
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
