"""
Callback system for skill execution transparency.

This module provides a comprehensive callback system that allows real-time
monitoring of skill execution events, including tool usage, LLM calls,
and node transitions.
"""

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage

from .models import SkillEvent, SkillEventType

logger = logging.getLogger(__name__)


class SkillCallback(ABC):
    """
    Abstract base class for skill execution callbacks.
    """

    @abstractmethod
    def on_skill_event(
        self,
        event_type: SkillEventType,
        data: Dict[str, Any],
        skill_name: str,
        execution_id: str
    ) -> None:
        """
        Handle a skill execution event.

        Args:
            event_type: Type of the event.
            data: Event data dictionary.
            skill_name: Name of the skill generating the event.
            execution_id: Unique execution identifier.
        """
        pass


class CallbackManager:
    """
    Manager for multiple skill callbacks that forwards events to all registered callbacks.
    """

    def __init__(self, callbacks: Optional[List[SkillCallback]] = None):
        """
        Initialize callback manager.

        Args:
            callbacks: List of initial callbacks to register.
        """
        self.callbacks = callbacks or []
        self._lock = threading.Lock()

    def add_callback(self, callback: SkillCallback) -> None:
        """
        Add a callback to the manager.

        Args:
            callback: Callback to add.
        """
        with self._lock:
            self.callbacks.append(callback)

    def remove_callback(self, callback: SkillCallback) -> None:
        """
        Remove a callback from the manager.

        Args:
            callback: Callback to remove.
        """
        with self._lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)

    def emit_event(
        self,
        event_type: SkillEventType,
        data: Dict[str, Any],
        skill_name: str,
        execution_id: str
    ) -> None:
        """
        Emit an event to all registered callbacks.

        Args:
            event_type: Type of the event.
            data: Event data dictionary.
            skill_name: Name of the skill generating the event.
            execution_id: Unique execution identifier.
        """
        # Create event object
        event = SkillEvent(
            event_type=event_type,
            data=data.copy(),
            skill_name=skill_name,
            execution_id=execution_id,
            timestamp=time.time()
        )

        # Forward to all callbacks (thread-safe)
        callbacks_snapshot = []
        with self._lock:
            callbacks_snapshot = self.callbacks.copy()

        for callback in callbacks_snapshot:
            try:
                callback.on_skill_event(event_type, data, skill_name, execution_id)
            except Exception as e:
                # Don't let callback errors break skill execution
                logger.warning(
                    f"Callback {callback.__class__.__name__} failed for event "
                    f"{event_type.value}: {e}"
                )

    def clear(self) -> None:
        """Clear all registered callbacks."""
        with self._lock:
            self.callbacks.clear()

    def __len__(self) -> int:
        """Return number of registered callbacks."""
        with self._lock:
            return len(self.callbacks)


class LoggingCallback(SkillCallback):
    """
    Simple callback that logs all events.
    """

    def __init__(self, level: int = logging.INFO):
        """
        Initialize logging callback.

        Args:
            level: Logging level to use for events.
        """
        self.level = level
        self.logger = logging.getLogger(f"{__name__}.LoggingCallback")

    def on_skill_event(
        self,
        event_type: SkillEventType,
        data: Dict[str, Any],
        skill_name: str,
        execution_id: str
    ) -> None:
        """Log the skill event."""
        message = f"[{skill_name}:{execution_id[-8:]}] {event_type.value}"
        if data:
            message += f": {data}"

        self.logger.log(self.level, message)


class ProgressCallback(SkillCallback):
    """
    Callback that tracks and displays execution progress.
    """

    def __init__(self):
        """Initialize progress callback."""
        self.start_times: Dict[str, float] = {}
        self.node_counts: Dict[str, int] = {}

    def on_skill_event(
        self,
        event_type: SkillEventType,
        data: Dict[str, Any],
        skill_name: str,
        execution_id: str
    ) -> None:
        """Track progress events."""
        if event_type == SkillEventType.SKILL_START:
            self.start_times[execution_id] = time.time()
            self.node_counts[execution_id] = 0
            print(f"🚀 Starting skill: {skill_name}")

        elif event_type == SkillEventType.SKILL_END:
            if execution_id in self.start_times:
                duration = time.time() - self.start_times[execution_id]
                nodes = self.node_counts.get(execution_id, 0)
                print(f"✅ Completed skill: {skill_name} ({duration:.1f}s, {nodes} nodes)")

        elif event_type == SkillEventType.NODE_START:
            node_name = data.get('node', 'unknown')
            print(f"   🔄 Executing node: {node_name}")
            self.node_counts[execution_id] = self.node_counts.get(execution_id, 0) + 1

        elif event_type == SkillEventType.TOOL_START:
            tool_name = data.get('tool', 'unknown')
            print(f"      🔧 Using tool: {tool_name}")

        elif event_type == SkillEventType.LLM_START:
            model = data.get('model', 'unknown')
            print(f"      🤖 Calling LLM: {model}")

        elif event_type == SkillEventType.ERROR:
            error = data.get('error', 'unknown error')
            print(f"❌ Error in skill {skill_name}: {error}")


