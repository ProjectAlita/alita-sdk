"""
Toolkit runtime utilities for event dispatching and execution context.
This module provides tools with the ability to dispatch custom events during execution.
"""

import sys
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def dispatch_custom_event(event_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Dispatch a custom event from within a toolkit tool execution.
    
    This function can be called by toolkit tools to send events back to the runtime
    for monitoring, logging, or other purposes.
    
    Args:
        event_type: Type of the event (e.g., "progress", "warning", "info")
        data: Event data dictionary
        
    Returns:
        Event dictionary if successful, None if no executor context available
        
    Example:
        ```python
        from alita_sdk.runtime.utils.toolkit_runtime import dispatch_custom_event
        
        def my_tool_function(param1, param2):
            # Dispatch a progress event
            dispatch_custom_event("progress", {
                "message": "Processing started",
                "step": 1,
                "total_steps": 3
            })
            
            # Do some work
            result = process_data(param1, param2)
            
            # Dispatch completion event
            dispatch_custom_event("completion", {
                "message": "Processing completed",
                "result_size": len(result)
            })
            
            return result
        ```
    """
    try:
        # Try to get the current executor context
        if hasattr(sys.modules[__name__], 'toolkit_dispatch_context'):
            context = sys.modules[__name__].toolkit_dispatch_context
            return context.dispatch_custom_event(event_type, data)
        else:
            # No executor context available - this is normal when not in test mode
            logger.debug(f"No toolkit executor context available for event: {event_type}")
            return None
    except Exception as e:
        logger.warning(f"Error dispatching custom event {event_type}: {e}")
        return None


def get_executor_context():
    """
    Get the current toolkit executor context if available.
    
    Returns:
        ToolkitExecutor context or None if not in execution context
    """
    try:
        if hasattr(sys.modules[__name__], 'toolkit_dispatch_context'):
            return sys.modules[__name__].toolkit_dispatch_context.executor
        return None
    except Exception:
        return None


def is_in_test_mode() -> bool:
    """
    Check if the toolkit is currently running in test mode.
    
    Returns:
        True if running in test mode with executor context, False otherwise
    """
    return get_executor_context() is not None


class ToolkitRuntimeContext:
    """
    Context manager for toolkit runtime execution.
    
    This can be used by tools that need to perform setup/cleanup operations
    when running in test mode vs normal execution.
    """
    
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.executor = get_executor_context()
        
    def __enter__(self):
        if self.executor:
            dispatch_custom_event("tool_start", {
                "tool_name": self.tool_name,
                "message": f"Starting execution of {self.tool_name}"
            })
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            if exc_type is None:
                dispatch_custom_event("tool_end", {
                    "tool_name": self.tool_name,
                    "message": f"Completed execution of {self.tool_name}",
                    "success": True
                })
            else:
                dispatch_custom_event("tool_error", {
                    "tool_name": self.tool_name,
                    "message": f"Error in {self.tool_name}: {exc_val}",
                    "success": False,
                    "error_type": exc_type.__name__ if exc_type else "Unknown"
                })
        return False  # Don't suppress exceptions
    
    def dispatch_progress(self, message: str, step: int = None, total_steps: int = None, **kwargs):
        """Convenience method for dispatching progress events."""
        data = {"message": message, "tool_name": self.tool_name}
        if step is not None:
            data["step"] = step
        if total_steps is not None:
            data["total_steps"] = total_steps
        data.update(kwargs)
        dispatch_custom_event("progress", data)
    
    def dispatch_info(self, message: str, **kwargs):
        """Convenience method for dispatching info events."""
        data = {"message": message, "tool_name": self.tool_name}
        data.update(kwargs)
        dispatch_custom_event("info", data)
    
    def dispatch_warning(self, message: str, **kwargs):
        """Convenience method for dispatching warning events."""
        data = {"message": message, "tool_name": self.tool_name}
        data.update(kwargs)
        dispatch_custom_event("warning", data)
