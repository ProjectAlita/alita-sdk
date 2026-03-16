"""Runtime toolkit security and sensitive-action guardrails."""

import logging
import os
import json
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_SENSITIVE_ACTION_COMPANY_NAME = 'Your organization'
DEFAULT_SENSITIVE_ACTION_MESSAGE_TEMPLATE = (
    "{company_name} requires approval before running the sensitive action '{action_name}'."
)

# Module-level configuration
_blocked_toolkits: List[str] = []
_blocked_tools: Dict[str, List[str]] = {}
_blocklist_initialized: bool = False

_sensitive_tools: Dict[str, List[str]] = {}
_sensitive_action_company_name: str = DEFAULT_SENSITIVE_ACTION_COMPANY_NAME
_sensitive_action_message_template: str = DEFAULT_SENSITIVE_ACTION_MESSAGE_TEMPLATE
_sensitive_tools_initialized: bool = False


def get_tool_name_aliases(tool_name: Optional[str]) -> List[str]:
    """Return canonical aliases for a tool name.

    Runtime tool names can appear in multiple forms depending on how a tool is
    routed: plain base name (`list_branches_in_repo`), legacy prefixed name
    (`github___list_branches_in_repo`), or UI/runtime-prefixed name
    (`elitea_core:list_branches_in_repo`). Sensitive-tool matching and blocked
    follow-up exclusion must treat these as the same action.
    """
    normalized = str(tool_name or '').strip().lower()
    if not normalized:
        return []

    aliases: List[str] = []
    current = normalized
    while current and current not in aliases:
        aliases.append(current)

        reduced = current
        if '___' in reduced:
            reduced = reduced.split('___', 1)[1].strip()
        if ':' in reduced:
            reduced = reduced.split(':', 1)[1].strip()

        if not reduced or reduced == current:
            break
        current = reduced

    return aliases


def normalize_tool_name(tool_name: Optional[str]) -> str:
    """Return the canonical base tool name used by security checks."""
    aliases = get_tool_name_aliases(tool_name)
    return aliases[-1] if aliases else ''


def _normalize_tools_mapping(tool_map: Optional[Dict[str, List[str]]]) -> Dict[str, List[str]]:
    return {
        str(key).strip().lower(): [str(item).strip().lower() for item in (values or []) if str(item).strip()]
        for key, values in (tool_map or {}).items()
        if str(key).strip()
    }


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
    global _blocked_toolkits, _blocked_tools, _blocklist_initialized

    _blocked_toolkits = [t.lower() for t in (blocked_toolkits or [])]
    _blocked_tools = _normalize_tools_mapping(blocked_tools)
    _blocklist_initialized = True

    if _blocked_toolkits:
        logger.info(f"[SECURITY] Configured blocked toolkits: {_blocked_toolkits}")
    if _blocked_tools:
        logger.info(f"[SECURITY] Configured blocked tools: {_blocked_tools}")


def configure_sensitive_tools(
    sensitive_tools: Optional[Dict[str, List[str]]] = None,
    company_name: Optional[str] = None,
    message_template: Optional[str] = None,
) -> None:
    global _sensitive_tools, _sensitive_action_company_name, _sensitive_action_message_template
    global _sensitive_tools_initialized

    _sensitive_tools = _normalize_tools_mapping(sensitive_tools)
    _sensitive_action_company_name = company_name or DEFAULT_SENSITIVE_ACTION_COMPANY_NAME
    _sensitive_action_message_template = (
        message_template or DEFAULT_SENSITIVE_ACTION_MESSAGE_TEMPLATE
    )
    _sensitive_tools_initialized = True

def _load_blocklist_from_env() -> None:
    """Load blocklist from environment variables if not configured."""
    global _blocked_toolkits, _blocked_tools, _blocklist_initialized

    if _blocklist_initialized:
        return

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
            _blocked_tools = _normalize_tools_mapping(parsed)
            logger.info(f"[SECURITY] Loaded blocked tools from env: {_blocked_tools}")
        except Exception as e:
            logger.warning(f"[SECURITY] Failed to parse ALITA_BLOCKED_TOOLS: {e}")

    _blocklist_initialized = True


def _load_sensitive_tools_from_env() -> None:
    global _sensitive_tools, _sensitive_action_company_name, _sensitive_action_message_template
    global _sensitive_tools_initialized

    if _sensitive_tools_initialized:
        return

    env_sensitive_tools = os.environ.get('ALITA_SENSITIVE_TOOLS', '')
    env_company_name = os.environ.get('ALITA_SENSITIVE_ACTION_COMPANY_NAME', '')
    env_message_template = os.environ.get('ALITA_SENSITIVE_ACTION_MESSAGE_TEMPLATE', '')

    if env_sensitive_tools:
        try:
            _sensitive_tools = _normalize_tools_mapping(json.loads(env_sensitive_tools))
        except Exception as e:
            logger.warning(f"[SECURITY] Failed to parse ALITA_SENSITIVE_TOOLS: {e}")

    if env_company_name:
        _sensitive_action_company_name = env_company_name

    if env_message_template:
        _sensitive_action_message_template = env_message_template

    _sensitive_tools_initialized = True