class FileCallback(SkillCallback):
    """
    Callback that writes events to a file for analysis or debugging.
    """

    def __init__(self, file_path: Path, json_format: bool = True):
        """
        Initialize file callback.

        Args:
            file_path: Path to write events to.
            json_format: Whether to write events as JSON (True) or text (False).
        """
        self.file_path = file_path
        self.json_format = json_format
        self._lock = threading.Lock()

        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def on_skill_event(
        self,
        event_type: SkillEventType,
        data: Dict[str, Any],
        skill_name: str,
        execution_id: str
    ) -> None:
        """Write event to file."""
        event = SkillEvent(
            event_type=event_type,
            data=data,
            skill_name=skill_name,
            execution_id=execution_id,
            timestamp=time.time()
        )

        with self._lock:
            try:
                with open(self.file_path, 'a', encoding='utf-8') as f:
                    if self.json_format:
                        f.write(json.dumps(event.to_dict()) + '\n')
                    else:
                        f.write(f"{event.timestamp} [{skill_name}:{execution_id}] "
                               f"{event_type.value}: {data}\n")
            except Exception as e:
                logger.warning(f"Failed to write event to file {self.file_path}: {e}")


class SkillLangChainCallback(BaseCallbackHandler):
    """
    LangChain callback handler that forwards events to the skill callback system.
    """

    def __init__(self, callback_manager: CallbackManager, skill_name: str, execution_id: str):
        """
        Initialize LangChain callback handler.

        Args:
            callback_manager: Callback manager to forward events to.
            skill_name: Name of the skill being executed.
            execution_id: Execution identifier.
        """
        super().__init__()
        self.callback_manager = callback_manager
        self.skill_name = skill_name
        self.execution_id = execution_id

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any
    ) -> None:
        """Handle tool start event."""
        self.callback_manager.emit_event(
            SkillEventType.TOOL_START,
            {
                "tool": serialized.get("name", "unknown"),
                "input": input_str,
                "serialized": serialized
            },
            self.skill_name,
            self.execution_id
        )

    def on_tool_end(
        self,
        output: str,
        **kwargs: Any
    ) -> None:
        """Handle tool end event."""
        self.callback_manager.emit_event(
            SkillEventType.TOOL_END,
            {
                "output": output
            },
            self.skill_name,
            self.execution_id
        )

    def on_tool_error(
        self,
        error: Exception,
        **kwargs: Any
    ) -> None:
        """Handle tool error event."""
        self.callback_manager.emit_event(
            SkillEventType.ERROR,
            {
                "error": str(error),
                "error_type": "tool_error"
            },
            self.skill_name,
            self.execution_id
        )

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any
    ) -> None:
        """Handle LLM start event."""
        self.callback_manager.emit_event(
            SkillEventType.LLM_START,
            {
                "model": serialized.get("model_name", "unknown"),
                "prompts": prompts,
                "serialized": serialized
            },
            self.skill_name,
            self.execution_id
        )

    def on_llm_end(
        self,
        response: Any,
        **kwargs: Any
    ) -> None:
        """Handle LLM end event."""
        self.callback_manager.emit_event(
            SkillEventType.LLM_END,
            {
                "response": str(response)
            },
            self.skill_name,
            self.execution_id
        )

    def on_llm_error(
        self,
        error: Exception,
        **kwargs: Any
    ) -> None:
        """Handle LLM error event."""
        self.callback_manager.emit_event(
            SkillEventType.ERROR,
            {
                "error": str(error),
                "error_type": "llm_error"
            },
            self.skill_name,
            self.execution_id
        )

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        """Handle chain start event."""
        self.callback_manager.emit_event(
            SkillEventType.CUSTOM_EVENT,
            {
                "event": "chain_start",
                "chain": serialized.get("name", "unknown"),
                "inputs": inputs
            },
            self.skill_name,
            self.execution_id
        )

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        """Handle chain end event."""
        self.callback_manager.emit_event(
            SkillEventType.CUSTOM_EVENT,
            {
                "event": "chain_end",
                "outputs": outputs
            },
            self.skill_name,
            self.execution_id
        )


class CallbackEmitter:
    """
    Helper class for emitting callbacks from subprocess execution.

    This class writes events to a pipe file that can be monitored by the parent process.
    """

    def __init__(self, pipe_path: Optional[str], execution_id: str):
        """
        Initialize callback emitter.

        Args:
            pipe_path: Path to callback pipe file.
            execution_id: Execution identifier.
        """
        self.pipe_path = Path(pipe_path) if pipe_path else None
        self.execution_id = execution_id
        self._lock = threading.Lock()

    def emit(
        self,
        event_type: SkillEventType,
        data: Dict[str, Any],
        skill_name: str
    ) -> None:
        """
        Emit an event to the pipe file.

        Args:
            event_type: Type of event.
            data: Event data.
            skill_name: Name of skill generating event.
        """
        if not self.pipe_path:
            return

        event = SkillEvent(
            event_type=event_type,
            data=data,
            skill_name=skill_name,
            execution_id=self.execution_id,
            timestamp=time.time()
        )

        with self._lock:
            try:
                with open(self.pipe_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(event.to_dict()) + '\n')
                    f.flush()
            except Exception as e:
                logger.warning(f"Failed to emit callback event: {e}")


def create_default_callbacks() -> List[SkillCallback]:
    """
    Create a default set of callbacks for skill execution.

    Returns:
        List of default callback instances.
    """
    return [
        LoggingCallback(level=logging.INFO),
        ProgressCallback()
    ]


def create_debug_callbacks(log_file: Optional[Path] = None) -> List[SkillCallback]:
    """
    Create callbacks suitable for debugging skill execution.

    Args:
        log_file: Optional path to write detailed event log.

    Returns:
        List of debug callback instances.
    """
    callbacks = [
        LoggingCallback(level=logging.DEBUG),
        ProgressCallback()
    ]

    if log_file:
        callbacks.append(FileCallback(log_file, json_format=True))

    return callbacks