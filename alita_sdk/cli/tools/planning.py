"""
Planning tools for CLI agents.

Provides plan management for multi-step task execution with progress tracking.
Sessions are persisted to $ALITA_DIR/sessions/<session_id>/
- plan.json: Execution plan with steps
- memory.db: SQLite database for conversation memory
- session.json: Session metadata (agent, model, etc.)
"""

import os
import json
import uuid
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


def get_sessions_dir() -> Path:
    """Get the sessions directory path."""
    alita_dir = os.environ.get('ALITA_DIR', os.path.expanduser('~/.alita'))
    return Path(alita_dir) / 'sessions'


def generate_session_id() -> str:
    """Generate a new unique session ID."""
    return uuid.uuid4().hex[:12]


def get_session_dir(session_id: str) -> Path:
    """Get the directory for a specific session."""
    return get_sessions_dir() / session_id


def get_session_memory_path(session_id: str) -> Path:
    """Get the path to the memory database for a session."""
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / "memory.db"


def get_session_metadata_path(session_id: str) -> Path:
    """Get the path to the session metadata file."""
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / "session.json"


def create_session_memory(session_id: str):
    """
    Create a SQLite-based memory saver for the session.
    
    Args:
        session_id: The session ID
        
    Returns:
        SqliteSaver instance connected to the session's memory.db
    """
    from langgraph.checkpoint.sqlite import SqliteSaver
    
    memory_path = get_session_memory_path(session_id)
    conn = sqlite3.connect(str(memory_path), check_same_thread=False)
    logger.debug(f"Created session memory at {memory_path}")
    return SqliteSaver(conn)


def save_session_metadata(session_id: str, metadata: Dict[str, Any]) -> None:
    """
    Save session metadata (agent name, model, etc.).
    
    Args:
        session_id: The session ID
        metadata: Dictionary with session metadata
    """
    metadata_path = get_session_metadata_path(session_id)
    metadata['session_id'] = session_id
    metadata_path.write_text(json.dumps(metadata, indent=2))
    logger.debug(f"Saved session metadata to {metadata_path}")