def is_toolkit_blocked(toolkit_type: str) -> bool:
    """
    Check if a toolkit type is blocked.

    Args:
        toolkit_type: The type/name of the toolkit (e.g., 'github', 'shell')

    Returns:
        True if the toolkit is blocked, False otherwise
    """
    _load_blocklist_from_env()

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
    _load_blocklist_from_env()

    # First check if entire toolkit is blocked
    if is_toolkit_blocked(toolkit_type):
        return True

    # Check specific tool
    toolkit_lower = toolkit_type.lower()
    if toolkit_lower in _blocked_tools:
        blocked_tool_names = set(_blocked_tools[toolkit_lower])
        for candidate_name in get_tool_name_aliases(tool_name):
            if candidate_name in blocked_tool_names:
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
    _load_blocklist_from_env()
    return _blocked_tools.get(toolkit_type.lower(), [])


def get_blocklist_config() -> Dict:
    """
    Get the current blocklist configuration.

    Returns:
        Dict with 'blocked_toolkits' and 'blocked_tools'
    """
    _load_blocklist_from_env()
    return {
        'blocked_toolkits': _blocked_toolkits.copy(),
        'blocked_tools': {k: v.copy() for k, v in _blocked_tools.items()}
    }


def find_sensitive_tool_match(
    tool_name: str,
    toolkit_identifiers: Optional[List[Optional[str]]] = None,
) -> Optional[str]:
    _load_sensitive_tools_from_env()

    tool_name_aliases = get_tool_name_aliases(tool_name)
    if not tool_name_aliases:
        return None

    normalized_identifiers = []
    for identifier in toolkit_identifiers or []:
        normalized = str(identifier or '').strip().lower()
        if normalized and normalized not in normalized_identifiers:
            normalized_identifiers.append(normalized)

    for identifier in normalized_identifiers:
        sensitive_tool_names = set(_sensitive_tools.get(identifier, []))
        for candidate_name in tool_name_aliases:
            if candidate_name in sensitive_tool_names:
                return identifier

    wildcard_sensitive_tool_names = set(_sensitive_tools.get('*', []))
    for candidate_name in tool_name_aliases:
        if candidate_name in wildcard_sensitive_tool_names:
            return '*'

    return None


def get_sensitive_tool_policy(
    tool_name: str,
    toolkit_identifiers: Optional[List[Optional[str]]] = None,
    toolkit_label: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    matched_identifier = find_sensitive_tool_match(tool_name, toolkit_identifiers)
    if not matched_identifier:
        return None

    company_name = _sensitive_action_company_name or DEFAULT_SENSITIVE_ACTION_COMPANY_NAME
    message_template = _sensitive_action_message_template or DEFAULT_SENSITIVE_ACTION_MESSAGE_TEMPLATE
    resolved_toolkit_label = toolkit_label or matched_identifier or 'this toolkit'
    action_name = f'{resolved_toolkit_label}.{tool_name}' if resolved_toolkit_label else tool_name

    try:
        policy_message = message_template.format(
            company_name=company_name,
            tool_name=tool_name,
            toolkit_name=resolved_toolkit_label,
            toolkit_type=resolved_toolkit_label,
            toolkit_label=resolved_toolkit_label,
            action_name=action_name,
        )
    except Exception:
        policy_message = DEFAULT_SENSITIVE_ACTION_MESSAGE_TEMPLATE.format(
            company_name=company_name,
            tool_name=tool_name,
            toolkit_label=resolved_toolkit_label,
            action_name=action_name,
        )

    return {
        'matched_identifier': matched_identifier,
        'company_name': company_name,
        'message_template': message_template,
        'policy_message': policy_message,
        'toolkit_label': resolved_toolkit_label,
        'action_name': action_name,
    }


def get_sensitive_tools_config() -> Dict:
    _load_sensitive_tools_from_env()
    return {
        'sensitive_tools': {k: v.copy() for k, v in _sensitive_tools.items()},
        'sensitive_action_company_name': _sensitive_action_company_name,
        'sensitive_action_message_template': _sensitive_action_message_template,
    }


def has_sensitive_tools_config() -> bool:
    _load_sensitive_tools_from_env()
    return bool(_sensitive_tools)


def reset_blocklist() -> None:
    """Reset the blocklist configuration (mainly for testing)."""
    global _blocked_toolkits, _blocked_tools, _blocklist_initialized
    _blocked_toolkits = []
    _blocked_tools = {}
    _blocklist_initialized = False


def reset_sensitive_tools() -> None:
    global _sensitive_tools, _sensitive_action_company_name, _sensitive_action_message_template
    global _sensitive_tools_initialized
    _sensitive_tools = {}
    _sensitive_action_company_name = DEFAULT_SENSITIVE_ACTION_COMPANY_NAME
    _sensitive_action_message_template = DEFAULT_SENSITIVE_ACTION_MESSAGE_TEMPLATE
    _sensitive_tools_initialized = False
