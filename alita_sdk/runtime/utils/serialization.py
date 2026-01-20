"""
Serialization utilities for safe JSON encoding of complex objects.

Handles Pydantic models, LangChain messages, datetime objects, and other
non-standard types that may appear in state variables.
"""
import json
import logging
from datetime import datetime, date
from typing import Any

logger = logging.getLogger(__name__)


def _convert_to_serializable(obj: Any, _seen: set = None) -> Any:
    """
    Recursively convert an object to JSON-serializable primitives.

    Handles nested dicts and lists that may contain non-serializable objects.
    Uses a seen set to prevent infinite recursion with circular references.

    Args:
        obj: Any object to convert
        _seen: Internal set to track seen object ids (for circular reference detection)

    Returns:
        JSON-serializable representation of the object
    """
    # Initialize seen set for circular reference detection
    if _seen is None:
        _seen = set()

    # Check for circular references (only for mutable objects)
    obj_id = id(obj)
    if isinstance(obj, (dict, list, set)) and obj_id in _seen:
        return f"<circular reference: {type(obj).__name__}>"

    # Primitives - return as-is
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # Add to seen set for mutable containers
    if isinstance(obj, (dict, list, set)):
        _seen = _seen | {obj_id}  # Create new set to avoid mutation issues

    # Dict - recursively process all values
    if isinstance(obj, dict):
        return {
            _convert_to_serializable(k, _seen): _convert_to_serializable(v, _seen)
            for k, v in obj.items()
        }

    # List/tuple - recursively process all items
    if isinstance(obj, (list, tuple)):
        return [_convert_to_serializable(item, _seen) for item in obj]

    # Set - convert to list and process
    if isinstance(obj, set):
        return [_convert_to_serializable(item, _seen) for item in obj]

    # Bytes - decode to string
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return obj.decode('utf-8', errors='replace')

    # Datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()

    # Pydantic BaseModel (v2) - check for model_dump method
    if hasattr(obj, 'model_dump') and callable(getattr(obj, 'model_dump')):
        try:
            return _convert_to_serializable(obj.model_dump(), _seen)
        except Exception as e:
            logger.debug(f"Failed to call model_dump on {type(obj).__name__}: {e}")

    # Pydantic BaseModel (v1) - check for dict method
    if hasattr(obj, 'dict') and callable(getattr(obj, 'dict')) and hasattr(obj, '__fields__'):
        try:
            return _convert_to_serializable(obj.dict(), _seen)
        except Exception as e:
            logger.debug(f"Failed to call dict on {type(obj).__name__}: {e}")

    # LangChain BaseMessage - extract key fields
    if hasattr(obj, 'type') and hasattr(obj, 'content'):
        try:
            result = {
                "type": obj.type,
                "content": _convert_to_serializable(obj.content, _seen),
            }
            if hasattr(obj, 'additional_kwargs') and obj.additional_kwargs:
                result["additional_kwargs"] = _convert_to_serializable(obj.additional_kwargs, _seen)
            if hasattr(obj, 'name') and obj.name:
                result["name"] = obj.name
            return result
        except Exception as e:
            logger.debug(f"Failed to extract message fields from {type(obj).__name__}: {e}")

    # Objects with __dict__ attribute (custom classes)
    if hasattr(obj, '__dict__'):
        try:
            return _convert_to_serializable(obj.__dict__, _seen)
        except Exception as e:
            logger.debug(f"Failed to serialize __dict__ of {type(obj).__name__}: {e}")

    # UUID objects
    if hasattr(obj, 'hex') and hasattr(obj, 'int'):
        return str(obj)

    # Enum objects
    if hasattr(obj, 'value') and hasattr(obj, 'name') and hasattr(obj.__class__, '__members__'):
        return obj.value

    # Last resort - convert to string
    try:
        return str(obj)
    except Exception:
        return f"<non-serializable: {type(obj).__name__}>"


def safe_serialize(obj: Any, **kwargs) -> str:
    """
    Safely serialize any object to a JSON string.

    Pre-processes the entire object tree to convert non-serializable
    objects before passing to json.dumps. This ensures nested dicts
    and lists with non-standard objects are handled correctly.

    Args:
        obj: Any object to serialize
        **kwargs: Additional arguments passed to json.dumps
            (e.g., indent, sort_keys)

    Returns:
        JSON string representation of the object

    Example:
        >>> from pydantic import BaseModel
        >>> class User(BaseModel):
        ...     name: str
        >>> state = {"user": User(name="Alice"), "count": 5}
        >>> safe_serialize(state)
        '{"user": {"name": "Alice"}, "count": 5}'
    """
    # Pre-process the entire object tree
    serializable = _convert_to_serializable(obj)

    # Set defaults
    kwargs.setdefault('ensure_ascii', False)

    return json.dumps(serializable, **kwargs)
