#!/usr/bin/env python3
"""
Local Pipeline Test Runner

Runs pipeline test cases locally without backend dependency.
Replicates all transformations from the seed_pipelines stage.
Uses AlitaClient for LLM access (same as run_streamlit.py).

This module provides:
- IsolatedPipelineTestRunner: Executes pipeline tests locally
- create_alita_client(): Creates AlitaClient from environment
- find_tests_in_suite(): Finds test files matching patterns

Note: Toolkit tools are created by LocalSetupStrategy, not this module.

Environment variables (from .env):
    DEPLOYMENT_URL      Alita deployment URL
    API_KEY             Alita API key
    PROJECT_ID          Alita project ID
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

import yaml

# Add parent directories to path for imports
SCRIPT_DIR = Path(__file__).parent
TEST_PIPELINES_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = TEST_PIPELINES_DIR.parent.parent.parent

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

# Reuse functions from seed_pipelines.py
from seed_pipelines import (
    parse_pipeline_yaml,
    get_yaml_files,
)

# Reuse shared utilities from utils_common.py
from utils_common import (
    load_token_from_env,
    load_base_url_from_env,
    load_project_id_from_env,
)

# Reuse process_pipeline_result for consistent result processing
from run_pipeline import process_pipeline_result, PipelineResult

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



def create_alita_client():
    """
    Create AlitaClient from environment variables.

    Same pattern as run_streamlit.py uses.
    Loads from .env file in project root.
    """
    from alita_sdk.runtime.clients.client import AlitaClient

    base_url = load_base_url_from_env()
    auth_token = load_token_from_env()
    project_id = load_project_id_from_env()

    if not base_url:
        raise ValueError("DEPLOYMENT_URL not set in .env")
    if not auth_token:
        raise ValueError("API_KEY not set in .env")
    if not project_id:
        raise ValueError("PROJECT_ID not set in .env")

    logger.info(f"Creating AlitaClient for {base_url} (project: {project_id})")

    return AlitaClient(
        base_url=base_url,
        project_id=project_id,
        auth_token=auth_token,
    )


class IsolatedPipelineTestRunner:
    """
    Runs pipeline YAML tests without backend dependency.

    Uses AlitaClient for LLM access (same as streamlit).
    Replicates transformations from seed_pipelines.py.
    
    Tools must be pre-created by LocalSetupStrategy and passed to __init__.
    """

    def __init__(
        self,
        tools: Optional[List[Any]] = None,
        env_vars: Optional[Dict[str, Any]] = None,
        verbose: bool = False,
        alita_client = None,
        llm = None,
    ):
        """
        Initialize the test runner.

        Args:
            tools: Pre-created toolkit tools (from LocalSetupStrategy)
            env_vars: Environment variables for substitution
            verbose: Enable verbose logging
            alita_client: Optional pre-created AlitaClient
            llm: Optional pre-created LLM instance
        """
        self._tools = tools or []
        self.env_vars = env_vars or {}
        self.verbose = verbose
        self.alita_client = alita_client
        self.llm = llm  # Use provided LLM or create on demand


        if verbose:
            logger.setLevel(logging.DEBUG)

    def _ensure_client(self):
        """Ensure AlitaClient is initialized."""
        if self.alita_client is None:
            self.alita_client = create_alita_client()
        return self.alita_client

    def _get_llm(self, model: str = 'gpt-4o-2024-11-20', temperature: float = 0.0, max_tokens: int = 4096):
        """
        Get LLM from AlitaClient or return pre-created instance.

        If LLM was passed during initialization, returns that.
        Otherwise, creates one using AlitaClient.
        Same pattern as streamlit.py and client.application().
        """
        if self.llm is not None:
            return self.llm

        client = self._ensure_client()

        self.llm = client.get_llm(
            model_name=model,
            model_config={
                'temperature': temperature,
                'max_tokens': max_tokens,
            }
        )
        logger.info(f"Created LLM: {model}")
        return self.llm

    def _extract_response_content(self, response: Dict[str, Any], response_format: str = 'output') -> str:
        """
        Extract and normalize content from agent response.
        
        Mirrors backend's extract_response_content function.

        Args:
            response: The raw response from agent invocation
            response_format: Either 'messages' (for predict_agent) or 'output' (for application agent)

        Returns:
            Normalized string content
        """
        if response_format == 'messages':
            # Predict agent format: {"messages": [...]}
            messages = response.get("messages", [])
            if isinstance(messages, list) and len(messages) > 0:
                last_message = messages[-1]
                # Handle both dict and message object
                if hasattr(last_message, 'content'):
                    content = last_message.content
                elif isinstance(last_message, dict):
                    content = last_message.get('content', '')
                else:
                    content = str(last_message)
            else:
                content = str(response)
        else:
            # Application agent format: {"output": ...}
            content = response.get("output", "")

        return content

    def _build_output_message(self, content: str) -> Dict[str, Any]:
        """
        Build a standardized output message dict.
        
        Mirrors backend's build_output_message function.

        Args:
            content: The normalized response content

        Returns:
            Dict with content and role='assistant'
        """
        return {
            'content': content,
            'role': 'assistant',
            'type': 'ai',
            'additional_kwargs': {},
            'response_metadata': {},
            'id': None,
            'name': None,
            'tool_calls': [],
            'invalid_tool_calls': [],
            'usage_metadata': None
        }

    def _transform_to_remote_format(self, local_result: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """
        Transform local graph.invoke() result to match remote /predict API format.
        
        This enables process_pipeline_result to work consistently across local and remote modes.
        
        Args:
            local_result: Raw result from graph.invoke()
            user_input: The user input message
            
        Returns:
            Dict in remote API format with chat_history, result, tool_calls_dict
        """
        # Build chat_history in remote format
        chat_history = [
            {'role': 'user', 'content': user_input}
        ]
        
        # Extract response content using backend logic
        response_content = self._extract_response_content(local_result, response_format='output')
        
        # Add assistant message to chat history
        output_message = self._build_output_message(response_content)
        chat_history.append(output_message)
        
        # Extract test results from state
        # Check common locations where test results might be stored
        result_field = None
        
        # Priority 1: test_results field (most specific)
        if 'test_results' in local_result:
            test_results = local_result['test_results']
            # Parse if it's a JSON string
            if isinstance(test_results, str) and test_results.strip().startswith('{'):
                try:
                    result_field = json.loads(test_results)
                except json.JSONDecodeError:
                    result_field = {'raw_output': test_results}
            else:
                result_field = test_results
        
        # Priority 2: output field (fallback)
        if result_field is None and 'output' in local_result:
            output = local_result['output']
            # Parse if it's a JSON string
            if isinstance(output, str) and output.strip().startswith('{'):
                try:
                    result_field = json.loads(output)
                except json.JSONDecodeError:
                    result_field = {'raw_output': output}
            elif isinstance(output, dict):
                result_field = output
        
        # Build remote-like structure
        remote_format = {
            'chat_history': chat_history,
            'error': None,
            'tool_calls_dict': {},  # Local doesn't have detailed tool call tracking
            'tool_calls': [],
            'thinking_steps': [],
        }
        
        # Add result field if available (should be a dict now, not a string)
        if result_field is not None:
            remote_format['result'] = result_field
        
        return remote_format

    def run_test(
        self,
        test_yaml_path: str,
        input_message: str = '',
        timeout: int = 120,
        dry_run: bool = False,
    ) -> PipelineResult:
        """
        Execute a pipeline test case locally.

        Args:
            test_yaml_path: Path to the test YAML file
            input_message: Optional input message for the pipeline
            timeout: Execution timeout in seconds
            dry_run: If True, only show transformed YAML without execution

        Returns:
            PipelineResult with execution details
        """
        from alita_sdk.runtime.langchain.langraph_agent import create_graph
        from langgraph.checkpoint.memory import MemorySaver

        path = Path(test_yaml_path)
        if not path.exists():
            return PipelineResult(
                success=False,
                pipeline_id=0,
                pipeline_name=path.stem,
                error=f"Test file not found: {path}"
            )

        logger.info(f"Loading test: {path}")

        # Transform YAML (reuse seed_pipelines.py logic)
        try:
            transformed = parse_pipeline_yaml(path, env_substitutions=self.env_vars)
            yaml_schema = transformed['yaml_content']
        except Exception as e:
            return PipelineResult(
                success=False,
                pipeline_id=0,
                pipeline_name=path.stem,
                error=f"Failed to transform YAML: {e}"
            )

        logger.info(f"Test: {transformed['name']}")
        logger.debug(f"Description: {transformed['description']}")

        if self.verbose or dry_run:
            print("\n" + "="*60)
            print("TRANSFORMED YAML:")
            print("="*60)
            print(yaml_schema)
            print("="*60 + "\n")

        if dry_run:
            return PipelineResult(
                success=True,
                pipeline_id=0,
                pipeline_name=path.stem,
                output={"transformed_yaml": yaml_schema},
            )

        # Check for pre-created tools
        if not self._tools:
            return PipelineResult(
                success=False,
                pipeline_id=0,
                pipeline_name=path.stem,
                error="No toolkit tools provided. Tools must be created by LocalSetupStrategy."
            )
        logger.info(f"Using {len(self._tools)} toolkit tools")

        # Extract model from YAML if specified in nodes
        model_name = 'gpt-4o-2024-11-20'  # default
        # try:
        #     yaml_dict = yaml.safe_load(yaml_schema)
        #     if isinstance(yaml_dict, dict) and 'nodes' in yaml_dict:
        #         nodes = yaml_dict['nodes']
        #         if isinstance(nodes, list):
        #             for node in nodes:
        #                 if isinstance(node, dict) and node.get('type') == 'llm':
        #                     if 'model' in node:
        #                         model_name = node['model']
        #                         logger.info(f"Found LLM model in YAML: {model_name}")
        #                         break
        # except Exception as e:
        #     logger.debug(f"Could not extract model from YAML: {e}")

        # Get LLM from AlitaClient
        try:
            llm = self._get_llm(model=model_name)
        except Exception as e:
            return PipelineResult(
                success=False,
                pipeline_id=0,
                pipeline_name=path.stem,
                error=f"Failed to create LLM: {e}"
            )

        memory = MemorySaver()

        # Create graph (same as backend does)
        try:
            start_time = time.time()

            graph = create_graph(
                client=llm,
                yaml_schema=yaml_schema,
                tools=self._tools,
                memory=memory,
                store=None,
                debug=self.verbose,
                alita_client=self.alita_client,
            )

            logger.info("Graph created successfully")
        except Exception as e:
            return PipelineResult(
                success=False,
                pipeline_id=0,
                pipeline_name=path.stem,
                error=f"Failed to create graph: {e}"
            )

        # Execute the graph
        try:
            config = {'configurable': {'thread_id': f'test-{path.stem}'}}
            # Use "execute" as default input (same as run_pipeline.py)
            initial_state = {
                'input': input_message or 'execute',
                'messages': [],
            }

            logger.info("Executing pipeline...")
            result = graph.invoke(initial_state, config=config)

            execution_time = time.time() - start_time

            if self.verbose:
                print("\n" + "="*60)
                print("EXECUTION RESULT:")
                print("="*60)
                print(json.dumps(result, indent=2, default=str))
                print("="*60 + "\n")

            # Transform local result to match remote structure (backend format)
            # This mirrors the backend's extract_response_content + build_output_message
            result_data = self._transform_to_remote_format(result, input_message or 'execute')
            
            # Use shared process_pipeline_result for consistent result extraction
            pipeline_result = process_pipeline_result(
                result_data=result_data,
                pipeline_id=0,  # Local execution has no backend ID
                pipeline_name=path.stem,
                execution_time=execution_time,
                logger=None,  # Use None - function handles it gracefully
            )

            logger.info(f"Execution completed in {execution_time:.2f}s")
            logger.info(f"Test passed: {pipeline_result.test_passed}")

            # Return PipelineResult with output set to remote-formatted result
            # This ensures consistency with remote execution format
            pipeline_result.output = result_data
            return pipeline_result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Pipeline execution failed: {e}")
            return PipelineResult(
                success=False,
                pipeline_id=0,
                pipeline_name=path.stem,
                execution_time=execution_time,
                error=f"Pipeline execution failed: {e}",
            )


def find_tests_in_suite(suite_folder: Path, pattern: str, config: Optional[dict] = None) -> List[Path]:
    """
    Find test files in a suite folder matching a pattern.

    Replicates the logic from run_test.sh and run_suite.py.

    Args:
        suite_folder: Path to the suite directory (e.g., github_toolkit)
        pattern: Pattern to match test files (e.g., 'list_branches', 'GH01', '*')
        config: Optional loaded pipeline.yaml config

    Returns:
        List of matching test file paths
    """
    # Get all yaml files using seed_pipelines.py logic
    all_yaml_files = get_yaml_files(suite_folder, config)

    if not all_yaml_files:
        logger.warning(f"No test files found in {suite_folder}")
        return []

    # Filter by pattern (same as run_suite.py --pattern)
    if pattern == '*' or pattern == '':
        return all_yaml_files

    pattern_lower = pattern.lower()
    matched = []
    for yaml_file in all_yaml_files:
        # Check if pattern matches the filename (case-insensitive partial match)
        if pattern_lower in yaml_file.name.lower():
            matched.append(yaml_file)
            continue
        # Also check against the test name inside the file
        # (This is more expensive, so we do it only if filename didn't match)
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                test_name = data.get('name', '')
                if pattern_lower in test_name.lower():
                    matched.append(yaml_file)
        except Exception:
            pass

    return matched
