"""
Planning tools for CLI agents.

Provides plan management for multi-step task execution with progress tracking.
Sessions are persisted to $ALITA_DIR/sessions/<session_id>/
- plan.json: Execution plan with steps
- memory.db: SQLite database for conversation memory
- session.json: Session metadata (agent, model, etc.)

This module uses PlanningMiddleware for unified usage across CLI, indexer_worker,
and SDK agents. The middleware supports both PostgreSQL (production) and
filesystem (local CLI) storage backends.
"""

import os
import json
import uuid
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Session Management Functions
# ============================================================================

def get_sessions_dir() -> Path:
    """Get the sessions directory path (relative to $ALITA_DIR or .alita)."""
    alita_dir = os.environ.get('ALITA_DIR', '.alita')
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


def update_session_metadata(session_id: str, updates: Dict[str, Any]) -> None:
    """
    Update session metadata by merging new fields into existing metadata.
    
    This preserves existing fields while updating/adding new ones.
    
    Args:
        session_id: The session ID
        updates: Dictionary with fields to update/add
    """
    existing = load_session_metadata(session_id) or {}
    existing.update(updates)
    save_session_metadata(session_id, existing)
    logger.debug(f"Updated session metadata with: {list(updates.keys())}")


def get_alita_dir() -> Path:
    """Get the ALITA_DIR path (relative to $ALITA_DIR or .alita)."""
    return Path(os.environ.get('ALITA_DIR', '.alita'))


def to_portable_path(path: str) -> str:
    """
    Convert an absolute path to a portable path for session storage.
    
    If the path is under $ALITA_DIR, store as relative path (e.g., 'agents/my-agent.yaml').
    Otherwise, store the absolute path.
    
    Args:
        path: Absolute file path
        
    Returns:
        Portable path string (relative to ALITA_DIR if applicable, else absolute)
    """
    if not path:
        return path
    
    try:
        path_obj = Path(path).resolve()
        alita_dir = get_alita_dir().resolve()
        
        # Check if path is under ALITA_DIR
        if str(path_obj).startswith(str(alita_dir)):
            relative = path_obj.relative_to(alita_dir)
            return str(relative)
    except (ValueError, OSError):
        pass
    
    return str(path)


def from_portable_path(portable_path: str) -> str:
    """
    Convert a portable path back to an absolute path.
    
    If the path is relative, resolve it against $ALITA_DIR.
    Otherwise, return as-is.
    
    Args:
        portable_path: Portable path string from session storage
        
    Returns:
        Absolute file path
    """
    if not portable_path:
        return portable_path
    
    path_obj = Path(portable_path)
    
    # If already absolute, return as-is
    if path_obj.is_absolute():
        return str(path_obj)
    
    # Resolve relative path against ALITA_DIR
    alita_dir = get_alita_dir()
    return str(alita_dir / portable_path)


# ============================================================================
# PlanState - Re-export from middleware for CLI UI compatibility
# ============================================================================

# Re-export from middleware for consistent types across the codebase
from alita_sdk.runtime.middleware.planning import (
    PlanStep,
    PlanState,
    StepStatus,
    PlanningMiddleware,
)


def load_plan_state(session_id: str) -> Optional[PlanState]:
    """
    Load plan state from session directory using middleware storage.

    Args:
        session_id: The session ID

    Returns:
        PlanState or None if not found
    """
    try:
        # Use middleware's filesystem storage to load plan
        from alita_sdk.runtime.middleware.planning import FilesystemStorage
        storage = FilesystemStorage(str(get_sessions_dir() / session_id))
        return storage.get_plan(session_id)
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
                "steps_in_progress": 0,
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
                    steps = data.get("steps", [])
                    session_info["steps_total"] = len(steps)
                    # Handle both old (completed bool) and new (status string) formats
                    for s in steps:
                        if s.get("status") == StepStatus.COMPLETED or s.get("completed"):
                            session_info["steps_completed"] += 1
                        elif s.get("status") == StepStatus.IN_PROGRESS:
                            session_info["steps_in_progress"] += 1
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


# ============================================================================
# Planning Tools - Using PlanningMiddleware
# ============================================================================

def get_planning_middleware(
    plan_callback: Optional[Callable] = None,
    session_id: Optional[str] = None
) -> PlanningMiddleware:
    """
    Get a PlanningMiddleware instance for CLI usage.

    Uses filesystem storage with session_id as the conversation identifier.

    Args:
        plan_callback: Optional callback function called when plan changes (for CLI UI)
        session_id: Optional session ID for persistence. If None, generates a new one.

    Returns:
        PlanningMiddleware instance
    """
    # Generate session_id if not provided
    if not session_id:
        session_id = generate_session_id()

    # Create middleware with filesystem storage (no connection_string)
    # Use session-specific directory for plan storage
    middleware = PlanningMiddleware(
        conversation_id=session_id,
        connection_string=None,  # Uses filesystem storage
        storage_dir=str(get_sessions_dir() / session_id),
        callbacks={"plan_updated": plan_callback} if plan_callback else None,
    )

    return middleware


def get_planning_tools(
    plan_state: Optional[PlanState] = None,
    plan_callback: Optional[Callable] = None,
    session_id: Optional[str] = None
) -> tuple[List[BaseTool], PlanState]:
    """
    Get planning tools using PlanningMiddleware.

    Uses the PlanningMiddleware which supports both PostgreSQL
    and filesystem storage. For CLI, it uses filesystem storage with
    session_id as the conversation identifier.

    Args:
        plan_state: Optional existing plan state (for backwards compatibility)
        plan_callback: Optional callback function called when plan changes (for CLI UI)
        session_id: Optional session ID for persistence. If None, generates a new one.

    Returns:
        Tuple of (list of tools, plan state object)
    """
    # Generate session_id if not provided
    if not session_id:
        session_id = generate_session_id()

    # Create middleware with filesystem storage
    middleware = get_planning_middleware(
        plan_callback=plan_callback,
        session_id=session_id
    )

    # Get tools from middleware
    tools = middleware.get_tools()

    # Try to load existing plan state
    loaded = load_plan_state(session_id)
    state = loaded if loaded else (plan_state or PlanState())

    return tools, state
