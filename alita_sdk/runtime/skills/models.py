"""
Core data models for the Skills Registry system.

This module defines the data structures used throughout the skills system,
including skill metadata, execution configuration, and result formats.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillType(str, Enum):
    """Skill execution architecture type."""
    GRAPH = "graph"
    AGENT = "agent"
    PIPELINE = "pipeline"


class SkillSource(str, Enum):
    """Source type for skill definitions."""
    FILESYSTEM = "filesystem"  # Local agent.md files
    PLATFORM = "platform"     # Platform-hosted agents/pipelines


class ExecutionMode(str, Enum):
    """Skill execution isolation mode."""
    SUBPROCESS = "subprocess"
    REMOTE = "remote"


class SkillStatus(str, Enum):
    """Skill execution status."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RUNNING = "running"
    PENDING = "pending"


class SkillEventType(str, Enum):
    """Callback event types for skill execution."""
    SKILL_START = "skill_start"
    SKILL_END = "skill_end"
    NODE_START = "node_start"
    NODE_END = "node_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    LLM_START = "llm_start"
    LLM_END = "llm_end"
    ERROR = "error"
    PROGRESS = "progress"
    CUSTOM_EVENT = "custom_event"


class ExecutionConfig(BaseModel):
    """Configuration for skill execution."""

    mode: ExecutionMode = ExecutionMode.SUBPROCESS
    timeout: int = Field(default=300, description="Execution timeout in seconds")
    working_directory: Optional[str] = Field(
        default=None,
        description="Working directory for skill execution"
    )
    environment: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for skill execution"
    )
    max_retries: int = Field(default=0, description="Maximum retry attempts")

    class Config:
        use_enum_values = True


class ResultsConfig(BaseModel):
    """Configuration for skill result handling."""

    format: Literal["text_with_links"] = "text_with_links"
    output_files: List[str] = Field(
        default_factory=list,
        description="Expected output file patterns"
    )
    cleanup_policy: Literal["preserve", "cleanup"] = Field(
        default="preserve",
        description="Policy for cleaning up working directory"
    )

    class Config:
        use_enum_values = True


class SkillInputSchema(BaseModel):
    """Schema definition for skill inputs."""

    # Common fields
    description: Optional[str] = None

    # Agent-specific inputs
    variables: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Variable definitions for agent skills"
    )
    chat_history: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Chat history schema for agent skills"
    )
    user_input: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User input schema for agent skills"
    )

    # Graph-specific inputs
    state_variables: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="State variable definitions for graph skills"
    )


class SkillOutputSchema(BaseModel):
    """Schema definition for skill outputs."""

    primary_output: Dict[str, Any] = Field(
        default={"type": "text", "description": "Main result text"},
        description="Primary text output schema"
    )
    generated_files: Dict[str, Any] = Field(
        default={"type": "list[file_reference]", "description": "Created files"},
        description="File references schema"
    )
    additional_outputs: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Additional skill-specific outputs"
    )


class SkillMetadata(BaseModel):
    """Complete metadata for a skill definition."""

    # Core identification
    name: str = Field(description="Unique skill identifier")
    skill_type: SkillType = Field(description="Skill architecture type")
    source: SkillSource = Field(description="Source type for skill definition")

    # Filesystem-based skill fields
    path: Optional[str] = Field(
        default=None,
        description="Directory path containing agent.md (for filesystem skills)"
    )

    # Platform-based skill fields
    id: Optional[int] = Field(
        default=None,
        description="Platform ID (for platform-hosted skills)"
    )
    version_id: Optional[int] = Field(
        default=None,
        description="Platform version ID (for platform-hosted skills)"
    )

    # Descriptive metadata
    description: str = Field(description="Human-readable skill description")
    capabilities: List[str] = Field(
        default_factory=list,
        description="List of capabilities this skill provides"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization and filtering"
    )
    version: str = Field(default="1.0.0", description="Skill version")

    # Configuration
    execution: ExecutionConfig = Field(description="Execution configuration")
    results: ResultsConfig = Field(description="Result handling configuration")

    # Input/Output schemas
    inputs: SkillInputSchema = Field(description="Input schema definition")
    outputs: SkillOutputSchema = Field(description="Output schema definition")

    # Type-specific configurations
    # Graph-specific fields
    state_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="State schema for graph skills"
    )
    nodes: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Node definitions for graph skills"
    )
    graph_yaml: Optional[str] = Field(
        default=None,
        description="Complete YAML definition for graph skills"
    )

    # Agent-specific fields
    system_prompt: Optional[str] = Field(
        default=None,
        description="System prompt for agent skills"
    )
    agent_type: Optional[str] = Field(
        default=None,
        description="Agent architecture type (react, xml, etc.)"
    )
    toolkits: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Toolkit configurations for agent skills"
    )

    # LLM configuration
    model: Optional[str] = Field(default=None, description="Default LLM model")
    temperature: Optional[float] = Field(default=None, description="LLM temperature")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens")

    class Config:
        use_enum_values = True


class SkillOutputFile(BaseModel):
    """Reference to a file generated by skill execution."""

    path: Path = Field(description="Path to the generated file")
    description: str = Field(description="Human-readable file description")
    file_type: str = Field(description="File type (json, markdown, csv, etc.)")
    size_bytes: int = Field(description="File size in bytes")

    def __str__(self) -> str:
        """Format for LLM consumption."""
        size_kb = self.size_bytes / 1024
        if size_kb < 1:
            size_str = f"{self.size_bytes} bytes"
        else:
            size_str = f"{size_kb:.1f}KB"

        return f"[{self.description}]({self.path}) ({self.file_type}, {size_str})"


class SkillExecutionResult(BaseModel):
    """Result of skill execution with text output and file references."""

    # Execution metadata
    skill_name: str = Field(description="Name of executed skill")
    skill_type: SkillType = Field(description="Type of skill executed")
    status: SkillStatus = Field(description="Execution status")
    execution_mode: ExecutionMode = Field(description="Execution mode used")
    execution_id: str = Field(description="Unique execution identifier")

    # Results
    output_text: str = Field(description="Primary text output for LLM consumption")
    output_files: List[SkillOutputFile] = Field(
        default_factory=list,
        description="Generated files with descriptions"
    )

    # Execution details
    duration: float = Field(description="Execution duration in seconds")
    working_directory: Optional[Path] = Field(
        default=None,
        description="Working directory used for execution"
    )

    # Error information
    error_details: Optional[str] = Field(
        default=None,
        description="Error details if status is ERROR"
    )

    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata"
    )

    class Config:
        use_enum_values = True

    def format_for_llm(self) -> str:
        """Format result as text suitable for LLM consumption."""
        result = self.output_text

        if self.output_files:
            result += "\n\n**Generated Files:**\n"
            for file in self.output_files:
                result += f"- {file}\n"

        if self.status == SkillStatus.ERROR and self.error_details:
            result += f"\n\n**Error:** {self.error_details}"

        return result


@dataclass
class SkillEvent:
    """Event emitted during skill execution."""

    event_type: SkillEventType
    data: Dict[str, Any]
    skill_name: str
    execution_id: str
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "skill_name": self.skill_name,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp
        }


class SkillDiscoveryError(Exception):
    """Exception raised during skill discovery."""
    pass


class SkillValidationError(Exception):
    """Exception raised during skill validation."""
    pass


class SkillExecutionError(Exception):
    """Exception raised during skill execution."""
    pass