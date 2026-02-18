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
import yaml
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Any

import requests

# Force UTF-8 encoding for Windows compatibility
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # Python < 3.7
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Import shared pattern matching utilities
from pattern_matcher import matches_pattern

# Import shared utilities
from utils_common import load_from_env, load_token_from_env, load_base_url_from_env, load_project_id_from_env
from logger import TestLogger


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


def get_auth_headers(include_content_type: bool = False) -> dict:
    """Get authentication headers from environment."""
    token = load_from_env("AUTH_TOKEN") or load_from_env("ELITEA_TOKEN") or load_from_env("API_KEY")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def load_nodes_with_continue_on_error(pipeline_name: str, logger: Optional[TestLogger] = None) -> set:
    """
    Load the test YAML definition and extract node IDs that have continue_on_error: true.
    
    Args:
        pipeline_name: Name of the pipeline to find the YAML file for
        logger: Optional logger for debugging
        
    Returns:
        Set of node IDs that have continue_on_error enabled
    """
    import yaml
    
    nodes_with_flag = set()
    
    try:
        # Search for test YAML files in common locations
        test_dirs = [
            Path("suites"),
            Path("."),
            Path(".."),
            Path("../../suites"),
        ]
        
        for base_dir in test_dirs:
            if not base_dir.exists():
                continue
                
            # Search recursively for test YAML files
            for yaml_file in base_dir.rglob("*.yaml"):
                try:
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        
                    if not data or not isinstance(data, dict):
                        continue
                    
                    # Check if this is the right test file
                    if data.get("name") != pipeline_name:
                        continue
                    
                    # Found the right file - extract nodes with continue_on_error
                    nodes = data.get("nodes", [])
                    for node in nodes:
                        if isinstance(node, dict) and node.get("continue_on_error") is True:
                            node_id = node.get("id")
                            if node_id:
                                nodes_with_flag.add(node_id)
                                if logger:
                                    logger.debug(f"Found node '{node_id}' with continue_on_error: true")
                    
                    # Found and processed the file
                    break
                except Exception:
                    continue
            
            if nodes_with_flag:
                break
                
    except Exception as e:
        if logger:
            logger.debug(f"Could not load node configuration: {e}")
    
    return nodes_with_flag


def is_error_from_continue_on_error_node(error_text: str, tool_calls_dict: dict, 
                                         nodes_with_continue_on_error: set,
                                         logger: Optional[TestLogger] = None) -> bool:
    """
    Check if an error message came from a node with continue_on_error: true.
    
    This checks if the error text appears in the tool_output of a tool call
    from a node that has the continue_on_error flag enabled.
    
    Args:
        error_text: The error message text
        tool_calls_dict: Dictionary of tool calls from execution
        nodes_with_continue_on_error: Set of node IDs that have continue_on_error: true
        logger: Optional logger for debugging
        
    Returns:
        True if error came from a continue_on_error node, False otherwise
    """
    if not tool_calls_dict or not error_text or not nodes_with_continue_on_error:
        return False
    
    # Extract key parts of error message for matching
    error_key = error_text.strip()[:100]  # First 100 chars for matching
    
    for tool_call_id, tool_call in tool_calls_dict.items():
        tool_output = tool_call.get("tool_output") or tool_call.get("content", "")
        
        if isinstance(tool_output, str) and error_key in tool_output:
            # Error matches this tool's output - check if node has continue_on_error
            node_name = tool_call.get("metadata", {}).get("langgraph_node", "unknown")
            
            if node_name in nodes_with_continue_on_error:
                if logger:
                    logger.debug(f"Error from node '{node_name}' with continue_on_error: true - treating as expected")
                return True
            else:
                if logger:
                    logger.debug(f"Error from node '{node_name}' without continue_on_error - treating as failure")
                return False
    
    return False


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


