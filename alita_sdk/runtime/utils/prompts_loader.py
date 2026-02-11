"""Prompt constants.

Keep large prompt strings out of strategy implementations to reduce noise,
make reviews easier, and allow centralized updates.

Prompts are loaded from markdown files in alita_sdk/prompts/ directory.
"""

from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


class PromptFile(Enum):
    """Enum of available prompt markdown files."""

    ERROR_TRANSFORMATION_SYSTEM = "transform_error_system_prompt.md"
    ERROR_TRANSFORMATION_USER_SUFFIX = "transform_error_user_prompt_suffix.md"

    def __str__(self) -> str:
        """Return the filename value."""
        return self.value


class PromptLoader:
    """
    Generic prompt loader that loads and caches prompts from markdown files.

    Usage:
        from alita_sdk.runtime.middleware.prompt_constants import PromptLoader, PromptFile

        system_prompt = PromptLoader.get_prompt(PromptFile.ERROR_TRANSFORMATION_SYSTEM)
        user_suffix = PromptLoader.get_prompt(PromptFile.ERROR_TRANSFORMATION_USER_SUFFIX)
    """

    _prompts_dir: Optional[Path] = None
    _cache: Dict[str, str] = {}

    @classmethod
    def _get_prompts_dir(cls) -> Path:
        """Get the prompts directory path."""

        import alita_sdk
        if cls._prompts_dir is None:
            cls._prompts_dir = Path(alita_sdk.__file__).parent / "docs" / "prompts"
        return cls._prompts_dir

    @classmethod
    def get_prompt(cls, prompt_file: PromptFile) -> str:
        """
        Load prompt content from markdown file with caching.

        Args:
            prompt_file: PromptFile enum value specifying which prompt to load

        Returns:
            Prompt content as string

        Raises:
            FileNotFoundError: If prompt file doesn't exist

        Example:
            >>> system_prompt = PromptLoader.get_prompt(PromptFile.ERROR_TRANSFORMATION_SYSTEM)
            >>> print(len(system_prompt))
            1500
        """
        filename = prompt_file.value

        # Check cache first
        if filename in cls._cache:
            return cls._cache[filename]

        # Load from file
        prompts_dir = cls._get_prompts_dir()
        prompt_path = prompts_dir / filename

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}\n"
                f"Expected location: {prompts_dir}\n"
                f"Looking for: {filename}"
            )

        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        # Cache and return
        cls._cache[filename] = content
        return content

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the prompt cache. Useful for testing or hot-reloading."""
        cls._cache.clear()

    @classmethod
    def preload_all(cls) -> None:
        """Preload all prompts into cache. Optional optimization."""
        for prompt_file in PromptFile:
            cls.get_prompt(prompt_file)


# Backward compatibility: Keep TransformErrorPrompts as alias with same interface
# Prompt constants for middleware strategies
class TransformErrorPrompts:
    """
    Legacy interface for TransformErrorStrategy prompts.
    Maintained for backward compatibility.
    """

    @classmethod
    @property
    def SYSTEM_PROMPT(cls) -> str:
        """Load and cache system prompt from markdown file."""
        return PromptLoader.get_prompt(PromptFile.ERROR_TRANSFORMATION_SYSTEM)

    @classmethod
    @property
    def USER_PROMPT_SUFFIX(cls) -> str:
        """Load and cache user prompt suffix from markdown file."""
        return PromptLoader.get_prompt(PromptFile.ERROR_TRANSFORMATION_USER_SUFFIX)
