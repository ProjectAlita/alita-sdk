"""
Planning Middleware - Task planning and tracking for agents.

Provides plan management for multi-step task execution with progress tracking.
Supports two storage backends:
1. PostgreSQL - when connection_string is provided (production/indexer_worker)
2. Filesystem - when no connection string (local CLI usage)

Usage:
    from alita_sdk.runtime.middleware.planning import PlanningMiddleware

    middleware = PlanningMiddleware(
        conversation_id="session-123",
        connection_string="postgresql://...",  # Optional
        callbacks={"plan_updated": my_callback}
    )
"""

from .middleware import PlanningMiddleware
from .wrapper import (
    PlanningWrapper,
    PlanStep,
    PlanState,
    StepStatus,
    FilesystemStorage,
    PostgresStorage,
)
from .models import (
    AgentPlan,
    PlanStatus,
    ensure_plan_tables,
    delete_plan_by_conversation_id,
    cleanup_on_graceful_completion,
)

__all__ = [
    # Main middleware class
    "PlanningMiddleware",
    # Wrapper and state classes
    "PlanningWrapper",
    "PlanStep",
    "PlanState",
    "StepStatus",
    # Storage backends
    "FilesystemStorage",
    "PostgresStorage",
    # SQLAlchemy model and utilities
    "AgentPlan",
    "PlanStatus",
    "ensure_plan_tables",
    "delete_plan_by_conversation_id",
    "cleanup_on_graceful_completion",
]