def process_pipeline_result(
    result_data: Any,
    pipeline_id: int = 0,
    pipeline_name: str = "Unknown",
    version_id: Optional[int] = None,
    execution_time: float = 0.0,
    logger: Optional[TestLogger] = None,
    verbose: bool = False,
) -> PipelineResult:
    """
    Process raw pipeline output into a structured PipelineResult.
    
    This function handles output from both:
    - Remote execution: /predict API response
    - Local execution: graph.invoke() result
    
    Args:
        result_data: The raw output from pipeline execution (dict or response data)
        pipeline_id: ID of the pipeline (0 for local execution)
        pipeline_name: Name of the pipeline
        version_id: Optional version ID
        execution_time: Time taken for execution
        logger: Optional TestLogger instance for verbose logging
        verbose: Whether to enable verbose output (ignored, for compatibility)
        
    Returns:
        PipelineResult with extracted test results and metadata
    """
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
    
    # Load node configuration to identify nodes with continue_on_error: true
    nodes_with_continue_on_error = load_nodes_with_continue_on_error(pipeline_name, logger)
    if nodes_with_continue_on_error and logger:
        logger.debug(f"Loaded {len(nodes_with_continue_on_error)} nodes with continue_on_error: {nodes_with_continue_on_error}")

    # CRITICAL: Check for tool execution errors FIRST (before checking test_passed from LLM)
    # This prevents false positives where LLM says "test passed" but a tool actually failed
    if isinstance(result_data, dict) and "tool_calls_dict" in result_data:
        tool_calls = result_data.get("tool_calls_dict", {})
        if isinstance(tool_calls, dict):
            for tool_call_id, tool_call in tool_calls.items():
                if not isinstance(tool_call, dict):
                    continue
                
                # Check if this tool call failed
                finish_reason = tool_call.get("finish_reason")
                if finish_reason == "error":
                    # Tool execution failed - check if from continue_on_error node first
                    node_name = tool_call.get("metadata", {}).get("langgraph_node", "unknown")
                    
                    # Check if error is from a node with continue_on_error: true
                    if node_name in nodes_with_continue_on_error:
                        if logger:
                            logger.debug(f"Error from node '{node_name}' with continue_on_error: true - not treating as failure")
                        continue  # Skip this error, don't mark test as failed
                    
                    # Error is NOT from continue_on_error node - treat as failure
                    tool_name = tool_call.get("tool_meta", {}).get("name", "unknown_tool")
                    tool_error = tool_call.get("error", "Unknown error")
                    
                    # Format a clear error message
                    if "ValidationError" in tool_error:
                        # Extract validation error details
                        lines = tool_error.split('\n')
                        validation_msg = "Validation error"
                        for line in lines:
                            if "validation error" in line.lower():
                                validation_msg = line.strip()
                                break
                            elif "Input should be" in line or "type=" in line:
                                validation_msg = line.strip()
                                break
                        detected_error = f"Tool '{tool_name}' failed: {validation_msg}"
                    else:
                        # Generic error message
                        error_preview = tool_error[:200] + "..." if len(tool_error) > 200 else tool_error
                        detected_error = f"Tool '{tool_name}' execution failed: {error_preview}"
                    
                    test_passed = False
                    
                    if logger:
                        logger.error(f"Tool execution error detected: {detected_error}")
                        logger.debug(f"Full tool error: {tool_error}")
                    
                    # Break on first error (could collect all errors if needed)
                    break
                
                # Also check tool output content for error patterns (e.g., pyodide_sandbox errors)
                # Some tools complete successfully but return error information in their output
                tool_output = tool_call.get("tool_output") or tool_call.get("content")
                if isinstance(tool_output, str) and tool_output.strip():
                    # Try to parse as JSON to detect structured error responses
                    try:
                        parsed_output = json.loads(tool_output)
                        if isinstance(parsed_output, dict):
                            # Check for error field or execution failure status
                            if "error" in parsed_output and parsed_output["error"]:
                                tool_name = tool_call.get("tool_meta", {}).get("name", "unknown_tool")
                                error_msg = parsed_output["error"]
                                
                                # Extract meaningful error from tracebacks
                                if "Traceback" in error_msg:
                                    # Get last line of traceback (usually the actual error)
                                    lines = error_msg.strip().split('\n')
                                    error_summary = lines[-1] if lines else error_msg
                                else:
                                    error_summary = error_msg[:200] + "..." if len(error_msg) > 200 else error_msg
                                
                                detected_error = f"Tool '{tool_name}' returned error: {error_summary}"
                                test_passed = False
                                
                                if logger:
                                    logger.error(f"Tool output error detected: {detected_error}")
                                    logger.debug(f"Full error: {error_msg}")
                                
                                break
                            
                            # Check for execution failure status
                            elif parsed_output.get("status") == "Execution failed":
                                tool_name = tool_call.get("tool_meta", {}).get("name", "unknown_tool")
                                error_msg = parsed_output.get("error", "Execution failed")
                                
                                if "Traceback" in error_msg:
                                    lines = error_msg.strip().split('\n')
                                    error_summary = lines[-1] if lines else error_msg
                                else:
                                    error_summary = error_msg[:200] + "..." if len(error_msg) > 200 else error_msg
                                
                                detected_error = f"Tool '{tool_name}' execution failed: {error_summary}"
                                test_passed = False
                                
                                if logger:
                                    logger.error(f"Tool execution failure detected: {detected_error}")
                                    logger.debug(f"Full error: {error_msg}")
                                
                                break
                    except json.JSONDecodeError:
                        pass

    # Check for errors in direct result field (e.g., from local execution or chat_history parsing)
    if test_passed is None and isinstance(result_data, dict):
        if "result" in result_data:
            result_obj = result_data.get("result", {})
            if isinstance(result_obj, dict):
                # Check for error indicators in result object
                if "error" in result_obj and result_obj["error"]:
                    error_msg = result_obj["error"]
                    
                    if "Traceback" in error_msg:
                        lines = error_msg.strip().split('\n')
                        error_summary = lines[-1] if lines else error_msg
                    else:
                        error_summary = error_msg[:200] + "..." if len(error_msg) > 200 else error_msg
                    
                    detected_error = f"Execution error: {error_summary}"
                    test_passed = False
                    
                    if logger:
                        logger.error(f"Result error detected: {detected_error}")
                        logger.debug(f"Full error: {error_msg}")
                
                # Check for execution failure status in result
                elif result_obj.get("status") == "Execution failed":
                    error_msg = result_obj.get("error", "Execution failed")
                    
                    if "Traceback" in error_msg:
                        lines = error_msg.strip().split('\n')
                        error_summary = lines[-1] if lines else error_msg
                    else:
                        error_summary = error_msg[:200] + "..." if len(error_msg) > 200 else error_msg
                    
                    detected_error = f"Execution failed: {error_summary}"
                    test_passed = False
                    
                    if logger:
                        logger.error(f"Execution failure in result: {detected_error}")
                        logger.debug(f"Full error: {error_msg}")
    
    # Check for errors in chat_history messages (before checking test_passed)
    if test_passed is None and isinstance(result_data, dict) and "chat_history" in result_data:
        chat_history = result_data.get("chat_history", [])
        tool_calls_dict = result_data.get("tool_calls_dict", {})
        
        for msg in chat_history:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                # Try to parse JSON content for error patterns
                if isinstance(content, str) and content.strip().startswith("{"):
                    try:
                        parsed_content = json.loads(content)
                        if isinstance(parsed_content, dict):
                            # Check for error field
                            if "error" in parsed_content and parsed_content["error"]:
                                error_msg = parsed_content["error"]
                                
                                # Check if this error came from a continue_on_error node
                                if is_error_from_continue_on_error_node(error_msg, tool_calls_dict, nodes_with_continue_on_error, logger):
                                    if logger:
                                        logger.debug(f"Error from continue_on_error node - not treating as failure")
                                    continue
                                
                                if "Traceback" in error_msg:
                                    lines = error_msg.strip().split('\n')
                                    error_summary = lines[-1] if lines else error_msg
                                else:
                                    error_summary = error_msg[:200] + "..." if len(error_msg) > 200 else error_msg
                                
                                detected_error = f"Chat history error: {error_summary}"
                                test_passed = False
                                
                                if logger:
                                    logger.error(f"Error in chat_history: {detected_error}")
                                    logger.debug(f"Full error: {error_msg}")
                                
                                break
                            
                            # Check for execution failure status
                            elif parsed_content.get("status") == "Execution failed":
                                error_msg = parsed_content.get("error", "Execution failed")
                                
                                # Check if this error came from a continue_on_error node
                                if is_error_from_continue_on_error_node(error_msg, tool_calls_dict, nodes_with_continue_on_error, logger):
                                    if logger:
                                        logger.debug(f"Execution failed from continue_on_error node - not treating as failure")
                                    continue
                                
                                if "Traceback" in error_msg:
                                    lines = error_msg.strip().split('\n')
                                    error_summary = lines[-1] if lines else error_msg
                                else:
                                    error_summary = error_msg[:200] + "..." if len(error_msg) > 200 else error_msg
                                
                                detected_error = f"Execution failed in chat: {error_summary}"
                                test_passed = False
                                
                                if logger:
                                    logger.error(f"Execution failure in chat_history: {detected_error}")
                                    logger.debug(f"Full error: {error_msg}")
                                
                                break
                    except json.JSONDecodeError:
                        pass

    # Check various result structures for test_passed (only if not already set by error checks)
    if test_passed is None and isinstance(result_data, dict):
        # Direct test_passed field
        if "test_passed" in result_data:
            test_passed = result_data.get("test_passed")
        # Check for test_results at top level (validation nodes often use this)
        elif "test_results" in result_data:
            test_results = result_data.get("test_results", {})
            if isinstance(test_results, dict) and "test_passed" in test_results:
                test_passed = test_results.get("test_passed")
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
        
        # Check tool_calls_dict for code node outputs (pyodide_sandbox)
        # This handles cases where test_results is in a code node's output
        if test_passed is None and "tool_calls_dict" in result_data:
            tool_calls = result_data.get("tool_calls_dict", {})
            if isinstance(tool_calls, dict):
                # Look for code nodes with test_results in output
                for tool_call_id, tool_call in tool_calls.items():
                    if not isinstance(tool_call, dict):
                        continue
                    
                    tool_name = tool_call.get("tool_meta", {}).get("name", "")
                    if tool_name != "pyodide_sandbox":
                        continue
                    
                    # Parse tool_output for test_results
                    tool_output = tool_call.get("tool_output", "")
                    if isinstance(tool_output, str) and tool_output.strip().startswith("{"):
                        try:
                            parsed = json.loads(tool_output)
                            if isinstance(parsed, dict):
                                # Check result.test_results.test_passed
                                if "result" in parsed:
                                    result_obj = parsed.get("result", {})
                                    if isinstance(result_obj, dict) and "test_results" in result_obj:
                                        tr = result_obj.get("test_results", {})
                                        if isinstance(tr, dict) and "test_passed" in tr:
                                            test_passed = tr.get("test_passed")
                                            if isinstance(output, dict):
                                                output["result"] = result_obj
                                            else:
                                                output = result_obj
                                            break
                        except json.JSONDecodeError:
                            pass
        
        # Check in chat_history (pipeline response format)
        if test_passed is None and "chat_history" in result_data:
            chat_history = result_data.get("chat_history", [])
            for msg in chat_history:
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    # Check for tool call error in content that indicates failure
                    if isinstance(content, str) and ("Error executing code: [Errno 7]" in content or "[Errno 7] Argument list too long" in content):
                         test_passed = False
                         detected_error = "Content too large: The data payload exceeded system limits. Consider reducing the amount of data being processed."
                         output = {"error": detected_error, "raw_content": content}
                         break

                    # Strip markdown code fences if present
                    json_content = content
                    if isinstance(content, str):
                        # Remove markdown code fences (```json ... ``` or ``` ... ```)
                        stripped = content.strip()
                        if stripped.startswith("```"):
                            lines = stripped.split("\n")
                            if lines[0].startswith("```"):
                                lines = lines[1:]  # Remove first line
                            if lines and lines[-1].strip() == "```":
                                lines = lines[:-1]  # Remove last line
                            json_content = "\n".join(lines).strip()

                    if isinstance(json_content, str) and json_content.startswith("{"):
                        try:
                            parsed = json.loads(json_content)
                            if isinstance(parsed, dict):
                                if "test_passed" in parsed:
                                    test_passed = parsed.get("test_passed")
                                    if isinstance(output, dict):
                                        output["result"] = parsed
                                    else:
                                        output = parsed
                                    break
                                # Check for test_results at top level (common in validation nodes)
                                elif "test_results" in parsed:
                                    test_results = parsed.get("test_results", {})
                                    if isinstance(test_results, dict) and "test_passed" in test_results:
                                        test_passed = test_results.get("test_passed")
                                        if isinstance(output, dict):
                                            output["result"] = test_results
                                        else:
                                            output = test_results
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
                    key=lambda x: x.get("timestamp_finish") or "" if isinstance(x, dict) else "",
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

    if logger:
        logger.debug(f"Processed result - test_passed: {test_passed}")
        if test_passed is False:
            # Log error details when test fails
            if detected_error:
                logger.error(f"Test failed: {detected_error}")
            elif isinstance(output, dict):
                # Try to extract error from output
                error_msg = output.get("error") or output.get("error_message")
                if error_msg:
                    logger.error(f"Test failed: {error_msg}")
                elif "result" in output:
                    result = output.get("result")
                    if isinstance(result, dict):
                        error_msg = result.get("error") or result.get("error_message") or result.get("message")
                        if error_msg:
                            logger.error(f"Test failed: {error_msg}")
                        else:
                            logger.error(f"Test failed: {result}")
                    else:
                        logger.error(f"Test failed with result: {result}")
                else:
                    logger.error(f"Test failed with output: {output}")
            else:
                logger.error(f"Test failed with output: {output}")

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