def load_session_metadata(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Load session metadata.
    
    Args:
        session_id: The session ID
        
    Returns:
        Session metadata dict or None if not found
    """
    metadata_path = get_session_metadata_path(session_id)
    if metadata_path.exists():
        try:
            return json.loads(metadata_path.read_text())
        except Exception as e:
            logger.warning(f"Failed to load session metadata: {e}")
    return None


class PlanStep(BaseModel):
    """A single step in a plan."""
    description: str = Field(description="Step description")
    completed: bool = Field(default=False, description="Whether step is completed")


class PlanState(BaseModel):
    """Current plan state."""
    title: str = Field(default="", description="Plan title")
    steps: List[PlanStep] = Field(default_factory=list, description="List of steps")
    session_id: str = Field(default="", description="Session ID for persistence")
    
    def render(self) -> str:
        """Render plan as formatted string with checkboxes."""
        if not self.steps:
            return ""
        
        lines = []
        if self.title:
            lines.append(f"📋 {self.title}")
        
        for i, step in enumerate(self.steps, 1):
            checkbox = "☑" if step.completed else "☐"
            status = " (completed)" if step.completed else ""
            lines.append(f"   {checkbox} {i}. {step.description}{status}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "steps": [{"description": s.description, "completed": s.completed} for s in self.steps],
            "session_id": self.session_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanState":
        """Create from dictionary."""
        steps = [PlanStep(**s) for s in data.get("steps", [])]
        return cls(
            title=data.get("title", ""), 
            steps=steps,
            session_id=data.get("session_id", "")
        )
    
    def save(self) -> Optional[Path]:
        """Save plan state to session file."""
        if not self.session_id:
            return None
        
        try:
            session_dir = get_sessions_dir() / self.session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            
            plan_file = session_dir / "plan.json"
            plan_file.write_text(json.dumps(self.to_dict(), indent=2))
            logger.debug(f"Saved plan to {plan_file}")
            return plan_file
        except Exception as e:
            logger.warning(f"Failed to save plan: {e}")
            return None
    
    @classmethod
    def load(cls, session_id: str) -> Optional["PlanState"]:
        """Load plan state from session file."""
        try:
            plan_file = get_sessions_dir() / session_id / "plan.json"
            if plan_file.exists():
                data = json.loads(plan_file.read_text())
                state = cls.from_dict(data)
                state.session_id = session_id
                logger.debug(f"Loaded plan from {plan_file}")
                return state
        except Exception as e:
            logger.warning(f"Failed to load plan: {e}")
        return None


def list_sessions() -> List[Dict[str, Any]]:
    """List all sessions with their metadata and plans."""
    sessions = []
    sessions_dir = get_sessions_dir()
    
    if not sessions_dir.exists():
        return sessions
    
    for session_dir in sessions_dir.iterdir():
        if session_dir.is_dir():
            session_info = {
                "session_id": session_dir.name,
                "title": None,
                "steps_total": 0,
                "steps_completed": 0,
                "agent_name": None,
                "model": None,
                "modified": 0,
                "has_memory": False,
                "has_plan": False,
            }
            
            # Load session metadata
            metadata_file = session_dir / "session.json"
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text())
                    session_info["agent_name"] = metadata.get("agent_name")
                    session_info["model"] = metadata.get("model")
                    session_info["modified"] = metadata_file.stat().st_mtime
                except Exception:
                    pass
            
            # Check for memory database
            memory_file = session_dir / "memory.db"
            if memory_file.exists():
                session_info["has_memory"] = True
                # Use memory file mtime if newer
                mem_mtime = memory_file.stat().st_mtime
                if mem_mtime > session_info["modified"]:
                    session_info["modified"] = mem_mtime
            
            # Load plan info
            plan_file = session_dir / "plan.json"
            if plan_file.exists():
                try:
                    data = json.loads(plan_file.read_text())
                    session_info["has_plan"] = True
                    session_info["title"] = data.get("title", "(untitled)")
                    session_info["steps_total"] = len(data.get("steps", []))
                    session_info["steps_completed"] = sum(1 for s in data.get("steps", []) if s.get("completed"))
                    # Use plan file mtime if newer
                    plan_mtime = plan_file.stat().st_mtime
                    if plan_mtime > session_info["modified"]:
                        session_info["modified"] = plan_mtime
                except Exception:
                    pass
            
            # Only include sessions that have some content
            if session_info["has_memory"] or session_info["has_plan"]:
                sessions.append(session_info)
    
    # Sort by modified time, newest first
    sessions.sort(key=lambda x: x.get("modified", 0), reverse=True)
    return sessions


class UpdatePlanInput(BaseModel):
    """Input for updating the plan."""
    title: str = Field(description="Title for the plan (e.g., 'Test Investigation Plan')")
    steps: List[str] = Field(description="List of step descriptions in order")


class CompleteStepInput(BaseModel):
    """Input for marking a step as complete."""
    step_number: int = Field(description="Step number to mark as complete (1-indexed)")


class UpdatePlanTool(BaseTool):
    """Create or update the execution plan."""
    
    name: str = "update_plan"
    description: str = """Create or replace the current execution plan.
    
Use this when:
- Starting a multi-step task that needs tracking
- The sequence of activities matters
- Breaking down a complex task into phases

The plan will be displayed to the user and you can mark steps complete as you progress.
Plans are automatically saved and can be resumed in future sessions.

Example:
    update_plan(
        title="API Test Investigation",
        steps=[
            "Reproduce the failing test locally",
            "Capture error logs and stack trace",
            "Identify root cause",
            "Apply fix to test or code",
            "Re-run test suite to verify"
        ]
    )"""
    args_schema: type[BaseModel] = UpdatePlanInput
    
    # Reference to shared plan state (set by executor)
    plan_state: Optional[PlanState] = None
    _plan_callback: Optional[Callable] = None
    
    def __init__(self, plan_state: Optional[PlanState] = None, plan_callback: Optional[Callable] = None, **kwargs):
        super().__init__(**kwargs)
        self.plan_state = plan_state or PlanState()
        self._plan_callback = plan_callback
    
    def _run(self, title: str, steps: List[str]) -> str:
        """Update the plan with new steps."""
        self.plan_state.title = title
        self.plan_state.steps = [PlanStep(description=s) for s in steps]
        
        # Auto-save to session
        saved_path = self.plan_state.save()
        
        # Notify callback if set (for UI rendering)
        if self._plan_callback:
            self._plan_callback(self.plan_state)
        
        result = f"Plan updated:\n\n{self.plan_state.render()}"
        if saved_path:
            result += f"\n\n[dim]Session: {self.plan_state.session_id}[/dim]"
        return result


class CompleteStepTool(BaseTool):
    """Mark a plan step as complete."""
    
    name: str = "complete_step"
    description: str = """Mark a step in the current plan as completed.
    
Use this after finishing a step to update the plan progress.
Step numbers are 1-indexed (first step is 1, not 0).
Progress is automatically saved.

Example:
    complete_step(step_number=1)  # Mark first step as done"""
    args_schema: type[BaseModel] = CompleteStepInput
    
    # Reference to shared plan state (set by executor)
    plan_state: Optional[PlanState] = None
    _plan_callback: Optional[Callable] = None
    
    def __init__(self, plan_state: Optional[PlanState] = None, plan_callback: Optional[Callable] = None, **kwargs):
        super().__init__(**kwargs)
        self.plan_state = plan_state or PlanState()
        self._plan_callback = plan_callback
    
    def _run(self, step_number: int) -> str:
        """Mark a step as complete."""
        if not self.plan_state.steps:
            return "No plan exists. Use update_plan first to create a plan."
        
        if step_number < 1 or step_number > len(self.plan_state.steps):
            return f"Invalid step number. Plan has {len(self.plan_state.steps)} steps (1-{len(self.plan_state.steps)})."
        
        step = self.plan_state.steps[step_number - 1]
        if step.completed:
            return f"Step {step_number} was already completed."
        
        step.completed = True
        
        # Auto-save to session
        self.plan_state.save()
        
        # Notify callback if set (for UI rendering)
        if self._plan_callback:
            self._plan_callback(self.plan_state)
        
        # Count progress
        completed = sum(1 for s in self.plan_state.steps if s.completed)
        total = len(self.plan_state.steps)
        
        return f"✓ Step {step_number} completed ({completed}/{total} done)\n\n{self.plan_state.render()}"


def get_planning_tools(
    plan_state: Optional[PlanState] = None,
    plan_callback: Optional[Callable] = None,
    session_id: Optional[str] = None
) -> tuple[List[BaseTool], PlanState]:
    """
    Get planning tools with shared state.
    
    Args:
        plan_state: Optional existing plan state to use
        plan_callback: Optional callback function called when plan changes
        session_id: Optional session ID for persistence. If provided and plan exists,
                   will load from disk. If None, generates a new session ID.
        
    Returns:
        Tuple of (list of tools, plan state object)
    """
    # Try to load existing session or create new one
    if session_id:
        loaded = PlanState.load(session_id)
        if loaded:
            state = loaded
            logger.info(f"Resumed session {session_id} with plan: {state.title}")
        else:
            state = plan_state or PlanState()
            state.session_id = session_id
    else:
        state = plan_state or PlanState()
        if not state.session_id:
            state.session_id = generate_session_id()
    
    tools = [
        UpdatePlanTool(plan_state=state, plan_callback=plan_callback),
        CompleteStepTool(plan_state=state, plan_callback=plan_callback),
    ]
    
    return tools, state
