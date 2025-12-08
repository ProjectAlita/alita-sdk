"""
CLI Context Manager for chat history management.

Provides token-aware context management with pruning, summarization,
and efficient tracking of message inclusion status.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .message import CLIMessage, cli_messages_to_dicts, cli_messages_to_langchain
from .token_estimation import estimate_tokens, calculate_total_tokens
from .strategies import PruningOrchestrator, PruningConfig

logger = logging.getLogger(__name__)


@dataclass
class ContextInfo:
    """
    Information about current context state for UI display.
    
    Attributes:
        used_tokens: Tokens currently in context
        max_tokens: Maximum allowed tokens
        fill_ratio: Percentage of context used (0.0-1.0)
        message_count: Total messages in history
        included_count: Messages included in context
        pruned_count: Messages excluded from context
        summary_count: Number of active summaries
    """
    used_tokens: int = 0
    max_tokens: int = 8000
    fill_ratio: float = 0.0
    message_count: int = 0
    included_count: int = 0
    pruned_count: int = 0
    summary_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'used_tokens': self.used_tokens,
            'max_tokens': self.max_tokens,
            'fill_ratio': self.fill_ratio,
            'message_count': self.message_count,
            'included_count': self.included_count,
            'pruned_count': self.pruned_count,
            'summary_count': self.summary_count,
        }


@dataclass
class Summary:
    """
    Conversation summary for context compression.
    
    Attributes:
        content: Summary text
        from_idx: Start message index (inclusive)
        to_idx: End message index (inclusive)
        token_count: Token count of summary
        created_at: Creation timestamp
    """
    content: str
    from_idx: int
    to_idx: int
    token_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        """Calculate token count if not provided."""
        if self.token_count == 0 and self.content:
            self.token_count = estimate_tokens(self.content)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'content': self.content,
            'from_idx': self.from_idx,
            'to_idx': self.to_idx,
            'token_count': self.token_count,
            'created_at': self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Summary':
        """Create Summary from dictionary."""
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)
        
        return cls(
            content=data['content'],
            from_idx=data['from_idx'],
            to_idx=data['to_idx'],
            token_count=data.get('token_count', 0),
            created_at=created_at,
        )


class CLIContextManager:
    """
    Manages chat history context with token-aware pruning and summarization.
    
    Features:
    - Incremental token tracking (O(1) for new messages)
    - Lazy pruning (only when needed)
    - In-memory message inclusion tracking
    - Summary generation and management
    - Session state persistence
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        alita_dir: str = '.alita',
        # Convenience parameters (override config if provided)
        max_context_tokens: Optional[int] = None,
        preserve_recent: Optional[int] = None,
        pruning_method: Optional[str] = None,
        enable_summarization: Optional[bool] = None,
        summary_trigger_ratio: Optional[float] = None,
        summaries_limit: Optional[int] = None,
        llm: Optional[Any] = None,
    ):
        """
        Initialize context manager.
        
        Args:
            config: Context management configuration dict
            session_id: Session ID for persistence
            alita_dir: Base Alita directory
            max_context_tokens: Maximum tokens in context (overrides config)
            preserve_recent: Number of recent messages to preserve (overrides config)
            pruning_method: Pruning strategy name (overrides config)
            enable_summarization: Enable automatic summarization (overrides config)
            summary_trigger_ratio: Context fill ratio that triggers summarization (overrides config)
            summaries_limit: Maximum number of summaries to keep (overrides config)
            llm: LLM instance for summarization
        """
        # Default configuration
        self.config = {
            'enabled': True,
            'max_context_tokens': 8000,
            'preserve_recent_messages': 5,
            'pruning_method': 'oldest_first',
            'enable_summarization': True,
            'summary_trigger_ratio': 0.8,
            'summaries_limit_count': 5,
            'weights': {
                'recency': 1.0,
                'importance': 1.0,
                'user_messages': 1.2,
                'thread_continuity': 1.0,
            },
        }
        if config:
            self.config.update(config)
        
        # Apply convenience parameters
        if max_context_tokens is not None:
            self.config['max_context_tokens'] = max_context_tokens
        if preserve_recent is not None:
            self.config['preserve_recent_messages'] = preserve_recent
        if pruning_method is not None:
            self.config['pruning_method'] = pruning_method
        if enable_summarization is not None:
            self.config['enable_summarization'] = enable_summarization
        if summary_trigger_ratio is not None:
            self.config['summary_trigger_ratio'] = summary_trigger_ratio
        if summaries_limit is not None:
            self.config['summaries_limit_count'] = summaries_limit
        
        self.session_id = session_id
        self.alita_dir = alita_dir
        self.llm = llm  # LLM for summarization
        
        # Message storage
        self._messages: List[CLIMessage] = []
        self._summaries: List[Summary] = []
        
        # Token tracking (incremental)
        self._included_tokens: int = 0
        self._summary_tokens: int = 0
        self._needs_pruning: bool = False
        
        # Pruning orchestrator
        self._orchestrator = PruningOrchestrator(self.config)
        
        # Load existing state if session provided
        if session_id:
            self._load_state()
    
    @property
    def max_tokens(self) -> int:
        """Get maximum context tokens."""
        return self.config.get('max_context_tokens', 8000)
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens in context (messages + summaries)."""
        return self._included_tokens + self._summary_tokens
    
    @property
    def fill_ratio(self) -> float:
        """Get context fill ratio (0.0-1.0)."""
        if self.max_tokens <= 0:
            return 0.0
        return min(1.0, self.total_tokens / self.max_tokens)
    
    def add_message(self, role: str, content: str) -> CLIMessage:
        """
        Add a new message to the history.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            
        Returns:
            The created CLIMessage
        """
        index = len(self._messages)
        message = CLIMessage(
            role=role,
            content=content,
            index=index,
        )
        
        self._messages.append(message)
        self._included_tokens += message.token_count
        
        # Check if we need to prune
        if self.total_tokens > self.max_tokens:
            self._needs_pruning = True
        
        return message
    
    def build_context(
        self,
        system_prompt: Optional[str] = None,
        force_prune: bool = False,
    ) -> List[Dict[str, str]]:
        """
        Build optimized context for LLM invocation.
        
        This is the main method called before each LLM call.
        Only performs pruning if tokens exceed limit.
        
        Args:
            system_prompt: Optional system prompt to include
            force_prune: Force re-pruning even if not needed
            
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        if not self.config.get('enabled', True):
            # Context management disabled, return all messages
            messages = cli_messages_to_dicts(self._messages, include_only=False)
            if system_prompt:
                messages.insert(0, {'role': 'system', 'content': system_prompt})
            
            return messages
        
        # Prune if needed
        if self._needs_pruning or force_prune:
            self._apply_pruning()
        
        # Build message list
        messages = []
        
        # Add system prompt first
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        
        # Add summaries as system context
        if self._summaries:
            summary_text = self._format_summaries_for_context()
            if summary_text:
                messages.append({
                    'role': 'system',
                    'content': f"Previous conversation summary:\n{summary_text}"
                })
        
        # Add included messages
        messages.extend(cli_messages_to_dicts(self._messages, include_only=True))
        
        return messages
    
    def build_context_langchain(
        self,
        system_prompt: Optional[str] = None,
        force_prune: bool = False,
    ) -> List[Any]:
        """
        Build optimized context as LangChain messages.
        
        Args:
            system_prompt: Optional system prompt to include
            force_prune: Force re-pruning even if not needed
            
        Returns:
            List of LangChain message objects
        """
        from langchain_core.messages import SystemMessage
        
        if not self.config.get('enabled', True):
            messages = cli_messages_to_langchain(self._messages, include_only=False)
            if system_prompt:
                messages.insert(0, SystemMessage(content=system_prompt))
            return messages
        
        if self._needs_pruning or force_prune:
            self._apply_pruning()
        
        messages = []
        
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        if self._summaries:
            summary_text = self._format_summaries_for_context()
            if summary_text:
                messages.append(SystemMessage(
                    content=f"Previous conversation summary:\n{summary_text}"
                ))
        
        messages.extend(cli_messages_to_langchain(self._messages, include_only=True))
        
        return messages
    
    def _apply_pruning(self):
        """Apply pruning strategy to reduce context size."""
        if not self._messages:
            self._needs_pruning = False
            return
        
        # Apply pruning
        self._orchestrator.apply_pruning(
            self._messages,
            summary_tokens=self._summary_tokens,
        )
        
        # Recalculate included tokens
        self._included_tokens = sum(
            m.token_count for m in self._messages if m.included
        )
        
        self._needs_pruning = False
        
        # Check if we should trigger summarization
        if self.config.get('enable_summarization', True):
            self._maybe_trigger_summarization()
        
        # Save state if session exists
        if self.session_id:
            self._save_state()
    
    def _maybe_trigger_summarization(self):
        """Check if summarization should be triggered and mark for it."""
        trigger_ratio = self.config.get('summary_trigger_ratio', 0.8)
        
        if self.fill_ratio < trigger_ratio:
            return
        
        # Count pruned messages that haven't been summarized
        pruned_messages = [m for m in self._messages if not m.included]
        
        # Check if we have enough pruned messages to summarize
        min_for_summary = 3
        if len(pruned_messages) >= min_for_summary:
            # Find the range of pruned messages
            if pruned_messages:
                from_idx = min(m.index for m in pruned_messages)
                to_idx = max(m.index for m in pruned_messages)
                
                # Check if this range is already summarized
                for summary in self._summaries:
                    if summary.from_idx <= from_idx and summary.to_idx >= to_idx:
                        return  # Already summarized
                
                logger.debug(
                    f"Summarization needed: {len(pruned_messages)} pruned messages "
                    f"(indices {from_idx}-{to_idx})"
                )
    
    def generate_summary(
        self,
        llm: Any,
        from_idx: Optional[int] = None,
        to_idx: Optional[int] = None,
    ) -> Optional[Summary]:
        """
        Generate a summary of pruned messages using the LLM.
        
        Args:
            llm: LLM instance with invoke() method
            from_idx: Start message index (default: first pruned)
            to_idx: End message index (default: last pruned)
            
        Returns:
            Generated Summary or None if failed/not needed
        """
        # Find pruned messages to summarize
        pruned_messages = [m for m in self._messages if not m.included]
        
        if not pruned_messages:
            return None
        
        if from_idx is None:
            from_idx = min(m.index for m in pruned_messages)
        if to_idx is None:
            to_idx = max(m.index for m in pruned_messages)
        
        # Get messages in range
        messages_to_summarize = [
            m for m in self._messages
            if from_idx <= m.index <= to_idx
        ]
        
        if len(messages_to_summarize) < 3:
            return None
        
        # Build summary prompt
        conversation_text = self._format_messages_for_summary(messages_to_summarize)
        
        summary_instructions = self.config.get('summary_instructions') or (
            "Summarize the following conversation concisely, preserving key information, "
            "decisions made, and important context. Focus on facts and outcomes."
        )
        
        prompt = f"{summary_instructions}\n\nConversation:\n{conversation_text}"
        
        try:
            response = llm.invoke([{'role': 'user', 'content': prompt}])
            summary_content = response.content if hasattr(response, 'content') else str(response)
            
            summary = Summary(
                content=summary_content,
                from_idx=from_idx,
                to_idx=to_idx,
            )
            
            # Add summary and update tokens
            self._summaries.append(summary)
            self._summary_tokens += summary.token_count
            
            # Prune old summaries if limit exceeded
            self._prune_old_summaries()
            
            # Save state
            if self.session_id:
                self._save_state()
            
            logger.info(f"Generated summary for messages {from_idx}-{to_idx}")
            return summary
            
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            return None
    
    def _prune_old_summaries(self):
        """Remove oldest summaries if limit exceeded."""
        limit = self.config.get('summaries_limit_count', 5)
        
        while len(self._summaries) > limit:
            removed = self._summaries.pop(0)
            self._summary_tokens -= removed.token_count
            logger.debug(f"Pruned old summary (indices {removed.from_idx}-{removed.to_idx})")
    
    def _format_messages_for_summary(self, messages: List[CLIMessage]) -> str:
        """Format messages for summary generation prompt."""
        lines = []
        for msg in messages:
            role = msg.role.capitalize()
            lines.append(f"{role}: {msg.content}")
        return "\n\n".join(lines)
    
    def _format_summaries_for_context(self) -> str:
        """Format all summaries for inclusion in context."""
        if not self._summaries:
            return ""
        
        parts = []
        for i, summary in enumerate(self._summaries, 1):
            if len(self._summaries) > 1:
                parts.append(f"[Part {i}] {summary.content}")
            else:
                parts.append(summary.content)
        
        return "\n\n".join(parts)
    
    def _build_context_info(self) -> ContextInfo:
        """Build context info for UI display."""
        included_count = sum(1 for m in self._messages if m.included)
        
        return ContextInfo(
            used_tokens=self.total_tokens,
            max_tokens=self.max_tokens,
            fill_ratio=self.fill_ratio,
            message_count=len(self._messages),
            included_count=included_count,
            pruned_count=len(self._messages) - included_count,
            summary_count=len(self._summaries),
        )
    
    def get_context_info(self) -> Dict[str, Any]:
        """
        Get current context info as a dictionary for UI display.
        
        Returns:
            Dict with keys: used_tokens, max_tokens, fill_ratio, pruned_count, etc.
        """
        return self._build_context_info().to_dict()
    
    def is_message_included(self, index: int) -> bool:
        """
        Check if a message at a given index is included in context.
        
        Args:
            index: Message index (0-based)
            
        Returns:
            True if included, False if pruned
        """
        if 0 <= index < len(self._messages):
            return self._messages[index].included
        return False
    
    def clear(self):
        """Clear all messages and summaries."""
        self._messages.clear()
        self._summaries.clear()
        self._included_tokens = 0
        self._summary_tokens = 0
        self._needs_pruning = False
        
        if self.session_id:
            self._save_state()
    
    def _get_state_path(self) -> Path:
        """Get path to context state file."""
        if self.alita_dir.startswith('~'):
            base = os.path.expanduser(self.alita_dir)
        else:
            base = self.alita_dir
        
        return Path(base) / 'sessions' / self.session_id / 'context_state.json'
    
    def _save_state(self):
        """Save context state to disk."""
        if not self.session_id:
            return
        
        state_path = self._get_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            'messages': [m.to_state_dict() for m in self._messages],
            'summaries': [s.to_dict() for s in self._summaries],
            'included_tokens': self._included_tokens,
            'summary_tokens': self._summary_tokens,
            'saved_at': datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            with open(state_path, 'w') as f:
                json.dump(state, f, indent=2)
            logger.debug(f"Saved context state to {state_path}")
        except IOError as e:
            logger.warning(f"Failed to save context state: {e}")
    
    def _load_state(self):
        """Load context state from disk."""
        if not self.session_id:
            return
        
        state_path = self._get_state_path()
        
        if not state_path.exists():
            return
        
        try:
            with open(state_path, 'r') as f:
                state = json.load(f)
            
            self._messages = [
                CLIMessage.from_state_dict(m)
                for m in state.get('messages', [])
            ]
            self._summaries = [
                Summary.from_dict(s)
                for s in state.get('summaries', [])
            ]
            self._included_tokens = state.get('included_tokens', 0)
            self._summary_tokens = state.get('summary_tokens', 0)
            
            # Recalculate if needed
            if self._included_tokens == 0 and self._messages:
                self._included_tokens = sum(
                    m.token_count for m in self._messages if m.included
                )
            if self._summary_tokens == 0 and self._summaries:
                self._summary_tokens = sum(s.token_count for s in self._summaries)
            
            logger.debug(f"Loaded context state from {state_path}")
            
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load context state: {e}")
    
    def import_chat_history(self, chat_history: List[Dict[str, str]]):
        """
        Import existing chat history into the context manager.
        
        Useful for migrating existing conversations or session resume.
        
        Args:
            chat_history: List of message dicts with 'role' and 'content'
        """
        for msg_dict in chat_history:
            role = msg_dict.get('role', 'user')
            content = msg_dict.get('content', '')
            if content:
                self.add_message(role, content)
    
    def export_chat_history(self, include_only: bool = False) -> List[Dict[str, str]]:
        """
        Export chat history as list of message dicts.
        
        Args:
            include_only: If True, only export included messages
            
        Returns:
            List of message dicts with 'role' and 'content'
        """
        return cli_messages_to_dicts(self._messages, include_only=include_only)


