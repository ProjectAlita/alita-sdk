"""
Skill runner subprocess entry point.

This module is executed as a subprocess by the skill executor to run
individual skills in isolation. It handles both graph and agent skills
using the existing alita-sdk infrastructure.
"""

import argparse
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logging for subprocess
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

logger = logging.getLogger(__name__)

# Import alita-sdk components
try:
    from ..langchain.assistant import Assistant
    from ..langchain.langraph_agent import create_graph
    from ..clients.client import AlitaClient
    from .models import SkillMetadata, SkillType, SkillStatus
except ImportError as e:
    logger.error(f"Failed to import alita-sdk components: {e}")
    sys.exit(1)


class SkillRunner:
    """
    Subprocess skill runner that executes individual skills.
    """

    def __init__(self):
        self.work_dir = None
        self.skill_metadata = None
        self.skill_input = None
        self.execution_id = None

    def run(self, input_file: Path, work_dir: Path) -> None:
        """
        Run a skill based on input file configuration.

        Args:
            input_file: Path to JSON input file with skill configuration.
            work_dir: Working directory for execution.
        """
        self.work_dir = work_dir
        result_file = work_dir / "skill_result.json"

        try:
            # Load input configuration
            self._load_input(input_file)

            # Execute skill based on type
            if self.skill_metadata.skill_type == SkillType.AGENT:
                result = self._run_agent_skill()
            else:  # SkillType.GRAPH
                result = self._run_graph_skill()

            # Write successful result
            self._write_result(result_file, {
                'status': 'success',
                'output_text': result,
                'execution_id': self.execution_id
            })

            logger.info(f"Skill '{self.skill_metadata.name}' completed successfully")

        except Exception as e:
            logger.error(f"Skill execution failed: {e}")
            logger.error(traceback.format_exc())

            # Write error result
            self._write_result(result_file, {
                'status': 'error',
                'output_text': f"Skill execution failed: {str(e)}",
                'error_details': str(e),
                'execution_id': self.execution_id
            })

            # Exit with error code
            sys.exit(1)

    def _load_input(self, input_file: Path) -> None:
        """
        Load skill configuration and input from JSON file.

        Args:
            input_file: Path to input JSON file.
        """
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Recreate SkillMetadata from dict
            self.skill_metadata = SkillMetadata(**data['skill_metadata'])
            self.skill_input = data['skill_input']
            self.execution_id = data['execution_id']

            logger.info(f"Loaded skill '{self.skill_metadata.name}' ({self.skill_metadata.skill_type.value})")

        except Exception as e:
            raise RuntimeError(f"Failed to load input file {input_file}: {e}")

    def _run_agent_skill(self) -> str:
        """
        Run an agent-type skill using the Assistant framework.

        Returns:
            Skill execution result as text.
        """
        logger.info("Executing agent skill")

        # Create mock AlitaClient (in production this would be passed or configured)
        # For subprocess execution, we need to handle this differently
        alita_client = self._create_mock_client()

        # Create LLM client
        llm = self._create_llm_client()

        # Build agent data structure compatible with Assistant
        agent_data = self._build_agent_data_structure()

        # Create Assistant instance
        assistant = Assistant(
            alita=alita_client,
            data=agent_data,
            client=llm,
            chat_history=self.skill_input.get('chat_history', []),
            app_type=self.skill_metadata.agent_type or 'react',
            tools=[]  # TODO: Load tools based on toolkit configuration
        )

        # Execute agent
        agent_executor = assistant.runnable()
        result = agent_executor.invoke({
            'input': self.skill_input['input'],
            'chat_history': self.skill_input.get('chat_history', []),
            **self.skill_input.get('variables', {})
        })

        # Extract output text
        if isinstance(result, dict):
            output_text = result.get('output', str(result))
        else:
            output_text = str(result)

        return output_text

    def _run_graph_skill(self) -> str:
        """
        Run a graph-type skill using the LangGraph framework.

        Returns:
            Skill execution result as text.
        """
        logger.info("Executing graph skill")

        # Create LLM client
        llm = self._create_llm_client()

        # Create graph from skill's YAML definition
        if not self.skill_metadata.graph_yaml:
            raise ValueError("Graph skill missing YAML definition")

        graph = create_graph(
            client=llm,
            yaml_schema=self.skill_metadata.graph_yaml,
            tools=[],  # TODO: Load tools based on configuration
            memory=None,  # TODO: Configure memory if needed
            store=None   # TODO: Configure store if needed
        )

        # Execute graph with state input
        result = graph.invoke(self.skill_input)

        # Extract output from graph result
        if isinstance(result, dict):
            # Try to get 'output' field first, then look for other relevant fields
            output_text = (result.get('output') or
                          result.get('messages', [{}])[-1].get('content', '') or
                          str(result))
        else:
            output_text = str(result)

        return output_text

    def _build_agent_data_structure(self) -> Dict[str, Any]:
        """
        Build agent data structure compatible with Assistant.

        Returns:
            Agent configuration dictionary.
        """
        # Build LLM settings
        llm_settings = {
            'model_name': self.skill_metadata.model or 'gpt-4o',
            'temperature': self.skill_metadata.temperature or 0.7,
            'max_tokens': self.skill_metadata.max_tokens or 2000,
            'top_p': 1.0,
            'top_k': -1
        }

        # Build tools configuration from toolkits
        tools = []
        if self.skill_metadata.toolkits:
            for toolkit_config in self.skill_metadata.toolkits:
                # Convert toolkit config to tool format expected by Assistant
                tools.append({
                    'type': toolkit_config.get('type', 'unknown'),
                    'name': toolkit_config.get('name', toolkit_config.get('type')),
                    'toolkit_name': toolkit_config.get('type'),
                    'config_ref': toolkit_config.get('config_ref')
                })

        return {
            'name': self.skill_metadata.name,
            'description': self.skill_metadata.description,
            'llm_settings': llm_settings,
            'agent_type': self.skill_metadata.agent_type or 'react',
            'system_prompt': self.skill_metadata.system_prompt,
            'tools': tools,
            'meta': {
                'step_limit': 25  # Default step limit
            }
        }

    def _create_mock_client(self):
        """
        Create a mock AlitaClient for subprocess execution.

        In a real implementation, this would be properly configured
        or passed from the parent process.
        """
        # TODO: Implement proper client creation based on configuration
        # For now, return None - the Assistant should handle this gracefully
        return None

    def _create_llm_client(self):
        """
        Create LLM client based on skill metadata.

        Returns:
            Configured LLM client.
        """
        # TODO: Implement proper LLM client creation
        # This would typically involve:
        # 1. Reading API keys from environment
        # 2. Creating appropriate LLM instance based on model
        # 3. Configuring with skill-specific settings

        # For now, return a placeholder that indicates LLM is needed
        class MockLLM:
            def __init__(self):
                self.model_name = self.skill_metadata.model or 'gpt-4o'
                self.temperature = self.skill_metadata.temperature or 0.7
                self.max_tokens = self.skill_metadata.max_tokens or 2000

            def invoke(self, messages, **kwargs):
                # This is a placeholder - in real implementation this would
                # call the actual LLM API
                return f"Mock LLM response for: {messages[-1] if messages else 'empty input'}"

        return MockLLM()

    def _write_result(self, result_file: Path, result_data: Dict[str, Any]) -> None:
        """
        Write execution result to file for parent process.

        Args:
            result_file: Path to result file.
            result_data: Result data to write.
        """
        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to write result file: {e}")
            raise


def main():
    """
    Main entry point for skill runner subprocess.
    """
    parser = argparse.ArgumentParser(description="Alita Skills Runner")
    parser.add_argument(
        '--input-file',
        type=Path,
        required=True,
        help="Path to JSON input file with skill configuration"
    )
    parser.add_argument(
        '--work-dir',
        type=Path,
        required=True,
        help="Working directory for skill execution"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.input_file.exists():
        logger.error(f"Input file does not exist: {args.input_file}")
        sys.exit(1)

    if not args.work_dir.exists():
        logger.error(f"Working directory does not exist: {args.work_dir}")
        sys.exit(1)

    # Change to working directory
    os.chdir(args.work_dir)

    # Run skill
    runner = SkillRunner()
    runner.run(args.input_file, args.work_dir)


if __name__ == '__main__':
    main()