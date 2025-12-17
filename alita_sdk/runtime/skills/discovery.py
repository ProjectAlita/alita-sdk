"""
Skill discovery service for finding and validating skills from filesystem.

This module handles the discovery of skill definitions from configurable
directories, parsing agent.md files, and creating validated SkillMetadata objects.
"""

import logging
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import (
    SkillMetadata, SkillType, ExecutionConfig, ResultsConfig,
    SkillInputSchema, SkillOutputSchema, SkillValidationError
)

logger = logging.getLogger(__name__)


class SkillDiscovery:
    """Service for discovering and validating skills from filesystem."""

    def __init__(self, search_paths: Optional[List[str]] = None):
        """
        Initialize skill discovery service.

        Args:
            search_paths: Custom search paths. If None, uses default paths.
        """
        self.search_paths = search_paths or self._get_default_search_paths()
        self.cache: Dict[str, SkillMetadata] = {}
        logger.info(f"Initialized skill discovery with paths: {self.search_paths}")

    @staticmethod
    def _get_default_search_paths() -> List[str]:
        """Get default search paths for skills."""
        return [
            ".alita/agents/skills",
            "./skills",
            os.path.expanduser("~/.alita/skills")
        ]

    def discover(self, refresh: bool = False) -> Dict[str, SkillMetadata]:
        """
        Discover skills from configured search paths.

        Args:
            refresh: If True, clear cache and rescan all directories.

        Returns:
            Dictionary mapping skill names to SkillMetadata objects.

        Raises:
            Exception: If discovery fails critically.
        """
        if not refresh and self.cache:
            logger.debug(f"Returning cached skills: {len(self.cache)} found")
            return self.cache

        if refresh:
            logger.info("Refreshing skill discovery cache")
            self.cache.clear()

        discovered_skills = {}

        for search_path in self.search_paths:
            try:
                path_skills = self._discover_in_path(search_path)
                logger.info(f"Found {len(path_skills)} skills in {search_path}")

                # Handle name collisions
                for name, skill in path_skills.items():
                    if name in discovered_skills:
                        logger.warning(
                            f"Skill name collision: '{name}' found in both "
                            f"{discovered_skills[name].path} and {skill.path}. "
                            f"Using the latter."
                        )
                    discovered_skills[name] = skill

            except Exception as e:
                logger.error(f"Error discovering skills in {search_path}: {e}")
                # Continue with other paths rather than failing completely

        logger.info(f"Discovery complete: {len(discovered_skills)} skills found")
        self.cache = discovered_skills
        return discovered_skills

    def _discover_in_path(self, search_path: str) -> Dict[str, SkillMetadata]:
        """
        Discover skills in a specific path.

        Args:
            search_path: Path to search for skills.

        Returns:
            Dictionary of discovered skills.
        """
        path = Path(search_path).expanduser().resolve()

        if not path.exists():
            logger.debug(f"Search path does not exist: {path}")
            return {}

        if not path.is_dir():
            logger.warning(f"Search path is not a directory: {path}")
            return {}

        skills = {}

        # Recursively find all agent.md files, including through symlinks
        for agent_file in self._find_agent_files(path):
            try:
                skill_metadata = self._parse_skill_file(agent_file)
                if skill_metadata:
                    skills[skill_metadata.name] = skill_metadata
                    logger.debug(f"Discovered skill: {skill_metadata.name} at {agent_file.parent}")
            except Exception as e:
                logger.error(f"Error parsing skill file {agent_file}: {e}")
                continue

        return skills

    def _find_agent_files(self, path: Path) -> list[Path]:
        """
        Find all agent.md files, including through symlinks.

        Python's rglob doesn't follow symlinks by default, so we need
        to handle them manually for skills discovery.

        Args:
            path: Root path to search from.

        Returns:
            List of agent.md file paths found.
        """
        agent_files = []

        def _walk_directory(current_path: Path, visited: set = None):
            if visited is None:
                visited = set()

            # Avoid infinite loops from circular symlinks
            resolved_path = current_path.resolve()
            if resolved_path in visited:
                return
            visited.add(resolved_path)

            try:
                if not current_path.exists() or not current_path.is_dir():
                    return

                for item in current_path.iterdir():
                    if item.name == "agent.md" and item.is_file():
                        agent_files.append(item)
                    elif item.is_dir():
                        # Recurse into subdirectories (including symlinked ones)
                        _walk_directory(item, visited.copy())

            except (PermissionError, OSError) as e:
                logger.debug(f"Cannot access {current_path}: {e}")

        _walk_directory(path)
        logger.debug(f"Found {len(agent_files)} agent.md files in {path}")
        return agent_files

    def _parse_skill_file(self, agent_file: Path) -> Optional[SkillMetadata]:
        """
        Parse an agent.md file and create SkillMetadata.

        Args:
            agent_file: Path to agent.md file.

        Returns:
            SkillMetadata object if valid, None otherwise.

        Raises:
            SkillValidationError: If skill definition is invalid.
        """
        logger.debug(f"Parsing skill file: {agent_file}")

        try:
            content = agent_file.read_text(encoding='utf-8')
            logger.debug(f"Read {len(content)} characters from {agent_file}")
        except Exception as e:
            logger.error(f"Cannot read file {agent_file}: {e}")
            raise SkillValidationError(f"Cannot read file {agent_file}: {e}")

        # Extract YAML frontmatter
        frontmatter, body = self._extract_frontmatter(content)

        if not frontmatter:
            logger.debug(f"No frontmatter found in {agent_file}")
            return None

        logger.debug(f"Extracted frontmatter from {agent_file}: {list(frontmatter.keys())}")

        # Validate agent_type
        agent_type = frontmatter.get('agent_type')
        if agent_type != 'skill':
            logger.debug(f"File {agent_file} is not a skill (agent_type: {agent_type})")
            return None

        logger.debug(f"Agent type validation passed for {agent_file}")

        # Validate and create metadata
        try:
            metadata = self._create_skill_metadata(frontmatter, body, agent_file.parent)
            logger.debug(f"Successfully created metadata for skill: {metadata.name}")
            return metadata
        except Exception as e:
            logger.error(f"Invalid skill definition in {agent_file}: {e}")
            raise SkillValidationError(f"Invalid skill definition in {agent_file}: {e}")

    def _extract_frontmatter(self, content: str) -> Tuple[Optional[Dict], str]:
        """
        Extract YAML frontmatter from markdown content.

        Args:
            content: Full file content.

        Returns:
            Tuple of (frontmatter_dict, remaining_body).
        """
        # Match YAML frontmatter pattern
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return None, content

        try:
            frontmatter = yaml.safe_load(match.group(1))
            body = match.group(2).strip()
            return frontmatter, body
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML frontmatter: {e}")
            return None, content

    def _create_skill_metadata(
        self,
        frontmatter: Dict,
        body: str,
        skill_path: Path
    ) -> SkillMetadata:
        """
        Create SkillMetadata from parsed frontmatter.

        Args:
            frontmatter: Parsed YAML frontmatter.
            body: Markdown body content.
            skill_path: Path to skill directory.

        Returns:
            Validated SkillMetadata object.

        Raises:
            SkillValidationError: If validation fails.
        """
        logger.debug(f"Creating skill metadata from frontmatter keys: {list(frontmatter.keys())}")

        # Validate required fields
        name = frontmatter.get('name')
        if not name:
            raise SkillValidationError("Missing required field: name")

        logger.debug(f"Skill name: {name}")

        description = frontmatter.get('description', '')
        skill_type_str = frontmatter.get('skill_type', 'agent')

        logger.debug(f"Skill type string: {skill_type_str}")

        try:
            skill_type = SkillType(skill_type_str)
            logger.debug(f"Parsed skill type: {skill_type}")
        except ValueError:
            raise SkillValidationError(f"Invalid skill_type: {skill_type_str}. Must be 'graph' or 'agent'")

        # Parse execution configuration
        logger.debug(f"Parsing execution config: {frontmatter.get('execution', {})}")
        try:
            execution_config = self._parse_execution_config(frontmatter.get('execution', {}))
            logger.debug(f"Created execution config: {execution_config}")
        except Exception as e:
            logger.error(f"Failed to parse execution config: {e}")
            raise SkillValidationError(f"Invalid execution configuration: {e}")

        # Parse results configuration
        logger.debug(f"Parsing results config: {frontmatter.get('results', {})}")
        try:
            results_config = self._parse_results_config(frontmatter.get('results', {}))
            logger.debug(f"Created results config: {results_config}")
        except Exception as e:
            logger.error(f"Failed to parse results config: {e}")
            raise SkillValidationError(f"Invalid results configuration: {e}")

        # Parse input/output schemas
        logger.debug(f"Parsing input schema: {frontmatter.get('inputs', {})}")
        try:
            inputs = self._parse_input_schema(frontmatter.get('inputs', {}), skill_type)
            logger.debug(f"Created input schema: {inputs}")
        except Exception as e:
            logger.error(f"Failed to parse input schema: {e}")
            raise SkillValidationError(f"Invalid input schema: {e}")

        logger.debug(f"Parsing output schema: {frontmatter.get('outputs', {})}")
        try:
            outputs = self._parse_output_schema(frontmatter.get('outputs', {}))
            logger.debug(f"Created output schema: {outputs}")
        except Exception as e:
            logger.error(f"Failed to parse output schema: {e}")
            raise SkillValidationError(f"Invalid output schema: {e}")

        # Create base metadata
        logger.debug("Creating SkillMetadata object...")
        try:
            from .models import SkillSource
            metadata = SkillMetadata(
                name=name,
                skill_type=skill_type,
                source=SkillSource.FILESYSTEM,
                path=str(skill_path),
                description=description,
                capabilities=frontmatter.get('capabilities', []),
                tags=frontmatter.get('tags', []),
                version=frontmatter.get('version', '1.0.0'),
                execution=execution_config,
                results=results_config,
                inputs=inputs,
                outputs=outputs,
                model=frontmatter.get('model'),
                temperature=frontmatter.get('temperature'),
                max_tokens=frontmatter.get('max_tokens')
            )
            logger.debug("Base metadata created successfully")
        except Exception as e:
            logger.error(f"Failed to create base metadata: {e}")
            raise SkillValidationError(f"Failed to create skill metadata: {e}")

        # Add type-specific fields
        try:
            if skill_type == SkillType.GRAPH:
                metadata.state_schema = frontmatter.get('state', {})
                metadata.nodes = frontmatter.get('nodes', [])
                # Store complete YAML for graph reconstruction
                metadata.graph_yaml = self._build_graph_yaml(frontmatter)
                logger.debug("Added graph-specific fields")
            else:  # AGENT
                metadata.system_prompt = body if body else frontmatter.get('system_prompt')
                metadata.agent_type = frontmatter.get('agent_subtype', 'react')  # Use different field name
                metadata.toolkits = frontmatter.get('toolkits', [])
                logger.debug("Added agent-specific fields")

            # Validate type-specific requirements
            self._validate_skill_type_requirements(metadata)

            logger.debug(f"Successfully created skill metadata: {name} ({skill_type.value})")
            return metadata

        except Exception as e:
            logger.error(f"Failed to add type-specific fields: {e}")
            raise SkillValidationError(f"Failed to complete skill metadata: {e}")

    def _parse_execution_config(self, execution_data: Dict) -> ExecutionConfig:
        """Parse execution configuration from frontmatter."""
        return ExecutionConfig(
            mode=execution_data.get('mode', 'subprocess'),
            timeout=execution_data.get('timeout', 300),
            working_directory=execution_data.get('working_directory'),
            environment=execution_data.get('environment', {}),
            max_retries=execution_data.get('max_retries', 0)
        )

    def _parse_results_config(self, results_data: Dict) -> ResultsConfig:
        """Parse results configuration from frontmatter."""
        return ResultsConfig(
            format=results_data.get('format', 'text_with_links'),
            output_files=results_data.get('output_files', []),
            cleanup_policy=results_data.get('cleanup_policy', 'preserve')
        )

    def _parse_input_schema(self, inputs_data: Dict, skill_type: SkillType) -> SkillInputSchema:
        """Parse input schema based on skill type."""
        schema = SkillInputSchema()

        if skill_type == SkillType.AGENT:
            schema.variables = inputs_data.get('variables', {})
            schema.chat_history = inputs_data.get('chat_history')
            schema.user_input = inputs_data.get('user_input')
        else:  # GRAPH
            schema.state_variables = inputs_data.get('state_variables', {})

        return schema

    def _parse_output_schema(self, outputs_data: Dict) -> SkillOutputSchema:
        """Parse output schema from frontmatter."""
        return SkillOutputSchema(
            primary_output=outputs_data.get('primary_output', {
                "type": "text",
                "description": "Main result text"
            }),
            generated_files=outputs_data.get('generated_files', {
                "type": "list[file_reference]",
                "description": "Created files"
            }),
            additional_outputs=outputs_data.get('additional_outputs')
        )

    def _build_graph_yaml(self, frontmatter: Dict) -> str:
        """Build complete YAML for graph skills."""
        graph_definition = {
            'name': frontmatter.get('name'),
            'description': frontmatter.get('description'),
            'state': frontmatter.get('state', {}),
            'nodes': frontmatter.get('nodes', []),
            'entry_point': frontmatter.get('entry_point'),
            'interrupt_before': frontmatter.get('interrupt_before', []),
            'interrupt_after': frontmatter.get('interrupt_after', [])
        }

        # Remove None values
        graph_definition = {k: v for k, v in graph_definition.items() if v is not None}

        return yaml.dump(graph_definition, default_flow_style=False)

    def _validate_skill_type_requirements(self, metadata: SkillMetadata) -> None:
        """
        Validate type-specific requirements for skills.

        Args:
            metadata: SkillMetadata to validate.

        Raises:
            SkillValidationError: If validation fails.
        """
        if metadata.skill_type == SkillType.GRAPH:
            if not metadata.state_schema:
                logger.warning(f"Graph skill {metadata.name} has no state schema")
            if not metadata.nodes:
                raise SkillValidationError(f"Graph skill {metadata.name} must have nodes defined")

        elif metadata.skill_type == SkillType.AGENT:
            if not metadata.system_prompt:
                logger.warning(f"Agent skill {metadata.name} has no system prompt")
            if not metadata.toolkits:
                logger.warning(f"Agent skill {metadata.name} has no toolkits defined")

    def get_skill_by_name(self, name: str) -> Optional[SkillMetadata]:
        """
        Get a specific skill by name.

        Args:
            name: Name of the skill to retrieve.

        Returns:
            SkillMetadata if found, None otherwise.
        """
        if not self.cache:
            self.discover()

        return self.cache.get(name)

    def find_skills_by_capability(self, capability: str) -> List[SkillMetadata]:
        """
        Find skills that provide a specific capability.

        Args:
            capability: Capability to search for.

        Returns:
            List of matching SkillMetadata objects.
        """
        if not self.cache:
            self.discover()

        return [
            skill for skill in self.cache.values()
            if capability in skill.capabilities
        ]

    def find_skills_by_tag(self, tag: str) -> List[SkillMetadata]:
        """
        Find skills with a specific tag.

        Args:
            tag: Tag to search for.

        Returns:
            List of matching SkillMetadata objects.
        """
        if not self.cache:
            self.discover()

        return [
            skill for skill in self.cache.values()
            if tag in skill.tags
        ]

    def find_skills_by_type(self, skill_type: SkillType) -> List[SkillMetadata]:
        """
        Find skills of a specific type.

        Args:
            skill_type: SkillType to filter by.

        Returns:
            List of matching SkillMetadata objects.
        """
        if not self.cache:
            self.discover()

        return [
            skill for skill in self.cache.values()
            if skill.skill_type == skill_type
        ]

    def validate_skill_definition(self, skill_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate a skill definition without adding it to cache.

        Args:
            skill_path: Path to skill directory containing agent.md.

        Returns:
            Tuple of (is_valid, error_message).
        """
        agent_file = skill_path / "agent.md"

        if not agent_file.exists():
            return False, f"agent.md not found in {skill_path}"

        try:
            self._parse_skill_file(agent_file)
            return True, None
        except Exception as e:
            return False, str(e)