def sanitize_message_history(messages: List[Any]) -> List[Any]:
    """
    Sanitize message history to ensure valid tool call/response structure.
    
    This function ensures that any AIMessage with tool_calls has corresponding
    ToolMessages for all tool_call_ids. This prevents the LLM API error:
    "An assistant message with 'tool_calls' must be followed by tool messages 
    responding to each 'tool_call_id'."
    
    Use this when:
    - Resuming from a GraphRecursionError (step limit)
    - Resuming from a tool execution limit
    - Loading corrupted checkpoint state
    
    Args:
        messages: List of LangChain message objects or dicts
        
    Returns:
        Sanitized list of messages with placeholder ToolMessages added for any
        missing tool call responses.
    """
    from langchain_core.messages import ToolMessage, AIMessage as LCAIMessage
    
    if not messages:
        return messages
    
    result = list(messages)  # Copy to avoid mutating original
    
    # Build set of existing tool_call_ids that have responses
    existing_tool_responses = set()
    for msg in result:
        if hasattr(msg, 'tool_call_id') and msg.tool_call_id:
            existing_tool_responses.add(msg.tool_call_id)
        elif isinstance(msg, dict) and msg.get('type') == 'tool':
            tool_call_id = msg.get('tool_call_id')
            if tool_call_id:
                existing_tool_responses.add(tool_call_id)
    
    # Find AIMessages with tool_calls and check for missing responses
    messages_to_add = []
    for i, msg in enumerate(result):
        tool_calls = None
        
        # Check for tool_calls in different message formats
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            tool_calls = msg.tool_calls
        elif isinstance(msg, dict) and msg.get('tool_calls'):
            tool_calls = msg.get('tool_calls')
        
        if tool_calls:
            # Check each tool_call for a corresponding response
            for tool_call in tool_calls:
                tool_call_id = None
                tool_name = 'unknown'
                
                if isinstance(tool_call, dict):
                    tool_call_id = tool_call.get('id', '')
                    tool_name = tool_call.get('name', 'unknown')
                elif hasattr(tool_call, 'id'):
                    tool_call_id = getattr(tool_call, 'id', '')
                    tool_name = getattr(tool_call, 'name', 'unknown')
                
                if tool_call_id and tool_call_id not in existing_tool_responses:
                    # Missing tool response - create placeholder
                    logger.warning(
                        f"Found AIMessage with tool_call '{tool_name}' ({tool_call_id}) "
                        f"without corresponding ToolMessage. Adding placeholder."
                    )
                    placeholder = ToolMessage(
                        content=f"[Tool call '{tool_name}' was interrupted - no response available. "
                                f"The task may need to be retried.]",
                        tool_call_id=tool_call_id
                    )
                    messages_to_add.append((i + 1, placeholder))
                    existing_tool_responses.add(tool_call_id)  # Prevent duplicates
    
    # Insert placeholder messages (reverse order to maintain correct indices)
    for insert_idx, placeholder_msg in reversed(messages_to_add):
        result.insert(insert_idx, placeholder_msg)
    
    if messages_to_add:
        logger.info(f"Sanitized message history: added {len(messages_to_add)} placeholder ToolMessages")
    
    return result

