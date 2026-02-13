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
import warnings
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

# Import base callback classes for local metadata collection
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from uuid import UUID
from datetime import datetime, timezone
import traceback

# Note: Do NOT use logging.basicConfig() here as it prevents dynamic log level changes
# Logging configuration is handled by configure_file_logging() at runtime
# basicConfig() is a one-time operation that cannot be overridden
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Default level for utils_local


class MetadataCollectingCallback(BaseCallbackHandler):
    """
    Callback that collects execution metadata for result building.
    
    Collects backend-compatible data (thinking_steps, tool_calls, token counts)
    for local test execution to build results matching production backend format.
    
    Usage:
        callback = MetadataCollectingCallback()
        config = {"callbacks": [callback]}
        result = agent.invoke(input, config=config)
        
        # Access collected metadata
        summary = callback.get_summary()
        thinking_steps = callback.thinking_steps
        tool_calls = callback.tool_calls
        tokens_in = callback.tokens_in
    """
    
    def __init__(self):
        """
        Initialize metadata collecting callback.
        """
        super().__init__()
        
        # Attributes required for compatibility (referenced in callback methods)
        self.current_model: str = 'gpt-4o'  # Default model name
        self.step_counter: int = 0  # Step counter for execution tracking
        
        # Data collection (backend-compatible format)
        self.thinking_steps: List[Dict[str, Any]] = []
        self.tool_calls: Dict[str, Dict[str, Any]] = {}  # tool_run_id -> payload
        self.tokens_in: int = 0
        self.tokens_out: int = 0
        self.pending_llm_requests: Dict[UUID, Dict[str, Any]] = {}
        self.llm_start_timestamp: Optional[str] = None
    
    def _extract_token_usage(self, response: LLMResult) -> Optional[Dict[str, int]]:
        """
        Extract token usage from LLM response.
        
        Tries multiple sources:
        1. response.llm_output.token_usage (OpenAI, most providers)
        2. response.generations[].message.response_metadata.token_usage (Anthropic)
        
        Returns:
            Dict with prompt_tokens and completion_tokens, or None if not found
        """
        try:
            # Source 1: llm_output.token_usage (OpenAI format)
            if hasattr(response, 'llm_output') and response.llm_output:
                token_usage = response.llm_output.get('token_usage', {})
                if token_usage:
                    return {
                        'prompt_tokens': token_usage.get('prompt_tokens', 0),
                        'completion_tokens': token_usage.get('completion_tokens', 0),
                    }
            
            # Source 2: message.response_metadata.token_usage (Anthropic format)
            for generation in response.generations:
                for gen in generation:
                    if hasattr(gen, 'message') and hasattr(gen.message, 'response_metadata'):
                        metadata = gen.message.response_metadata
                        if 'token_usage' in metadata:
                            return {
                                'prompt_tokens': metadata['token_usage'].get('input_tokens', 0),
                                'completion_tokens': metadata['token_usage'].get('output_tokens', 0),
                            }
            
            return None
        except Exception as e:
            logger.warning(f"Failed to extract token usage: {e}")
            return None
    
    # Override LLM callbacks to collect metadata
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts - collect metadata and display."""
        # Track for token counting
        self.pending_llm_requests[run_id] = {
            "timestamp_start": datetime.now(tz=timezone.utc).isoformat(),
            "model": metadata.get("ls_model_name", self.current_model) if metadata else self.current_model,
        }
    
    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chat model starts - collect metadata and display."""
        # Track for token counting
        self.pending_llm_requests[run_id] = {
            "timestamp_start": datetime.now(tz=timezone.utc).isoformat(),
            "model": metadata.get("ls_model_name", self.current_model) if metadata else self.current_model,
        }
    
    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM finishes - collect thinking steps, tokens, and display."""
        # Extract token usage from API response
        token_usage = self._extract_token_usage(response)
        if token_usage:
            self.tokens_in += token_usage.get("prompt_tokens", 0)
            self.tokens_out += token_usage.get("completion_tokens", 0)
        
        # Get pending request data
        pending = self.pending_llm_requests.pop(run_id, {})
        llm_timestamp_start = pending.get("timestamp_start")
        
        # Track first LLM call timestamp
        if not self.llm_start_timestamp:
            self.llm_start_timestamp = llm_timestamp_start
        
        # Collect thinking steps from generations
        for generation in response.generations:
            for gen_item in generation:
                step = gen_item.model_dump()
                step['timestamp_start'] = llm_timestamp_start
                step['timestamp_finish'] = datetime.now(tz=timezone.utc).isoformat()
                step['tool_run_id'] = str(run_id)
                
                # Extract thinking from message content
                # Handles Claude extended thinking and GPT-o1/o3 reasoning
                msg_content = step.get('message', {}).get('content')
                if isinstance(msg_content, list) and not step.get('thinking'):
                    thinking_items = []
                    for item in msg_content:
                        if not isinstance(item, dict):
                            continue
                        item_type = item.get('type')
                        # Anthropic extended thinking
                        if item_type == 'thinking' and item.get('thinking'):
                            thinking_items.append(item.get('thinking'))
                        # OpenAI reasoning models - format 1: summary array
                        elif item_type == 'reasoning' and item.get('summary'):
                            for summary_item in item.get('summary', []):
                                if isinstance(summary_item, dict) and summary_item.get('text'):
                                    thinking_items.append(summary_item.get('text'))
                        # OpenAI reasoning models - format 2: direct reasoning field
                        elif item_type == 'reasoning' and item.get('reasoning'):
                            thinking_items.append(item.get('reasoning'))
                    
                    if thinking_items:
                        step['thinking'] = '\n'.join(thinking_items)
                
                self.thinking_steps.append(step)
    
    # Override tool callbacks to collect metadata
    
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool starts - collect metadata and display."""
        tool_name = serialized.get("name", "Unknown Tool")
        tool_run_id = str(run_id)
        
        # Build tool_meta with nested metadata structure (matches backend)
        tool_meta = {
            "name": tool_name,
            "description": serialized.get("description", ""),
        }
        
        # Extract toolkit metadata and create nested metadata object
        toolkit_metadata = {}
        
        # Source 1: metadata parameter (LangGraph checkpoint metadata)
        if metadata and isinstance(metadata, dict):
            if "toolkit_name" in metadata:
                toolkit_metadata["toolkit_name"] = metadata["toolkit_name"]
            if "toolkit_type" in metadata:
                toolkit_metadata["toolkit_type"] = metadata["toolkit_type"]
        
        # Source 2: serialized metadata (fallback)
        if not toolkit_metadata and "metadata" in serialized:
            serialized_meta = serialized["metadata"]
            if isinstance(serialized_meta, dict):
                if "toolkit_name" in serialized_meta:
                    toolkit_metadata["toolkit_name"] = serialized_meta["toolkit_name"]
                if "toolkit_type" in serialized_meta:
                    toolkit_metadata["toolkit_type"] = serialized_meta["toolkit_type"]
        
        # Add nested metadata object to tool_meta (only if we found toolkit info)
        if toolkit_metadata:
            tool_meta["metadata"] = toolkit_metadata
        
        # Store tool call metadata (matching backend ToolCallPayload structure)
        self.tool_calls[tool_run_id] = {
            'tool_name': tool_name,
            'tool_run_id': tool_run_id,
            'run_id': tool_run_id,  # Backend compatibility (duplicate of tool_run_id)
            'tool_meta': tool_meta,  # Full tool definition with description and metadata
            'tool_inputs': inputs or input_str,
            'timestamp_start': datetime.now(tz=timezone.utc).isoformat(),
            'metadata': metadata or {},
        }
    
    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool finishes - collect metadata and display."""
        tool_run_id = str(run_id)
        
        # Convert output to string (matches backend logic)
        tool_output = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        
        # Update tool call metadata
        if tool_run_id in self.tool_calls:
            self.tool_calls[tool_run_id].update({
                'tool_output': tool_output,
                'content': tool_output,  # Backend compatibility (alias for tool_output)
                'finish_reason': 'stop',
                'timestamp_finish': datetime.now(tz=timezone.utc).isoformat(),
            })
        else:
            # Tool start was missed - create entry (defensive)
            tool_name = kwargs.get('name', 'Unknown')
            # Try to get from parent's tool_runs if available
            if hasattr(self, 'tool_runs') and tool_run_id in self.tool_runs:
                tool_name = self.tool_runs[tool_run_id].get('name', tool_name)
            
            self.tool_calls[tool_run_id] = {
                'tool_name': tool_name,
                'tool_run_id': tool_run_id,
                'run_id': tool_run_id,  # Backend compatibility
                'tool_output': tool_output,
                'content': tool_output,  # Backend compatibility
                'finish_reason': 'stop',
                'timestamp_finish': datetime.now(tz=timezone.utc).isoformat(),
            }
    
    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool errors - collect metadata and display."""
        tool_run_id = str(run_id)
        error_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        
        # Update tool call metadata with error
        if tool_run_id in self.tool_calls:
            self.tool_calls[tool_run_id].update({
                'error': error_str,
                'content': None,  # Backend sets to None on error
                'tool_output': None,  # Backend sets to None on error
                'finish_reason': 'error',
                'timestamp_finish': datetime.now(tz=timezone.utc).isoformat(),
            })
        else:
            # Tool start was missed - create entry with error (defensive)
            tool_name = kwargs.get('name', 'Unknown')
            if hasattr(self, 'tool_runs') and tool_run_id in self.tool_runs:
                tool_name = self.tool_runs[tool_run_id].get('name', tool_name)
            
            self.tool_calls[tool_run_id] = {
                'tool_name': tool_name,
                'tool_run_id': tool_run_id,
                'run_id': tool_run_id,  # Backend compatibility
                'error': error_str,
                'content': None,  # Backend sets to None on error
                'tool_output': None,  # Backend sets to None on error
                'finish_reason': 'error',
                'timestamp_finish': datetime.now(tz=timezone.utc).isoformat(),
            }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get execution summary with all collected metadata.
        
        Returns:
            Dict containing thinking_steps, tool_calls, token counts, etc.
            Ready to use with build_success_result pattern.
        """
        return {
            'thinking_steps': self.thinking_steps,
            'tool_calls': self.tool_calls,
            'tokens_in': self.tokens_in,
            'tokens_out': self.tokens_out,
            'llm_start_timestamp': self.llm_start_timestamp,
            'step_counter': self.step_counter,
        }


def configure_alita_sdk_logging(log_level: str = 'error'):
    """
    Configure alita_sdk package logging level.
    
    By default, suppress alita_sdk.* loggers to keep test output clean.
    
    Why this is needed:
    - Local test execution instantiates full toolkit stack locally
    - This triggers alita_sdk initialization logs:
      * alita_sdk.configurations
      * alita_sdk.tools
      * alita_sdk.runtime.langchain.langraph_agent
      * etc.
    - Remote mode doesn't show these because platform manages toolkit instantiation
    - For test-only runs, these logs clutter the output
    - Use --local=debug/info/warning to see more logs when debugging
    
    Args:
        log_level: Log level for alita_sdk loggers
                   - 'error': Suppress most SDK logs (default)
                   - 'warning': Show warnings and errors
                   - 'info': Show info messages
                   - 'debug': Show debug messages
    """
    # Map string level names to logging constants
    level_map = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
    }
    
    log_level_const = level_map.get(log_level.lower(), logging.ERROR)
    
    alita_loggers = [
        'alita_sdk',
        'alita_sdk.runtime',
        'alita_sdk.runtime.langchain',
        'alita_sdk.tools',
        'alita_sdk.configurations',
        'alita_sdk.cli',
        'alita_sdk.community',
    ]
    
    for logger_name in alita_loggers:
        logging.getLogger(logger_name).setLevel(log_level_const)
    
    # Suppress third-party HTTP client verbose logs and SSL warnings
    # These come from external dependencies making API calls:
    # - urllib3: Low-level HTTP client (used by requests for HTTPS calls)
    # - httpx: HTTP client used by LangChain/OpenAI SDK
    # - requests: HTTP library making API calls to backend
    # Set to WARNING to hide INFO logs about successful HTTP requests
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Also suppress third-party library warnings
    import warnings
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')


def configure_file_logging(log_file: str, sdk_log_level: str = 'error', verbose: bool = False):
    """
    Configure file-based logging for detailed execution trace.
    
    Sets up a file handler that captures DEBUG-level logs from all components
    to a file (typically run.log), while keeping console output clean.
    
    This is part of the 3-stream logging architecture:
    - STDOUT (console): INFO (utils_common only) + WARNING (all) + ERROR (all) when verbose=True
                        WARNING (all) + ERROR (all) when verbose=False
    - STDERR (console): ERRORS + WARNINGS (always)
    - run.log (file): DEBUG + all levels (always)
    
    Args:
        log_file: Path to log file (e.g., 'test_results/suite/run.log')
        sdk_log_level: Log level for alita_sdk loggers ('debug', 'info', 'warning', 'error')
        verbose: If True, allow INFO logs from utils_common on console
    
    Example:
        configure_file_logging('test_results/artifact/run.log', 'debug', verbose=True)
        # Now all DEBUG logs go to file, console only shows utils_common INFO
    """
    # Create file handler for DEBUG level logs
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(log_file, mode='a')  # Append mode
    file_handler.setLevel(logging.DEBUG)
    
    # Detailed format for file logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add to root logger (captures everything)
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)  # Allow DEBUG to propagate to file
    
    # Configure third-party loggers (suppress urllib3, httpx, requests noise)
    configure_alita_sdk_logging(sdk_log_level)
    
    # Override alita_sdk loggers to DEBUG for file logging
    # This allows DEBUG logs to be emitted and captured by the file handler
    # Must happen AFTER configure_alita_sdk_logging() which would reset them
    # Note: Child loggers inherit from parent, so only need top-level packages
    alita_loggers = [
        'alita_sdk',
        'alita_sdk.runtime',
        'alita_sdk.runtime.langchain',
        'alita_sdk.tools',
        'alita_sdk.configurations',
        'alita_sdk.cli',
        'alita_sdk.community',
    ]
    for logger_name in alita_loggers:
        logging.getLogger(logger_name).setLevel(logging.DEBUG)
    
    # Log logger configuration for debugging
    logger.debug(f"alita_sdk loggers set to DEBUG: {', '.join(alita_loggers)}")
    logger.debug(f"alita_sdk logger level: {logging.getLogger('alita_sdk').level} (should be {logging.DEBUG})")
    logger.debug(f"Root logger level: {root_logger.level} (should be {logging.DEBUG})")
    logger.debug(f"File handler level: {file_handler.level} (should be {logging.DEBUG})")
    
    # Prevent DEBUG logs from appearing on console
    # Set all existing console/stream handlers to INFO minimum
    console_handler_found = False
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            console_handler_found = True
            # Add same formatter as file handler for consistent output
            handler.setFormatter(formatter)
            # Console handlers should never show DEBUG
            if verbose:
                # When verbose: show INFO from utils_common/utils_local, WARNING+ from all
                handler.setLevel(logging.INFO)
                # Add filter to only show INFO from utils modules
                handler.addFilter(ConsoleInfoFilter())
            else:
                # When not verbose: only WARNING and ERROR
                handler.setLevel(logging.WARNING)
    
    # If no console handler exists, create one (shouldn't happen with basicConfig, but be safe)
    if not console_handler_found:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)  # Use same format as file handler
        if verbose:
            console_handler.setLevel(logging.INFO)
            console_handler.addFilter(ConsoleInfoFilter())
        else:
            console_handler.setLevel(logging.WARNING)
        root_logger.addHandler(console_handler)
    
    # Log the configuration
    logger.debug(f"File logging configured: {log_file} (SDK level: {sdk_log_level})")
    
    # Suppress paramiko/cryptography deprecation warnings (TripleDES cipher deprecation)
    warnings.filterwarnings('ignore', message='TripleDES has been moved to')
    try:
        from cryptography.utils import CryptographyDeprecationWarning
        warnings.filterwarnings('ignore', category=CryptographyDeprecationWarning)
    except ImportError:
        pass
    warnings.filterwarnings('ignore', module='paramiko', category=DeprecationWarning)
    
    # Suppress pydantic UserWarnings about field shadowing
    warnings.filterwarnings('ignore', module='pydantic', category=UserWarning)


class ConsoleInfoFilter(logging.Filter):
    """
    Filter that allows:
    - INFO level ONLY from utils_common and utils_local modules
    - WARNING and ERROR from all modules
    
    This prevents console clutter while showing useful progress info.
    """
    def filter(self, record):
        # Always allow WARNING and ERROR
        if record.levelno >= logging.WARNING:
            return True
        
        # For INFO level, only allow utils_common and utils_local
        if record.levelno == logging.INFO:
            return record.name.startswith('utils_local')
        
        # Block DEBUG and other levels
        return False


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
        sdk_log_level: str = 'error',
    ):
        """
        Initialize the test runner.

        Args:
            tools: Pre-created toolkit tools (from LocalSetupStrategy)
            env_vars: Environment variables for substitution
            verbose: Enable verbose logging for test framework (not SDK)
            alita_client: Optional pre-created AlitaClient
            llm: Optional pre-created LLM instance
            sdk_log_level: Log level for alita_sdk loggers
                           (debug, info, warning, error - default: error)
        """
        self._tools = tools or []
        self.env_vars = env_vars or {}
        self.verbose = verbose
        self.alita_client = alita_client
        self.llm = llm

        # Note: SDK logging is configured ONCE in run_suite_local() via configure_file_logging()
        # Do NOT call configure_alita_sdk_logging() here, as it would reset logger levels
        # that were already configured for file-level DEBUG capture.
        # The --local flag's log level is already applied upstream.
        
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

    def _build_result_from_callbacks(
        self,
        graph_result: Dict[str, Any],
        user_input: str,
        callback: MetadataCollectingCallback
    ) -> Dict[str, Any]:
        """
        Build result structure using callback data (replicates backend's build_success_result).
        
        This mirrors the production backend's response building:
        - Uses callback.thinking_steps for LLM responses
        - Uses callback.tool_calls for tool execution metadata
        - Uses callback tokens for accurate usage tracking
        - Preserves test_results from graph state
        
        Args:
            graph_result: Raw result from graph.invoke()
            user_input: The user input message
            callback: MetadataCollectingCallback with collected execution data
            
        Returns:
            Dict in remote API format matching build_success_result
        """
        # Build chat_history
        chat_history = [
            {'role': 'user', 'content': user_input}
        ]
        
        # Extract response content from graph result
        response_content = self._extract_response_content(graph_result, response_format='output')
        output_message = self._build_output_message(response_content)
        chat_history.append(output_message)
        
        # Build result structure matching build_success_result from backend
        result_data = {
            'chat_history': chat_history,
            'error': None,
            'thinking_steps': callback.thinking_steps,  # From callback
            'tool_calls': [  # Filtered from callback
                step for step in callback.thinking_steps
                if step.get('generation_info', {}).get('finish_reason') == 'tool_calls'
            ],
            'tool_calls_dict': callback.tool_calls,  # From callback
            'chat_history_tokens_input': callback.tokens_in,  # From callback
            'llm_response_tokens_output': callback.tokens_out,  # From callback
        }
        
        return result_data

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

        # Visual delimiter before test
        logger.info("")
        logger.info("-" * 80)
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

        if dry_run:
            print("\n" + "="*60)
            print("TRANSFORMED YAML:")
            print("="*60)
            print(yaml_schema)
            print("="*60 + "\n")

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
            
            # Create callback for metadata collection
            callback = MetadataCollectingCallback()
            
            # Add callback to config
            config['callbacks'] = [callback]
            
            result = graph.invoke(initial_state, config=config)

            execution_time = time.time() - start_time

            # Build result using callback metadata (replicates backend's build_success_result)
            # This provides production-equivalent metadata: thinking_steps, tool_calls, tokens
            result_data = self._build_result_from_callbacks(result, input_message or 'execute', callback)

            if self.verbose:
                print("\n" + "="*60)
                print("LOCAL PREDICT RESULT:")
                print("="*60)
                print(json.dumps(result_data, indent=2, default=str))
                print("="*60 + "\n")

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
