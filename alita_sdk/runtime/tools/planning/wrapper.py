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
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    """A single step in a plan."""
    description: str = Field(description="Step description")
    completed: bool = Field(default=False, description="Whether step is completed")


class PlanState(BaseModel):
    """Current plan state."""
    title: str = Field(default="", description="Plan title")
    steps: List[PlanStep] = Field(default_factory=list, description="List of steps")
    status: str = Field(default="in_progress", description="Plan status")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for scoping")
    
    def render(self) -> str:
        """Render plan as formatted string with checkboxes."""
        if not self.steps:
            return "No plan created yet."
        
        lines = []
        if self.title:
            lines.append(f"📋 {self.title}")
        
        completed_count = sum(1 for s in self.steps if s.completed)
        total_count = len(self.steps)
        lines.append(f"   Progress: {completed_count}/{total_count} steps completed")
        lines.append("")
        
        for i, step in enumerate(self.steps, 1):
            checkbox = "☑" if step.completed else "☐"
            status = " ✓" if step.completed else ""
            lines.append(f"   {checkbox} {i}. {step.description}{status}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "steps": [{"description": s.description, "completed": s.completed} for s in self.steps],
            "status": self.status,
            "conversation_id": self.conversation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanState":
        """Create from dictionary."""
        steps = [PlanStep(**s) for s in data.get("steps", [])]
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
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        
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
        """
        Load plan from PostgreSQL.
        
        Uses conversation_id for scoping. Server provides conversation_id,
        CLI provides session_id as conversation_id.
        """
        from .models import AgentPlan
        
        try:
            session = self._get_session()
            
            # Use conversation_id for querying (set during initialization from server/CLI)
            query_id = self.conversation_id or conversation_id
            
            plan = session.query(AgentPlan).filter(
                AgentPlan.conversation_id == query_id
            ).first()
            
            if plan:
                steps = [
                    PlanStep(
                        description=s.get("description", ""),
                        completed=s.get("completed", False)
                    )
                    for s in plan.plan_data.get("steps", [])
                ]
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
        """
        Save plan to PostgreSQL.
        
        Uses conversation_id for scoping.
        """
        from .models import AgentPlan
        
        try:
            session = self._get_session()
            
            # Use conversation_id for querying and storing
            query_id = self.conversation_id or conversation_id
            
            existing = session.query(AgentPlan).filter(
                AgentPlan.conversation_id == query_id
            ).first()
            
            plan_data = {
                "steps": [{"description": s.description, "completed": s.completed} for s in plan.steps]
            }
            
            if existing:
                existing.title = plan.title
                existing.plan_data = plan_data
                existing.status = plan.status
                existing.updated_at = datetime.utcnow()
            else:
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
        """
        Delete plan from PostgreSQL.
        
        Uses conversation_id for scoping.
        """
        from .models import AgentPlan
        
        try:
            session = self._get_session()
            
            # Use conversation_id for querying
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
    
    Conversation ID can be:
    1. Passed explicitly to each method
    2. Set via conversation_id field (from server payload or CLI session_id)
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
        description="Optional callback function called when plan changes (for CLI UI updates)"
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
            # Use PostgreSQL storage
            try:
                storage = PostgresStorage(conn_str, self.conversation_id)
                object.__setattr__(self, '_storage', storage)
                object.__setattr__(self, '_use_postgres', True)
                logger.info("Planning toolkit using PostgreSQL storage")
            except Exception as e:
                logger.warning(f"Failed to initialize PostgreSQL storage, falling back to filesystem: {e}")
                storage = FilesystemStorage(self.storage_dir)
                object.__setattr__(self, '_storage', storage)
                object.__setattr__(self, '_use_postgres', False)
        else:
            # Use filesystem storage
            storage = FilesystemStorage(self.storage_dir)
            object.__setattr__(self, '_storage', storage)
            object.__setattr__(self, '_use_postgres', False)
            logger.info("Planning toolkit using filesystem storage")
        
        return self
    
    def run(self, action: str, *args, **kwargs) -> str:
        """Execute an action by name (called by BaseAction)."""
        # Strip toolkit prefix if present (e.g., "Plan___update_plan" -> "update_plan")
        if '___' in action:
            action = action.split('___')[-1]
        
        action_map = {
            "update_plan": self.update_plan,
            "complete_step": self.complete_step,
            "get_plan_status": self.get_plan_status,
            "delete_plan": self.delete_plan,
        }
        
        if action not in action_map:
            return f"Unknown action: {action}"
        
        return action_map[action](*args, **kwargs)
    
    def update_plan(self, title: str, steps: List[str], conversation_id: Optional[str] = None) -> str:
        """
        Create or update an execution plan.
        
        If a plan exists for the conversation_id, it will be replaced.
        
        Args:
            title: Plan title
            steps: List of step descriptions
            conversation_id: Conversation ID for scoping. Uses wrapper's conversation_id if not provided.
            
        Returns:
            Formatted plan state string
        """
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "❌ Error: conversation_id is required (from server or session_id from CLI)"
        
        try:
            plan = PlanState(
                title=title,
                steps=[PlanStep(description=s, completed=False) for s in steps],
                status="in_progress",
                conversation_id=conversation_id
            )
            
            existing = self._storage.get_plan(conversation_id)
            if self._storage.save_plan(conversation_id, plan):
                action = "updated" if existing else "created"
                
                # Notify callback if set (for CLI UI updates)
                if self.plan_callback:
                    self.plan_callback(plan)
                
                return f"✓ Plan {action}:\n\n{plan.render()}"
            else:
                return "❌ Error: Failed to save plan"
                
        except Exception as e:
            logger.error(f"Failed to update plan: {e}")
            return f"❌ Error updating plan: {str(e)}"
    
    def complete_step(self, step_number: int, conversation_id: Optional[str] = None) -> str:
        """
        Mark a step as completed.
        
        Args:
            step_number: Step number (1-indexed)
            conversation_id: Conversation ID for scoping. Uses wrapper's conversation_id if not provided.
            
        Returns:
            Updated plan state string
        """
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "❌ Error: conversation_id is required (from server or session_id from CLI)"
        
        try:
            plan = self._storage.get_plan(conversation_id)
            
            if not plan or not plan.steps:
                return "❌ No plan exists. Use update_plan first to create a plan."
            
            if step_number < 1 or step_number > len(plan.steps):
                return f"❌ Invalid step number. Plan has {len(plan.steps)} steps (1-{len(plan.steps)})."
            
            step = plan.steps[step_number - 1]
            if step.completed:
                return f"Step {step_number} was already completed.\n\n{plan.render()}"
            
            step.completed = True
            
            # Check if all steps completed
            all_completed = all(s.completed for s in plan.steps)
            if all_completed:
                plan.status = "completed"
            
            if self._storage.save_plan(conversation_id, plan):
                # Notify callback if set (for CLI UI updates)
                if self.plan_callback:
                    self.plan_callback(plan)
                
                completed = sum(1 for s in plan.steps if s.completed)
                total = len(plan.steps)
                return f"✓ Step {step_number} completed ({completed}/{total} done)\n\n{plan.render()}"
            else:
                return "❌ Error: Failed to save plan progress"
            
        except Exception as e:
            logger.error(f"Failed to complete step: {e}")
            return f"❌ Error completing step: {str(e)}"
    
    def get_plan_status(self, conversation_id: Optional[str] = None) -> str:
        """
        Get the current plan status.
        
        Args:
            conversation_id: Conversation ID for scoping. Uses wrapper's conversation_id if not provided.
            
        Returns:
            Formatted plan state or message if no plan exists
        """
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "❌ Error: conversation_id is required (from server or session_id from CLI)"
        
        try:
            plan = self._storage.get_plan(conversation_id)
            
            if not plan:
                return "No plan exists for the current conversation. Use update_plan to create one."
            
            return plan.render()
            
        except Exception as e:
            logger.error(f"Failed to get plan status: {e}")
            return f"❌ Error getting plan status: {str(e)}"
    
    def delete_plan(self, conversation_id: Optional[str] = None) -> str:
        """
        Delete the current plan.
        
        Args:
            conversation_id: Conversation ID for scoping. Uses wrapper's conversation_id if not provided.
            
        Returns:
            Confirmation message
        """
        conversation_id = conversation_id or self.conversation_id
        if not conversation_id:
            return "❌ Error: conversation_id is required (from server or session_id from CLI)"
        
        try:
            plan = self._storage.get_plan(conversation_id)
            
            if not plan:
                return "No plan exists for the current conversation."
            
            if self._storage.delete_plan(conversation_id):
                return f"✓ Plan '{plan.title}' deleted successfully."
            else:
                return "❌ Error: Failed to delete plan"
            
        except Exception as e:
            logger.error(f"Failed to delete plan: {e}")
            return f"❌ Error deleting plan: {str(e)}"
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Return list of available planning tools with their schemas.
        
        Returns:
            List of tool definitions with name, description, and args_schema
        """
        # Define input schemas for tools
        # conversation_id is optional when set on the wrapper instance
        UpdatePlanInput = create_model(
            'UpdatePlanInput',
            title=(str, Field(description="Title for the plan (e.g., 'Test Investigation Plan')")),
            steps=(List[str], Field(description="List of step descriptions in order")),
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional - uses default if not provided)"))
        )
        
        CompleteStepInput = create_model(
            'CompleteStepInput',
            step_number=(int, Field(description="Step number to mark as complete (1-indexed)")),
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional - uses default if not provided)"))
        )
        
        GetPlanStatusInput = create_model(
            'GetPlanStatusInput',
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional - uses default if not provided)"))
        )
        
        DeletePlanInput = create_model(
            'DeletePlanInput',
            conversation_id=(Optional[str], Field(default=None, description="Conversation ID (optional - uses default if not provided)"))
        )
        
        return [
            {
                "name": "update_plan",
                "description": """Create or replace the current execution plan.

Use this when:
- Starting a multi-step task that needs tracking
- The sequence of activities matters
- Breaking down a complex task into phases

The plan will be displayed and you can mark steps complete as you progress.

Example:
    update_plan(
        title="API Test Investigation",
        steps=[
            "Reproduce the failing test locally",
            "Capture error logs and stack trace", 
            "Identify root cause",
            "Apply fix",
            "Re-run test suite"
        ]
    )""",
                "args_schema": UpdatePlanInput
            },
            {
                "name": "complete_step",
                "description": """Mark a step in the current plan as completed.

Use this after finishing a step to update progress.
Step numbers are 1-indexed (first step is 1, not 0).

Example:
    complete_step(step_number=1)  # Mark first step as done""",
                "args_schema": CompleteStepInput
            },
            {
                "name": "get_plan_status",
                "description": """Get the current plan status and progress.

Shows the plan title, all steps with completion status, and overall progress.
Use this to review what needs to be done or verify progress.""",
                "args_schema": GetPlanStatusInput
            },
            {
                "name": "delete_plan",
                "description": """Delete the current plan.

Use this when:
- The plan is complete and no longer needed
- You want to start fresh with a new plan
- The current plan is no longer relevant""",
                "args_schema": DeletePlanInput
            }
        ]


# Import create_model for get_available_tools
from pydantic import create_model
