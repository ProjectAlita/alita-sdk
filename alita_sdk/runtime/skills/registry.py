"""
Skills Registry service for managing and querying skills.

This module provides a thread-safe registry service that uses the discovery
service to find skills and provides a clean API for skill management.
"""

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

from .discovery import SkillDiscovery
from .models import SkillMetadata, SkillType

logger = logging.getLogger(__name__)


class SkillsRegistry:
    """
    Thread-safe registry service for managing skills.

    The registry uses a discovery service to find skills and provides
    a clean API for querying, filtering, and managing skills.
    """

    def __init__(self, search_paths: Optional[List[str]] = None):
        """
        Initialize the skills registry.

        Args:
            search_paths: Custom search paths for skills. If None, uses defaults.
        """
        self.discovery = SkillDiscovery(search_paths)
        self._lock = threading.RLock()
        self._initialized = False

        logger.info("Skills registry initialized")

    def discover(self, refresh: bool = False) -> Dict[str, SkillMetadata]:
        """
        Discover skills from configured search paths.

        This is the primary method to populate the registry with skills.
        It's thread-safe and can be called multiple times.

        Args:
            refresh: If True, clear cache and rescan all directories.

        Returns:
            Dictionary mapping skill names to SkillMetadata objects.
        """
        with self._lock:
            skills = self.discovery.discover(refresh=refresh)
            self._initialized = True
            logger.info(f"Registry discovered {len(skills)} skills")
            return skills

    def list(self) -> List[SkillMetadata]:
        """
        Get list of all discovered skills.

        Returns:
            List of SkillMetadata objects.
        """
        with self._lock:
            if not self._initialized:
                self.discover()
            return list(self.discovery.cache.values())

    def get(self, name: str) -> Optional[SkillMetadata]:
        """
        Get a skill by name.

        Args:
            name: Name of the skill to retrieve.

        Returns:
            SkillMetadata if found, None otherwise.
        """
        with self._lock:
            if not self._initialized:
                self.discover()
            return self.discovery.get_skill_by_name(name)

    def find_by_capability(self, capability: str) -> List[SkillMetadata]:
        """
        Find skills that provide a specific capability.

        Args:
            capability: Capability to search for.

        Returns:
            List of matching SkillMetadata objects.
        """
        with self._lock:
            if not self._initialized:
                self.discover()
            return self.discovery.find_skills_by_capability(capability)

    def find_by_tag(self, tag: str) -> List[SkillMetadata]:
        """
        Find skills with a specific tag.

        Args:
            tag: Tag to search for.

        Returns:
            List of matching SkillMetadata objects.
        """
        with self._lock:
            if not self._initialized:
                self.discover()
            return self.discovery.find_skills_by_tag(tag)

    def find_by_type(self, skill_type: SkillType) -> List[SkillMetadata]:
        """
        Find skills of a specific type (graph or agent).

        Args:
            skill_type: SkillType to filter by.

        Returns:
            List of matching SkillMetadata objects.
        """
        with self._lock:
            if not self._initialized:
                self.discover()
            return self.discovery.find_skills_by_type(skill_type)

    def reload(self, name: str) -> Optional[SkillMetadata]:
        """
        Reload a specific skill from disk.

        This is useful when you know a specific skill has been updated
        and you want to reload just that skill without refreshing all.

        Args:
            name: Name of the skill to reload.

        Returns:
            Updated SkillMetadata if found and reloaded, None otherwise.
        """
        with self._lock:
            # Get current skill to know where to look
            current_skill = self.get(name)
            if not current_skill:
                logger.warning(f"Cannot reload skill '{name}': not found in registry")
                return None

            skill_path = Path(current_skill.path)
            agent_file = skill_path / "agent.md"

            try:
                # Parse the skill file directly
                updated_skill = self.discovery._parse_skill_file(agent_file)
                if updated_skill and updated_skill.name == name:
                    # Update cache with reloaded skill
                    self.discovery.cache[name] = updated_skill
                    logger.info(f"Successfully reloaded skill: {name}")
                    return updated_skill
                else:
                    logger.error(f"Reloaded skill name mismatch: expected '{name}', got '{updated_skill.name if updated_skill else None}'")
                    return None

            except Exception as e:
                logger.error(f"Failed to reload skill '{name}': {e}")
                return None

    def clear(self) -> None:
        """
        Clear the registry cache.

        This removes all cached skills. The next query will trigger
        a fresh discovery.
        """
        with self._lock:
            self.discovery.cache.clear()
            self._initialized = False
            logger.info("Registry cache cleared")

    def is_skill_valid(self, name: str) -> bool:
        """
        Check if a skill exists and is valid.

        Args:
            name: Name of the skill to check.

        Returns:
            True if skill exists and is valid, False otherwise.
        """
        skill = self.get(name)
        return skill is not None

    def validate_skill_at_path(self, skill_path: str) -> tuple[bool, Optional[str]]:
        """
        Validate a skill definition at a specific path.

        This can be used to validate a skill before adding it to
        the registry or to check if a skill definition is valid.

        Args:
            skill_path: Path to skill directory containing agent.md.

        Returns:
            Tuple of (is_valid, error_message).
        """
        return self.discovery.validate_skill_definition(Path(skill_path))

    def get_registry_stats(self) -> Dict[str, int]:
        """
        Get statistics about the registry contents.

        Returns:
            Dictionary with registry statistics.
        """
        with self._lock:
            if not self._initialized:
                self.discover()

            stats = {
                "total_skills": len(self.discovery.cache),
                "graph_skills": len(self.find_by_type(SkillType.GRAPH)),
                "agent_skills": len(self.find_by_type(SkillType.AGENT))
            }

            # Count unique capabilities and tags
            all_capabilities = set()
            all_tags = set()
            for skill in self.discovery.cache.values():
                all_capabilities.update(skill.capabilities)
                all_tags.update(skill.tags)

            stats["unique_capabilities"] = len(all_capabilities)
            stats["unique_tags"] = len(all_tags)

            return stats

    def get_skills_by_search_path(self) -> Dict[str, List[SkillMetadata]]:
        """
        Get skills grouped by their search path.

        This is useful for understanding which skills come from which
        directories and for debugging discovery issues.

        Returns:
            Dictionary mapping search paths to lists of skills.
        """
        with self._lock:
            if not self._initialized:
                self.discover()

            path_groups = {}
            for skill in self.discovery.cache.values():
                skill_path = Path(skill.path)

                # Find which search path this skill belongs to
                for search_path in self.discovery.search_paths:
                    search_path_obj = Path(search_path).expanduser().resolve()
                    try:
                        if skill_path.is_relative_to(search_path_obj):
                            if search_path not in path_groups:
                                path_groups[search_path] = []
                            path_groups[search_path].append(skill)
                            break
                    except (ValueError, OSError):
                        # skill_path is not relative to this search path
                        continue

            return path_groups

    def refresh_if_stale(self, max_age_seconds: int = 300) -> bool:
        """
        Refresh the registry if it's considered stale.

        Args:
            max_age_seconds: Maximum age in seconds before refresh.

        Returns:
            True if refresh was performed, False if cache is still fresh.
        """
        # This is a simple implementation - in production you might want
        # to track file modification times or use a more sophisticated
        # staleness check
        with self._lock:
            if not self._initialized:
                self.discover()
                return True

            # For now, always consider the cache fresh since we don't
            # track timestamps. This method provides the interface
            # for future enhancement.
            # TODO: Implement actual staleness check using max_age_seconds
            _ = max_age_seconds  # Suppress unused parameter warning
            return False

    def __len__(self) -> int:
        """Return the number of skills in the registry."""
        return len(self.list())

    def __contains__(self, name: str) -> bool:
        """Check if a skill name exists in the registry."""
        return self.is_skill_valid(name)

    def __repr__(self) -> str:
        """String representation of the registry."""
        stats = self.get_registry_stats()
        return (
            f"SkillsRegistry("
            f"skills={stats['total_skills']}, "
            f"graphs={stats['graph_skills']}, "
            f"agents={stats['agent_skills']})"
        )


# Global registry instance for convenience
_default_registry: Optional[SkillsRegistry] = None
_registry_lock = threading.Lock()


def get_default_registry() -> SkillsRegistry:
    """
    Get the default global skills registry instance.

    This provides a convenient way to access a shared registry
    without having to pass it around. The registry is created
    lazily on first access.

    Returns:
        Default SkillsRegistry instance.
    """
    global _default_registry

    with _registry_lock:
        if _default_registry is None:
            _default_registry = SkillsRegistry()
            logger.info("Created default skills registry")

        return _default_registry


def reset_default_registry() -> None:
    """
    Reset the default registry instance.

    This is mainly useful for testing or when you want to
    reinitialize the registry with different settings.
    """
    global _default_registry

    with _registry_lock:
        if _default_registry is not None:
            _default_registry.clear()
        _default_registry = None
        logger.info("Reset default skills registry")