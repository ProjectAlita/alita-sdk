"""
CLI tools package.

Contains specialized tools for CLI agents.
"""

from .filesystem import get_filesystem_tools
from .terminal import get_terminal_tools, create_default_blocked_patterns_file
from .planning import (
    get_planning_tools, 
    PlanState, 
    list_sessions, 
    generate_session_id,
    create_session_memory,
    save_session_metadata,
    load_session_metadata,
    get_session_dir,
)
from .approval import create_approval_wrapper, ApprovalToolWrapper, prompt_approval

__all__ = [
    'get_filesystem_tools',
    'get_terminal_tools',
    'create_default_blocked_patterns_file',
    'get_planning_tools',
    'PlanState',
    'list_sessions',
    'generate_session_id',
    'create_session_memory',
    'save_session_metadata',
    'load_session_metadata',
    'get_session_dir',
    'create_approval_wrapper',
    'ApprovalToolWrapper',
    'prompt_approval',
]
