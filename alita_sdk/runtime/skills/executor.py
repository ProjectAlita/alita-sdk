"""
Skill execution service with subprocess isolation.

This module provides the core execution engine for skills, supporting
both subprocess and remote execution modes with proper isolation
and result handling.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .input_builder import SkillInputBuilder
from .models import (
    ExecutionMode, SkillExecutionError, SkillExecutionResult,
    SkillMetadata, SkillOutputFile, SkillStatus, SkillType, SkillSource
)

logger = logging.getLogger(__name__)


class SkillExecutor:
    """
    Base class for skill execution with different isolation modes.
    """

    def __init__(self, alita_client=None):
        """
        Initialize skill executor.

        Args:
            alita_client: AlitaClient instance for remote execution and LLM access.
        """
        self.alita_client = alita_client
        self.input_builder = SkillInputBuilder()

    def execute_skill(
        self,
        metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        execution_id: Optional[str] = None
    ) -> SkillExecutionResult:
        """
        Execute a skill with the specified parameters.

        Args:
            metadata: Skill metadata containing execution configuration.
            task: Main task or user input for the skill.
            context: Additional context (variables or state).
            chat_history: Chat history for agent skills.
            execution_id: Optional execution ID for tracking.

        Returns:
            SkillExecutionResult with output and metadata.

        Raises:
            SkillExecutionError: If execution fails.
        """
        execution_id = execution_id or str(uuid.uuid4())

        logger.info(f"Executing skill '{metadata.name}' (mode: {metadata.execution.mode})")

        if metadata.execution.mode == ExecutionMode.SUBPROCESS:
            executor = SubprocessSkillExecutor(self.alita_client)
        elif metadata.execution.mode == ExecutionMode.REMOTE:
            executor = RemoteSkillExecutor(self.alita_client)
        else:
            raise SkillExecutionError(f"Unsupported execution mode: {metadata.execution.mode}")

        return executor._execute_skill_internal(
            metadata, task, context, chat_history, execution_id
        )


class SubprocessSkillExecutor(SkillExecutor):
    """
    Subprocess-based skill executor for local isolated execution.
    """

    def _execute_skill_internal(
        self,
        metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        execution_id: str = None
    ) -> SkillExecutionResult:
        """
        Execute skill in subprocess with isolation.
        """
        start_time = time.time()

        # Create isolated working directory
        work_dir = self._create_working_directory(metadata.name, execution_id)

        try:
            # Prepare skill input
            skill_input = self.input_builder.prepare_input(
                metadata, task, context, chat_history
            )

            # Prepare execution environment
            env = self._prepare_environment(metadata, work_dir)

            # Create input file for subprocess
            input_file = work_dir / "skill_input.json"
            with open(input_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'skill_metadata': metadata.dict(),
                    'skill_input': skill_input,
                    'execution_id': execution_id
                }, f, indent=2, default=str)

            # Execute skill in subprocess
            result = self._run_subprocess(metadata, work_dir, input_file, env)

            # Calculate duration
            duration = time.time() - start_time

            # Parse and return result
            return self._parse_execution_result(
                metadata, result, work_dir, execution_id, duration
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Skill execution failed for '{metadata.name}': {e}")

            return SkillExecutionResult(
                skill_name=metadata.name,
                skill_type=metadata.skill_type,
                status=SkillStatus.ERROR,
                execution_mode=ExecutionMode.SUBPROCESS,
                execution_id=execution_id,
                output_text=f"Skill execution failed: {str(e)}",
                output_files=[],
                duration=duration,
                working_directory=work_dir,
                error_details=str(e)
            )

        finally:
            # Cleanup based on policy
            if metadata.results.cleanup_policy == "cleanup":
                self._cleanup_working_directory(work_dir)

    def _create_working_directory(self, skill_name: str, execution_id: str) -> Path:
        """
        Create isolated working directory for skill execution.

        Args:
            skill_name: Name of the skill being executed.
            execution_id: Unique execution identifier.

        Returns:
            Path to created working directory.
        """
        # Create unique directory name
        dir_name = f"skill_{skill_name}_{execution_id}_{int(time.time())}"

        # Use system temp directory
        base_temp = Path(tempfile.gettempdir())
        work_dir = base_temp / "alita_skills" / dir_name

        # Create directory with proper permissions
        work_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Created working directory: {work_dir}")
        return work_dir

    def _prepare_environment(self, metadata: SkillMetadata, work_dir: Path) -> Dict[str, str]:
        """
        Prepare environment variables for subprocess execution.

        Args:
            metadata: Skill metadata with environment configuration.
            work_dir: Working directory path.

        Returns:
            Dictionary of environment variables.
        """
        # Start with current environment
        env = os.environ.copy()

        # Add skill-specific environment variables
        env.update(metadata.execution.environment)

        # Add standard variables
        env.update({
            'SKILL_NAME': metadata.name,
            'SKILL_TYPE': metadata.skill_type.value,
            'SKILL_WORK_DIR': str(work_dir),
            'PYTHONPATH': env.get('PYTHONPATH', '') + f":{work_dir}",
        })

        # Add alita-sdk to path if not present
        alita_sdk_path = str(Path(__file__).parent.parent.parent)
        if alita_sdk_path not in env.get('PYTHONPATH', ''):
            env['PYTHONPATH'] = f"{env['PYTHONPATH']}:{alita_sdk_path}"

        return env

    def _run_subprocess(
        self,
        metadata: SkillMetadata,
        work_dir: Path,
        input_file: Path,
        env: Dict[str, str]
    ) -> subprocess.CompletedProcess:
        """
        Run the skill in a subprocess.

        Args:
            metadata: Skill metadata.
            work_dir: Working directory.
            input_file: Path to input JSON file.
            env: Environment variables.

        Returns:
            CompletedProcess result.

        Raises:
            SkillExecutionError: If subprocess execution fails.
        """
        # Build command to run skill runner
        cmd = [
            sys.executable,
            "-m", "alita_sdk.runtime.skills.skill_runner",
            "--input-file", str(input_file),
            "--work-dir", str(work_dir)
        ]

        logger.debug(f"Running subprocess command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=metadata.execution.timeout
            )

            logger.debug(f"Subprocess completed with return code: {result.returncode}")

            if result.returncode != 0:
                error_msg = f"Skill subprocess failed with code {result.returncode}: {result.stderr}"
                logger.error(error_msg)
                raise SkillExecutionError(error_msg)

            return result

        except subprocess.TimeoutExpired as e:
            error_msg = f"Skill execution timed out after {metadata.execution.timeout} seconds"
            logger.error(error_msg)
            raise SkillExecutionError(error_msg) from e

        except Exception as e:
            error_msg = f"Subprocess execution failed: {str(e)}"
            logger.error(error_msg)
            raise SkillExecutionError(error_msg) from e

    def _parse_execution_result(
        self,
        metadata: SkillMetadata,
        subprocess_result: subprocess.CompletedProcess,
        work_dir: Path,
        execution_id: str,
        duration: float
    ) -> SkillExecutionResult:
        """
        Parse subprocess result into SkillExecutionResult.

        Args:
            metadata: Skill metadata.
            subprocess_result: Result from subprocess execution.
            work_dir: Working directory.
            execution_id: Execution identifier.
            duration: Execution duration.

        Returns:
            Parsed SkillExecutionResult.
        """
        # Try to read result file written by skill runner
        result_file = work_dir / "skill_result.json"

        if result_file.exists():
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)

                output_text = result_data.get('output_text', subprocess_result.stdout)
                status = SkillStatus(result_data.get('status', 'success'))
                error_details = result_data.get('error_details')

            except Exception as e:
                logger.warning(f"Failed to parse result file: {e}, using subprocess output")
                output_text = subprocess_result.stdout
                status = SkillStatus.SUCCESS
                error_details = None
        else:
            # Fallback to subprocess stdout
            output_text = subprocess_result.stdout
            status = SkillStatus.SUCCESS
            error_details = None

        # Find output files
        output_files = self._discover_output_files(work_dir, metadata.results.output_files)

        return SkillExecutionResult(
            skill_name=metadata.name,
            skill_type=metadata.skill_type,
            status=status,
            execution_mode=ExecutionMode.SUBPROCESS,
            execution_id=execution_id,
            output_text=output_text,
            output_files=output_files,
            duration=duration,
            working_directory=work_dir,
            error_details=error_details
        )

    def _discover_output_files(
        self,
        work_dir: Path,
        expected_patterns: List[str]
    ) -> List[SkillOutputFile]:
        """
        Discover output files in the working directory.

        Args:
            work_dir: Working directory to search.
            expected_patterns: List of expected file patterns.

        Returns:
            List of discovered output files.
        """
        output_files = []

        # Look for expected files first
        for pattern in expected_patterns:
            pattern_path = work_dir / pattern
            if pattern_path.exists() and pattern_path.is_file():
                output_files.append(self._create_output_file_reference(pattern_path))

        # Also discover any additional files that might have been created
        for file_path in work_dir.rglob("*"):
            if (file_path.is_file() and
                file_path.name not in ['skill_input.json', 'skill_result.json'] and
                not any(str(file_path).endswith(pattern) for pattern in expected_patterns)):

                # Only include files that seem to be outputs (not system files)
                if not file_path.name.startswith('.') and file_path.suffix in [
                    '.json', '.md', '.txt', '.csv', '.html', '.yaml', '.yml'
                ]:
                    output_files.append(self._create_output_file_reference(file_path))

        return output_files

    def _create_output_file_reference(self, file_path: Path) -> SkillOutputFile:
        """
        Create a SkillOutputFile reference for a discovered file.

        Args:
            file_path: Path to the output file.

        Returns:
            SkillOutputFile reference.
        """
        # Determine file type from extension
        file_type = file_path.suffix.lstrip('.').lower()
        if not file_type:
            file_type = 'unknown'

        # Get file size
        try:
            size_bytes = file_path.stat().st_size
        except OSError:
            size_bytes = 0

        # Generate description based on file name
        description = file_path.stem.replace('_', ' ').replace('-', ' ').title()

        return SkillOutputFile(
            path=file_path,
            description=description,
            file_type=file_type,
            size_bytes=size_bytes
        )

    def _cleanup_working_directory(self, work_dir: Path) -> None:
        """
        Clean up working directory after execution.

        Args:
            work_dir: Directory to clean up.
        """
        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
                logger.debug(f"Cleaned up working directory: {work_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup working directory {work_dir}: {e}")


class RemoteSkillExecutor(SkillExecutor):
    """
    Remote skill executor using AlitaClient for distributed execution.
    """

    def _execute_skill_internal(
        self,
        metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        execution_id: str = None
    ) -> SkillExecutionResult:
        """
        Execute skill remotely via AlitaClient.

        For platform-based skills (agents/pipelines), uses the AlitaClient
        to execute them directly on the platform.
        """
        if not self.alita_client:
            raise SkillExecutionError(
                "AlitaClient is required for remote skill execution"
            )

        start_time = time.time()

        try:
            # Handle platform-based skills (agents/pipelines)
            if metadata.source == SkillSource.PLATFORM:
                return self._execute_platform_skill(
                    metadata, task, context, chat_history, execution_id, start_time
                )

            # Handle filesystem-based skills (remote execution)
            else:
                return self._execute_filesystem_skill_remotely(
                    metadata, task, context, chat_history, execution_id, start_time
                )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Remote skill execution failed for '{metadata.name}': {e}")

            return SkillExecutionResult(
                skill_name=metadata.name,
                skill_type=metadata.skill_type,
                status=SkillStatus.ERROR,
                execution_mode=ExecutionMode.REMOTE,
                execution_id=execution_id,
                output_text=f"Remote skill execution failed: {str(e)}",
                output_files=[],
                duration=duration,
                error_details=str(e)
            )

    def _execute_platform_skill(
        self,
        metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        execution_id: str = None,
        start_time: float = None
    ) -> SkillExecutionResult:
        """
        Execute a platform-based skill (agent or pipeline).
        """
        try:
            if metadata.skill_type == SkillType.AGENT:
                # Execute agent via AlitaClient
                result = self._execute_platform_agent(metadata, task, context, chat_history)
            elif metadata.skill_type == SkillType.PIPELINE:
                # Execute pipeline via AlitaClient
                result = self._execute_platform_pipeline(metadata, task, context, chat_history)
            else:
                raise SkillExecutionError(f"Unsupported platform skill type: {metadata.skill_type}")

            duration = time.time() - start_time

            return SkillExecutionResult(
                skill_name=metadata.name,
                skill_type=metadata.skill_type,
                status=SkillStatus.SUCCESS,
                execution_mode=ExecutionMode.REMOTE,
                execution_id=execution_id,
                output_text=result,
                output_files=[],
                duration=duration,
                error_details=None
            )

        except Exception as e:
            duration = time.time() - start_time
            raise SkillExecutionError(f"Platform skill execution failed: {e}")

    def _execute_platform_agent(
        self,
        metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Execute a platform-hosted agent."""
        try:
            # Get agent application from platform
            app = self.alita_client.application(metadata.id, metadata.version_id)

            # Prepare input message for agent
            if chat_history:
                # If we have chat history, append the task as the latest message
                messages = chat_history + [{"role": "user", "content": task}]
            else:
                # Create fresh conversation with the task
                messages = [{"role": "user", "content": task}]

            # Add context as variables if provided
            variables = context or {}

            # Execute the agent
            logger.info(f"Executing platform agent {metadata.id}/{metadata.version_id} with task: {task}")
            response = app.invoke({
                "input": task,
                "messages": messages,
                **variables  # Spread context variables
            })

            # Extract output text from response
            if isinstance(response, dict):
                return response.get("output", str(response))
            else:
                return str(response)

        except Exception as e:
            logger.error(f"Failed to execute platform agent {metadata.id}/{metadata.version_id}: {e}")
            raise SkillExecutionError(f"Agent execution failed: {e}")

    def _execute_platform_pipeline(
        self,
        metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Execute a platform-hosted pipeline."""
        try:
            # Get pipeline application from platform
            app = self.alita_client.application(metadata.id, metadata.version_id)

            # Prepare input for pipeline
            # Pipelines typically work with input and context/state variables
            pipeline_input = {
                "input": task
            }

            # Add context variables
            if context:
                pipeline_input.update(context)

            # Execute the pipeline
            logger.info(f"Executing platform pipeline {metadata.id}/{metadata.version_id} with task: {task}")
            response = app.invoke(pipeline_input)

            # Extract output text from response
            if isinstance(response, dict):
                return response.get("output", str(response))
            else:
                return str(response)

        except Exception as e:
            logger.error(f"Failed to execute platform pipeline {metadata.id}/{metadata.version_id}: {e}")
            raise SkillExecutionError(f"Pipeline execution failed: {e}")

    def _execute_filesystem_skill_remotely(
        self,
        metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        execution_id: str = None,
        start_time: float = None
    ) -> SkillExecutionResult:
        """
        Execute a filesystem-based skill remotely.

        This is a placeholder for future remote execution of filesystem skills.
        For now, it falls back to subprocess execution.
        """
        logger.warning(f"Remote execution of filesystem skill '{metadata.name}' not implemented, using subprocess")

        # Fall back to subprocess execution
        subprocess_executor = SubprocessSkillExecutor(self.alita_client)
        return subprocess_executor._execute_skill_internal(
            metadata, task, context, chat_history, execution_id
        )