"""
CLI tools package.

Contains specialized tools for CLI agents.
"""

from .filesystem import get_filesystem_tools, FilesystemApiWrapper
from .terminal import get_terminal_tools, create_default_blocked_patterns_file
from .planning import (
    get_planning_tools, 
    PlanState, 
    list_sessions, 
    generate_session_id,
    create_session_memory,
    save_session_metadata,
    load_session_metadata,
    update_session_metadata,
    get_session_dir,
    to_portable_path,
    from_portable_path,
)
from .approval import create_approval_wrapper, ApprovalToolWrapper, prompt_approval

__all__ = [
    'get_filesystem_tools',
    'FilesystemApiWrapper',
    'get_terminal_tools',
    'create_default_blocked_patterns_file',
    'get_planning_tools',
    'PlanState',
    'list_sessions',
    'generate_session_id',
    'create_session_memory',
    'save_session_metadata',
    'load_session_metadata',
    'update_session_metadata',
    'get_session_dir',
    'to_portable_path',
    'from_portable_path',
    'create_approval_wrapper',
    'ApprovalToolWrapper',
    'prompt_approval',
]