def execute_pipeline(
    base_url: str,
    project_id: int,
    pipeline: dict,
    input_message: str = "",
    timeout: int = 120,
    logger: Optional[TestLogger] = None,
) -> PipelineResult:
    """Execute a pipeline using the v2 predict API (synchronous).
    
    Args:
        logger: Optional TestLogger instance for logging
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

    if logger:
        logger.debug(f"Executing: {pipeline_name} (ID: {pipeline_id}, Version: {version_id})")

    # Use v2 predict API for synchronous execution
    predict_url = f"{base_url}/api/v2/elitea_core/predict/prompt_lib/{project_id}/{version_id}"
    payload = {
        "chat_history": [],
        "user_input": input_message or "execute"
    }

    if logger:
        logger.debug(f"POST {predict_url}")
        logger.debug(f"Payload: {json.dumps(payload)}")

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

    if logger:
        logger.debug(f"Response: {response.status_code}")

    # Handle HTTP errors
    if response.status_code not in (200, 201):
        error_text = response.text if response.text else "No response body"
        
        # Log the HTTP error with details
        if logger:
            logger.http_error(
                response.status_code,
                error_text,
                context=f"POST {base_url}/api/v2/elitea_core/predict/prompt_lib/{pipeline_id}/{version_id}"
            )
        
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

    # Process the result using shared function
    return process_pipeline_result(
        result_data=result_data,
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        version_id=version_id,
        execution_time=execution_time,
        logger=logger,
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

    # Create logger instance
    logger = TestLogger(verbose=args.verbose, quiet=args.json) if args.verbose else None

    # Execute pipeline
    result = execute_pipeline(
        base_url=base_url,
        project_id=project_id,
        pipeline=pipeline,
        input_message=args.input,
        timeout=args.timeout,
        logger=logger
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
