"""
SQLAlchemy models for agent planning.

Defines the AgentPlan table for storing execution plans with steps.
Table is created automatically on toolkit initialization if it doesn't exist.
"""

import enum
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Text, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError

logger = logging.getLogger(__name__)

Base = declarative_base()


class PlanStatus(str, enum.Enum):
    """Status of an execution plan."""
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class AgentPlan(Base):
    """
    Stores execution plans for agent tasks.
    
    Created in the project-specific pgvector database.
    Plans are scoped by conversation_id (from server or CLI session_id).
    """
    __tablename__ = "agent_plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(String(255), nullable=False, index=True)
    
    # Plan metadata
    title = Column(String(255), nullable=True)
    status = Column(String(50), default=PlanStatus.in_progress.value)
    
    # Plan content (JSONB for flexible step storage)
    # Structure: {"steps": [{"description": "...", "completed": false}, ...]}
    plan_data = Column(JSONB, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)


# Pydantic models for tool input/output
class PlanStep(BaseModel):
    """A single step in a plan."""
    description: str = Field(description="Step description")
    completed: bool = Field(default=False, description="Whether step is completed")


class PlanState(BaseModel):
    """Current plan state for serialization."""
    title: str = Field(default="", description="Plan title")
    steps: List[PlanStep] = Field(default_factory=list, description="List of steps")
    status: str = Field(default=PlanStatus.in_progress.value, description="Plan status")
    
    def render(self) -> str:
        """Render plan as formatted string with checkboxes."""
        if not self.steps:
            return "No plan currently set."
        
        lines = []
        if self.title:
            lines.append(f"📋 {self.title}")
        
        completed_count = 0
        for i, step in enumerate(self.steps, 1):
            checkbox = "☑" if step.completed else "☐"
            status_text = " (completed)" if step.completed else ""
            lines.append(f"   {checkbox} {i}. {step.description}{status_text}")
            if step.completed:
                completed_count += 1
        
        lines.append(f"\nProgress: {completed_count}/{len(self.steps)} steps completed")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSONB storage."""
        return {
            "steps": [{"description": s.description, "completed": s.completed} for s in self.steps]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], title: str = "", status: str = PlanStatus.in_progress.value) -> "PlanState":
        """Create from dictionary (JSONB data)."""
        steps_data = data.get("steps", [])
        steps = [PlanStep(**s) if isinstance(s, dict) else s for s in steps_data]
        return cls(title=title, steps=steps, status=status)


def ensure_plan_tables(connection_string: str) -> bool:
    """
    Ensure the agent_plans table exists in the database.
    
    Creates the table if it doesn't exist. Safe to call multiple times.
    
    Args:
        connection_string: PostgreSQL connection string
        
    Returns:
        True if table was created or already exists, False on error
    """
    try:
        # Handle SecretStr if passed
        if hasattr(connection_string, 'get_secret_value'):
            connection_string = connection_string.get_secret_value()
        
        if not connection_string:
            logger.warning("No connection string provided for plan tables")
            return False
            
        engine = create_engine(connection_string)
        
        # Create tables if they don't exist
        Base.metadata.create_all(engine, checkfirst=True)
        
        logger.debug("Agent plans table ensured")
        return True
        
    except Exception as e:
        logger.error(f"Failed to ensure plan tables: {e}")
        return False


def delete_plan_by_conversation_id(connection_string: str, conversation_id: str) -> bool:
    """
    Delete a plan by conversation_id.
    
    Args:
        connection_string: PostgreSQL connection string
        conversation_id: The conversation ID to delete plans for
        
    Returns:
        True if deletion successful, False otherwise
    """
    try:
        if hasattr(connection_string, 'get_secret_value'):
            connection_string = connection_string.get_secret_value()
            
        if not connection_string or not conversation_id:
            return False
            
        engine = create_engine(connection_string)
        
        with engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM agent_plans WHERE conversation_id = :conversation_id"),
                {"conversation_id": conversation_id}
            )
            conn.commit()
            
        logger.debug(f"Deleted plan for conversation_id: {conversation_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete plan for conversation_id {conversation_id}: {e}")
        return False


def cleanup_on_graceful_completion(
    connection_string: str, 
    conversation_id: str,
    thread_id: str = None,
    delete_checkpoints: bool = True
) -> dict:
    """
    Cleanup plans and optionally checkpoints after graceful agent completion.
    
    This function is designed to be called after an agent completes successfully
    (no exceptions, valid finish reason).
    
    Args:
        connection_string: PostgreSQL connection string
        conversation_id: The conversation ID to cleanup plans for
        thread_id: The thread ID to cleanup checkpoints for (optional)
        delete_checkpoints: If True, also delete checkpoint data
        
    Returns:
        Dict with cleanup results: {'plan_deleted': bool, 'checkpoints_deleted': bool}
    """
    result = {'plan_deleted': False, 'checkpoints_deleted': False}
    
    try:
        if hasattr(connection_string, 'get_secret_value'):
            connection_string = connection_string.get_secret_value()
            
        if not connection_string or not conversation_id:
            logger.warning("Missing connection_string or conversation_id for cleanup")
            return result
        
        engine = create_engine(connection_string)
        
        with engine.connect() as conn:
            # Delete plan by conversation_id
            try:
                conn.execute(
                    text("DELETE FROM agent_plans WHERE conversation_id = :conversation_id"),
                    {"conversation_id": conversation_id}
                )
                result['plan_deleted'] = True
                logger.debug(f"Deleted plan for conversation_id: {conversation_id}")
            except Exception as e:
                # Table might not exist, which is fine
                logger.debug(f"Could not delete plan (table may not exist): {e}")
            
            # Delete checkpoints if requested (still uses thread_id as that's LangGraph's key)
            if delete_checkpoints and thread_id:
                checkpoint_tables = [
                    "checkpoints",
                    "checkpoint_writes", 
                    "checkpoint_blobs"
                ]
                
                for table in checkpoint_tables:
                    try:
                        conn.execute(
                            text(f"DELETE FROM {table} WHERE thread_id = :thread_id"),
                            {"thread_id": thread_id}
                        )
                        logger.debug(f"Deleted {table} for thread_id: {thread_id}")
                    except Exception as e:
                        logger.debug(f"Could not delete from {table}: {e}")
                
                result['checkpoints_deleted'] = True
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"Failed to cleanup for conversation_id {conversation_id}: {e}")
    
    return result
