"""
CLI Message wrapper with context tracking.

Provides a message class that tracks inclusion status, token counts,
and supports conversion to/from LangChain message formats.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .token_estimation import estimate_message_tokens


@dataclass
class CLIMessage:
    """
    Chat message with context management metadata.
    
    Tracks whether the message is included in context, its token count,
    and provides conversion to various message formats.
    
    Attributes:
        role: Message role (user, assistant, system)
        content: Message content text
        index: Position in the full conversation history
        token_count: Cached token count for this message
        included: Whether message is included in LLM context
        created_at: Timestamp when message was created
        priority: Priority weight for importance-based pruning
        weight: Additional weight factor for pruning decisions
    """
    role: str
    content: str
    index: int
    token_count: int = 0
    included: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: float = 1.0
    weight: float = 1.0
    
    def __post_init__(self):
        """Calculate token count if not provided."""
        if self.token_count == 0 and self.content:
            self.token_count = estimate_message_tokens(self.role, self.content)
    
    @classmethod
    def from_dict(cls, msg_dict: Dict[str, Any], index: int, model: str = 'gpt-4') -> 'CLIMessage':
        """
        Create CLIMessage from a simple dict format.
        
        Args:
            msg_dict: Dictionary with 'role' and 'content' keys
            index: Position in conversation
            model: Model name for token estimation
            
        Returns:
            CLIMessage instance
        """
        role = msg_dict.get('role', 'user')
        content = msg_dict.get('content', '')
        token_count = estimate_message_tokens(role, content, model)
        
        return cls(
            role=role,
            content=content,
            index=index,
            token_count=token_count,
            included=msg_dict.get('included', True),
            priority=msg_dict.get('priority', 1.0),
            weight=msg_dict.get('weight', 1.0),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to simple dict format for LLM calls.
        
        Returns:
            Dictionary with 'role' and 'content' keys
        """
        return {
            'role': self.role,
            'content': self.content,
        }
    
    def to_langchain_message(self) -> Any:
        """
        Convert to LangChain message format.
        
        Returns:
            Appropriate LangChain message type (HumanMessage, AIMessage, SystemMessage)
        """
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        if self.role == 'user':
            return HumanMessage(content=self.content)
        elif self.role == 'assistant':
            return AIMessage(content=self.content)
        elif self.role == 'system':
            return SystemMessage(content=self.content)
        else:
            # Default to HumanMessage for unknown roles
            return HumanMessage(content=self.content)
    
    @classmethod
    def from_langchain_message(cls, message: Any, index: int) -> 'CLIMessage':
        """
        Create CLIMessage from LangChain message.
        
        Args:
            message: LangChain message (HumanMessage, AIMessage, etc.)
            index: Position in conversation
            
        Returns:
            CLIMessage instance
        """
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        content = message.content if hasattr(message, 'content') else str(message)
        
        if isinstance(message, HumanMessage):
            role = 'user'
        elif isinstance(message, AIMessage):
            role = 'assistant'
        elif isinstance(message, SystemMessage):
            role = 'system'
        else:
            role = 'user'
        
        return cls(
            role=role,
            content=content,
            index=index,
        )
    
    def to_state_dict(self) -> Dict[str, Any]:
        """
        Convert to state dictionary for persistence.
        
        Returns:
            Dictionary with all fields for saving to context_state.json
        """
        return {
            'index': self.index,
            'role': self.role,
            'content': self.content,
            'token_count': self.token_count,
            'included': self.included,
            'created_at': self.created_at.isoformat(),
            'priority': self.priority,
            'weight': self.weight,
        }
    
    @classmethod
    def from_state_dict(cls, state: Dict[str, Any]) -> 'CLIMessage':
        """
        Restore CLIMessage from state dictionary.
        
        Args:
            state: Dictionary from to_state_dict()
            
        Returns:
            CLIMessage instance
        """
        created_at = state.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)
        
        return cls(
            role=state['role'],
            content=state['content'],
            index=state['index'],
            token_count=state.get('token_count', 0),
            included=state.get('included', True),
            created_at=created_at,
            priority=state.get('priority', 1.0),
            weight=state.get('weight', 1.0),
        )
    
    @property
    def meta(self) -> Dict[str, Any]:
        """
        Get metadata in context_manager compatible format.
        
        Used for compatibility with pruning strategies from context_manager.
        """
        return {
            'context': {
                'token_count': self.token_count,
                'weight': self.weight,
                'priority': self.priority,
                'included': self.included,
            }
        }
    
    @property
    def reply_to_id(self) -> Optional[int]:
        """
        Get reply-to ID (for thread awareness).
        
        For CLI messages, we use simple sequential ordering.
        User messages reply to previous assistant, and vice versa.
        """
        if self.index > 0:
            return self.index - 1
        return None
    
    @property
    def author_participant(self) -> Any:
        """
        Get author participant for importance scoring.
        
        Returns a simple object with entity_name attribute.
        """
        class Participant:
            def __init__(self, role: str):
                self.entity_name = role
        
        return Participant(self.role)


def messages_to_cli_messages(
    messages: List[Dict[str, Any]],
    model: str = 'gpt-4'
) -> List[CLIMessage]:
    """
    Convert a list of message dicts to CLIMessage objects.
    
    Args:
        messages: List of dicts with 'role' and 'content' keys
        model: Model name for token estimation
        
    Returns:
        List of CLIMessage objects
    """
    return [
        CLIMessage.from_dict(msg, index=i, model=model)
        for i, msg in enumerate(messages)
    ]


def cli_messages_to_dicts(
    messages: List[CLIMessage],
    include_only: bool = True
) -> List[Dict[str, str]]:
    """
    Convert CLIMessage objects to simple dicts for LLM calls.
    
    Args:
        messages: List of CLIMessage objects
        include_only: If True, only include messages where included=True
        
    Returns:
        List of dicts with 'role' and 'content' keys
    """
    result = []
    for msg in messages:
        if include_only and not msg.included:
            continue
        result.append(msg.to_dict())
    return result


def cli_messages_to_langchain(
    messages: List[CLIMessage],
    include_only: bool = True
) -> List[Any]:
    """
    Convert CLIMessage objects to LangChain messages.
    
    Args:
        messages: List of CLIMessage objects
        include_only: If True, only include messages where included=True
        
    Returns:
        List of LangChain message objects
    """
    result = []
    for msg in messages:
        if include_only and not msg.included:
            continue
        result.append(msg.to_langchain_message())
    return result
