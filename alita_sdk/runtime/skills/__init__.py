"""
Skills Registry system for alita_sdk.

This package provides a comprehensive skills registry system that supports
both graph-based and agent-based skills with isolated execution and
callback support.

Key Components:
- models: Core data models and types
- discovery: Skill discovery from filesystem
- registry: Thread-safe registry service
- executor: Skill execution with isolation
- callbacks: Event system for execution transparency

Usage:
    from alita_sdk.runtime.skills import get_default_registry

    registry = get_default_registry()
    skills = registry.list()
    skill = registry.get("my_skill")

    # Execute skill through SkillRouterTool or direct execution
"""

from .models import (
    SkillMetadata,
    SkillType,
    SkillSource,
    ExecutionMode,
    SkillStatus,
    SkillEventType,
    ExecutionConfig,
    ResultsConfig,
    SkillInputSchema,
    SkillOutputSchema,
    SkillExecutionResult,
    SkillOutputFile,
    SkillEvent,
    SkillValidationError,
    SkillExecutionError
)

from .discovery import SkillDiscovery
from .registry import SkillsRegistry, get_default_registry, reset_default_registry
from .executor import SkillExecutor
from .input_builder import SkillInputBuilder
from .callbacks import (
    SkillCallback, CallbackManager, LoggingCallback, ProgressCallback,
    FileCallback, SkillLangChainCallback, CallbackEmitter,
    create_default_callbacks, create_debug_callbacks
)

__all__ = [
    # Core models
    "SkillMetadata",
    "SkillType",
    "SkillSource",
    "ExecutionMode",
    "SkillStatus",
    "SkillEventType",
    "ExecutionConfig",
    "ResultsConfig",
    "SkillInputSchema",
    "SkillOutputSchema",
    "SkillExecutionResult",
    "SkillOutputFile",
    "SkillEvent",

    # Exceptions
    "SkillValidationError",
    "SkillExecutionError",

    # Services
    "SkillDiscovery",
    "SkillsRegistry",
    "get_default_registry",
    "reset_default_registry",
    "SkillExecutor",
    "SkillInputBuilder",

    # Callbacks
    "SkillCallback",
    "CallbackManager",
    "LoggingCallback",
    "ProgressCallback",
    "FileCallback",
    "SkillLangChainCallback",
    "CallbackEmitter",
    "create_default_callbacks",
    "create_debug_callbacks"
]