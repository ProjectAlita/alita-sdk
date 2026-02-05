"""
Toolkit Security Module

Provides runtime security filtering for toolkits and tools.
This is a fail-safe layer that prevents blocked toolkits/tools from
being instantiated, even if they exist in the database.

The blocklist can be configured by:
1. Calling configure_blocklist() at application startup
2. Setting environment variables ALITA_BLOCKED_TOOLKITS and ALITA_BLOCKED_TOOLS

Example:
    # At indexer startup
    from alita_sdk.runtime.toolkits.security import configure_blocklist
    configure_blocklist(
        blocked_toolkits=['shell', 'browser'],
        blocked_tools={'github': ['delete_repository'], 'jira': ['delete_issue']}
    )

    # Later, get_tools() will automatically filter blocked items
"""

import logging
import os
import json
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Module-level configuration
_blocked_toolkits: List[str] = []
_blocked_tools: Dict[str, List[str]] = {}
_initialized: bool = False


def configure_blocklist(
    blocked_toolkits: Optional[List[str]] = None,
    blocked_tools: Optional[Dict[str, List[str]]] = None
) -> None:
    """
    Configure the toolkit security blocklist.

    Args:
        blocked_toolkits: List of toolkit types to block completely
        blocked_tools: Dict mapping toolkit type to list of blocked tool names
    """
    global _blocked_toolkits, _blocked_tools, _initialized

    _blocked_toolkits = [t.lower() for t in (blocked_toolkits or [])]
    _blocked_tools = {
        k.lower(): [t.lower() for t in (v or [])]
        for k, v in (blocked_tools or {}).items()
    }
    _initialized = True

    if _blocked_toolkits:
        logger.info(f"[SECURITY] Configured blocked toolkits: {_blocked_toolkits}")
    if _blocked_tools:
        logger.info(f"[SECURITY] Configured blocked tools: {_blocked_tools}")


def _load_from_env() -> None:
    """Load blocklist from environment variables if not configured."""
    global _blocked_toolkits, _blocked_tools, _initialized

    if _initialized:
        return

    # Try loading from environment
    env_toolkits = os.environ.get('ALITA_BLOCKED_TOOLKITS', '')
    env_tools = os.environ.get('ALITA_BLOCKED_TOOLS', '')

    if env_toolkits:
        try:
            _blocked_toolkits = [t.strip().lower() for t in env_toolkits.split(',') if t.strip()]
            logger.info(f"[SECURITY] Loaded blocked toolkits from env: {_blocked_toolkits}")
        except Exception as e:
            logger.warning(f"[SECURITY] Failed to parse ALITA_BLOCKED_TOOLKITS: {e}")

    if env_tools:
        try:
            parsed = json.loads(env_tools)
            _blocked_tools = {
                k.lower(): [t.lower() for t in (v or [])]
                for k, v in parsed.items()
            }
            logger.info(f"[SECURITY] Loaded blocked tools from env: {_blocked_tools}")
        except Exception as e:
            logger.warning(f"[SECURITY] Failed to parse ALITA_BLOCKED_TOOLS: {e}")

    _initialized = True


def is_toolkit_blocked(toolkit_type: str) -> bool:
    """
    Check if a toolkit type is blocked.

    Args:
        toolkit_type: The type/name of the toolkit (e.g., 'github', 'shell')

    Returns:
        True if the toolkit is blocked, False otherwise
    """
    _load_from_env()

    blocked = toolkit_type.lower() in _blocked_toolkits
    if blocked:
        logger.warning(f"[SECURITY] Blocked toolkit type: {toolkit_type}")
    return blocked


def is_tool_blocked(toolkit_type: str, tool_name: str) -> bool:
    """
    Check if a specific tool within a toolkit is blocked.

    Args:
        toolkit_type: The type/name of the toolkit
        tool_name: The name of the tool within the toolkit

    Returns:
        True if the tool is blocked, False otherwise
    """
    _load_from_env()

    # First check if entire toolkit is blocked
    if is_toolkit_blocked(toolkit_type):
        return True

    # Check specific tool
    toolkit_lower = toolkit_type.lower()
    if toolkit_lower in _blocked_tools:
        if tool_name.lower() in _blocked_tools[toolkit_lower]:
            logger.warning(f"[SECURITY] Blocked tool '{tool_name}' in toolkit '{toolkit_type}'")
            return True

    return False


def get_blocked_tools_for_toolkit(toolkit_type: str) -> List[str]:
    """
    Get the list of blocked tools for a specific toolkit.

    Args:
        toolkit_type: The type/name of the toolkit

    Returns:
        List of blocked tool names (lowercase) for this toolkit
    """
    _load_from_env()
    return _blocked_tools.get(toolkit_type.lower(), [])


def get_blocklist_config() -> Dict:
    """
    Get the current blocklist configuration.

    Returns:
        Dict with 'blocked_toolkits' and 'blocked_tools'
    """
    _load_from_env()
    return {
        'blocked_toolkits': _blocked_toolkits.copy(),
        'blocked_tools': {k: v.copy() for k, v in _blocked_tools.items()}
    }


def reset_blocklist() -> None:
    """Reset the blocklist configuration (mainly for testing)."""
    global _blocked_toolkits, _blocked_tools, _initialized
    _blocked_toolkits = []
    _blocked_tools = {}
    _initialized = False
