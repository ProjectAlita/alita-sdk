"""
PlanningWrapper - Adaptive API wrapper for plan CRUD operations.

Supports two storage backends:
1. PostgreSQL - when connection_string is provided (production/indexer_worker)
2. Filesystem - when no connection string (local CLI usage)

Plans are scoped by conversation_id (from server) or session_id (from CLI).
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator, create_model

logger = logging.getLogger(__name__)


class StepStatus:
    """Step status constants."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class PlanStep(BaseModel):
    """A single step in a plan with 3-state status tracking."""
    description: str = Field(description="Step description")
    status: str = Field(default=StepStatus.PENDING, description="Step status: pending, in_progress, or completed")

    @property
    def completed(self) -> bool:
        """Backward compatibility: check if step is completed."""
        return self.status == StepStatus.COMPLETED

    @property
    def in_progress(self) -> bool:
        """Check if step is currently in progress."""
        return self.status == StepStatus.IN_PROGRESS

    @property
    def pending(self) -> bool:
        """Check if step is pending."""
        return self.status == StepStatus.PENDING


class PlanState(BaseModel):
    """Current plan state."""
    title: str = Field(default="", description="Plan title")
    steps: List[PlanStep] = Field(default_factory=list, description="List of steps")
    status: str = Field(default="in_progress", description="Plan status")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for scoping")

    def render(self) -> str:
        """Render plan as formatted string with status indicators."""
        if not self.steps:
            return "No plan created yet."

        lines = []
        if self.title:
            lines.append(f"📋 {self.title}")

        completed_count = sum(1 for s in self.steps if s.completed)
        in_progress_count = sum(1 for s in self.steps if s.in_progress)
        total_count = len(self.steps)
        lines.append(f"   Progress: {completed_count}/{total_count} completed, {in_progress_count} in progress")
        lines.append("")

        for i, step in enumerate(self.steps, 1):
            if step.completed:
                indicator = "☑"
                suffix = " ✓"
            elif step.in_progress:
                indicator = "▶"
                suffix = " (in progress)"
            else:
                indicator = "☐"
                suffix = ""
            lines.append(f"   {indicator} {i}. {step.description}{suffix}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "steps": [{"description": s.description, "status": s.status} for s in self.steps],
            "status": self.status,
            "conversation_id": self.conversation_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanState":
        """Create from dictionary with backward compatibility for old 'completed' field."""
        steps = []
        for s in data.get("steps", []):
            if "status" in s:
                # New format with status field
                steps.append(PlanStep(description=s["description"], status=s["status"]))
            elif "completed" in s:
                # Old format with completed bool - convert to status
                status = StepStatus.COMPLETED if s["completed"] else StepStatus.PENDING
                steps.append(PlanStep(description=s["description"], status=status))
            else:
                # Minimal format - just description
                steps.append(PlanStep(description=s.get("description", "")))

        return cls(
            title=data.get("title", ""),
            steps=steps,
            status=data.get("status", "in_progress"),
            conversation_id=data.get("conversation_id")
        )


class FilesystemStorage:
    """Filesystem-based plan storage for local CLI usage."""

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize filesystem storage.

        Args:
            base_dir: Base directory for plan storage.
                     Defaults to $ALITA_DIR/plans or .alita/plans
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            alita_dir = os.environ.get('ALITA_DIR', '.alita')
            self.base_dir = Path(alita_dir) / 'plans'

        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Filesystem storage initialized at {self.base_dir}")

    def _get_plan_path(self, conversation_id: str) -> Path:
        """Get the path to a plan file."""
        # Sanitize conversation_id for filesystem
        safe_id = conversation_id.replace('/', '_').replace('\\', '_')
        return self.base_dir / f"{safe_id}.json"

    def get_plan(self, conversation_id: str) -> Optional[PlanState]:
        """Load plan from filesystem."""
        plan_path = self._get_plan_path(conversation_id)
        if plan_path.exists():
            try:
                data = json.loads(plan_path.read_text())
                return PlanState.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load plan from {plan_path}: {e}")
        return None

    def save_plan(self, conversation_id: str, plan: PlanState) -> bool:
        """Save plan to filesystem."""
        try:
            plan_path = self._get_plan_path(conversation_id)
            plan.conversation_id = conversation_id
            plan_path.write_text(json.dumps(plan.to_dict(), indent=2))
            logger.debug(f"Saved plan to {plan_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save plan: {e}")
            return False

    def delete_plan(self, conversation_id: str) -> bool:
        """Delete plan from filesystem."""
        try:
            plan_path = self._get_plan_path(conversation_id)
            if plan_path.exists():
                plan_path.unlink()
                logger.debug(f"Deleted plan at {plan_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete plan: {e}")
            return False


class PostgresStorage:
    """PostgreSQL-based plan storage for production usage."""

    def __init__(self, connection_string: str, conversation_id: Optional[str] = None):
        """
        Initialize PostgreSQL storage.

        Args:
            connection_string: PostgreSQL connection string
            conversation_id: Conversation ID for scoping plans (from server or CLI session_id)
        """
        self.connection_string = connection_string
        self.conversation_id = conversation_id
        self._engine = None
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure the agent_plans table exists."""
        from .models import ensure_plan_tables
        ensure_plan_tables(self.connection_string)

    def _get_engine(self):
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            self._engine = create_engine(self.connection_string)
        return self._engine

    def _get_session(self):
        """Get a database session."""
        from sqlalchemy.orm import Session
        return Session(self._get_engine())

    def get_plan(self, conversation_id: str) -> Optional[PlanState]:
        """Load plan from PostgreSQL."""
        from .models import AgentPlan

        try:
            session = self._get_session()
            query_id = self.conversation_id or conversation_id

            plan = session.query(AgentPlan).filter(
                AgentPlan.conversation_id == query_id
            ).first()

            if plan:
                steps = []
                for s in plan.plan_data.get("steps", []):
                    if "status" in s:
                        steps.append(PlanStep(description=s.get("description", ""), status=s["status"]))
                    elif "completed" in s:
                        status = StepStatus.COMPLETED if s["completed"] else StepStatus.PENDING
                        steps.append(PlanStep(description=s.get("description", ""), status=status))
                    else:
                        steps.append(PlanStep(description=s.get("description", "")))
                result = PlanState(
                    title=plan.title,
                    steps=steps,
                    status=plan.status,
                    conversation_id=query_id
                )
                session.close()
                return result

            session.close()
            return None

        except Exception as e:
            logger.error(f"Failed to load plan from database: {e}")
            return None

    def save_plan(self, conversation_id: str, plan: PlanState) -> bool:
        """Save plan to PostgreSQL."""
        from .models import AgentPlan

        try:
            session = self._get_session()
            query_id = self.conversation_id or conversation_id

            existing = session.query(AgentPlan).filter(
                AgentPlan.conversation_id == query_id
            ).first()

            plan_data = {
                "steps": [{"description": s.description, "status": s.status} for s in plan.steps]
            }

            if existing:
                existing.title = plan.title
                existing.plan_data = plan_data
                existing.status = plan.status
                existing.updated_at = datetime.utcnow()
            else:
                from .models import AgentPlan
                new_plan = AgentPlan(
                    conversation_id=query_id,
                    title=plan.title,
                    plan_data=plan_data,
                    status=plan.status
                )
                session.add(new_plan)

            session.commit()
            session.close()
            return True

        except Exception as e:
            logger.error(f"Failed to save plan to database: {e}")
            return False

    def delete_plan(self, conversation_id: str) -> bool:
        """Delete plan from PostgreSQL."""
        from .models import AgentPlan

        try:
            session = self._get_session()
            query_id = self.conversation_id or conversation_id

            session.query(AgentPlan).filter(
                AgentPlan.conversation_id == query_id
            ).delete()
            session.commit()
            session.close()
            return True

        except Exception as e:
            logger.error(f"Failed to delete plan from database: {e}")
            return False


class PlanningWrapper(BaseModel):
    """
    Adaptive wrapper for plan management operations.

    Automatically selects storage backend:
    - PostgreSQL when connection_string is provided
    - Filesystem when no connection_string (local usage)
    """
    connection_string: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection string. If not provided, uses filesystem storage."
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation ID for scoping"
    )
    storage_dir: Optional[str] = Field(
        default=None,
        description="Directory for filesystem storage (when no connection_string)"
    )
    plan_callback: Optional[Any] = Field(
        default=None,
        description="Optional callback function called when plan changes"
    )

    # Runtime state
    _storage: Any = None
    _use_postgres: bool = False

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='after')
    def setup_storage(self):
        """Initialize the appropriate storage backend."""
        conn_str = self.connection_string
        if hasattr(conn_str, 'get_secret_value'):
            conn_str = conn_str.get_secret_value()

        if conn_str:
            try:
                storage = PostgresStorage(conn_str, self.conversation_id)
                object.__setattr__(self, '_storage', storage)
                object.__setattr__(self, '_use_postgres', True)
                logger.info("Planning middleware using PostgreSQL storage")
            except Exception as e:
                logger.warning(f"Failed to initialize PostgreSQL storage, falling back to filesystem: {e}")
                storage = FilesystemStorage(self.storage_dir)
                object.__setattr__(self, '_storage', storage)
                object.__setattr__(self, '_use_postgres', False)
        else:
            storage = FilesystemStorage(self.storage_dir)
            object.__setattr__(self, '_storage', storage)
            object.__setattr__(self, '_use_postgres', False)
            logger.info("Planning middleware using filesystem storage")

        return self

    def run(self, action: str, *args, **kwargs) -> str:
        """Execute an action by name (called by BaseAction)."""
        if '___' in action:
            action = action.split('___')[-1]

        action_map = {
            "update_plan": self.update_plan,
            "start_step": self.start_step,
            "complete_step": self.complete_step,
            "get_plan_status": self.get_plan_status,
            "delete_plan": self.delete_plan,
        }

        if action not in action_map:
            return f"Unknown action: {action}"

        return action_map[action](*args, **kwargs)

    def update_plan(self, title: str, steps: List[str], conversation_id: Optional[str] = None) -> str:
        """Create or update an execution plan."""
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "Error: conversation_id is required"

        try:
            plan = PlanState(
                title=title,
                steps=[PlanStep(description=s) for s in steps],
                status="in_progress",
                conversation_id=conversation_id
            )

            existing = self._storage.get_plan(conversation_id)
            if self._storage.save_plan(conversation_id, plan):
                action = "updated" if existing else "created"
                if self.plan_callback:
                    self.plan_callback(plan)
                return f"Plan {action}:\n\n{plan.render()}"
            else:
                return "Error: Failed to save plan"

        except Exception as e:
            logger.error(f"Failed to update plan: {e}")
            return f"Error updating plan: {str(e)}"

    def start_step(self, step_number: int, conversation_id: Optional[str] = None) -> str:
        """Mark a step as in progress."""
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "Error: conversation_id is required"

        try:
            plan = self._storage.get_plan(conversation_id)

            if not plan or not plan.steps:
                return "No plan exists. Use update_plan first to create a plan."

            if step_number < 1 or step_number > len(plan.steps):
                return f"Invalid step number. Plan has {len(plan.steps)} steps (1-{len(plan.steps)})."

            step = plan.steps[step_number - 1]
            if step.completed:
                return f"Step {step_number} is already completed.\n\n{plan.render()}"

            if step.in_progress:
                return f"Step {step_number} is already in progress.\n\n{plan.render()}"

            # Clear any other in-progress steps
            for s in plan.steps:
                if s.in_progress:
                    s.status = StepStatus.PENDING

            step.status = StepStatus.IN_PROGRESS

            if self._storage.save_plan(conversation_id, plan):
                if self.plan_callback:
                    self.plan_callback(plan)
                return f"Started step {step_number}: {step.description}\n\n{plan.render()}"
            else:
                return "Error: Failed to save plan progress"

        except Exception as e:
            logger.error(f"Failed to start step: {e}")
            return f"Error starting step: {str(e)}"

    def complete_step(self, step_number: int, conversation_id: Optional[str] = None) -> str:
        """Mark a step as completed."""
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "Error: conversation_id is required"

        try:
            plan = self._storage.get_plan(conversation_id)

            if not plan or not plan.steps:
                return "No plan exists. Use update_plan first to create a plan."

            if step_number < 1 or step_number > len(plan.steps):
                return f"Invalid step number. Plan has {len(plan.steps)} steps (1-{len(plan.steps)})."

            step = plan.steps[step_number - 1]
            if step.completed:
                return f"Step {step_number} was already completed.\n\n{plan.render()}"

            step.status = StepStatus.COMPLETED

            all_completed = all(s.completed for s in plan.steps)
            if all_completed:
                plan.status = "completed"

            if self._storage.save_plan(conversation_id, plan):
                if self.plan_callback:
                    self.plan_callback(plan)
                completed = sum(1 for s in plan.steps if s.completed)
                total = len(plan.steps)
                return f"Step {step_number} completed ({completed}/{total} done)\n\n{plan.render()}"
            else:
                return "Error: Failed to save plan progress"

        except Exception as e:
            logger.error(f"Failed to complete step: {e}")
            return f"Error completing step: {str(e)}"

    def get_plan_status(self, conversation_id: Optional[str] = None) -> str:
        """Get the current plan status."""
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "Error: conversation_id is required"

        try:
            plan = self._storage.get_plan(conversation_id)
            if not plan:
                return "No plan exists for the current conversation."
            return plan.render()
        except Exception as e:
            logger.error(f"Failed to get plan status: {e}")
            return f"Error getting plan status: {str(e)}"

    def delete_plan(self, conversation_id: Optional[str] = None) -> str:
        """Delete the current plan."""
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "Error: conversation_id is required"

        try:
            plan = self._storage.get_plan(conversation_id)
            if not plan:
                return "No plan exists for the current conversation."

            if self._storage.delete_plan(conversation_id):
                return f"Plan '{plan.title}' deleted successfully."
            else:
                return "Error: Failed to delete plan"

        except Exception as e:
            logger.error(f"Failed to delete plan: {e}")
            return f"Error deleting plan: {str(e)}"

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Return list of available planning tools with their schemas."""
        UpdatePlanInput = create_model(
            'UpdatePlanInput',
            title=(str, Field(description="Title for the plan")),
            steps=(List[str], Field(description="List of step descriptions in order")),
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional)"))
        )

        StartStepInput = create_model(
            'StartStepInput',
            step_number=(int, Field(description="Step number to start (1-indexed)")),
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional)"))
        )

        CompleteStepInput = create_model(
            'CompleteStepInput',
            step_number=(int, Field(description="Step number to complete (1-indexed)")),
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional)"))
        )

        GetPlanStatusInput = create_model(
            'GetPlanStatusInput',
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional)"))
        )

        DeletePlanInput = create_model(
            'DeletePlanInput',
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional)"))
        )

        return [
            {
                "name": "update_plan",
                "description": "Create or replace the current execution plan with a title and list of steps.",
                "args_schema": UpdatePlanInput
            },
            {
                "name": "start_step",
                "description": "Mark a step as in progress. Only one step can be in progress at a time.",
                "args_schema": StartStepInput
            },
            {
                "name": "complete_step",
                "description": "Mark a step as completed.",
                "args_schema": CompleteStepInput
            },
            {
                "name": "get_plan_status",
                "description": "Get the current plan status and progress.",
                "args_schema": GetPlanStatusInput
            },
            {
                "name": "delete_plan",
                "description": "Delete the current plan.",
                "args_schema": DeletePlanInput
            }
        ]
