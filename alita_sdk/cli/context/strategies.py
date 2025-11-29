"""
Pruning strategies for CLI context management.

Implements various strategies for selecting which messages to include
in the LLM context when the token limit is exceeded.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type, Union

from .message import CLIMessage


@dataclass
class PruningConfig:
    """Configuration for pruning strategies."""
    
    max_context_tokens: int = 8000
    preserve_recent_messages: int = 5
    pruning_method: str = 'oldest_first'
    weights: Dict[str, float] = field(default_factory=lambda: {
        'recency': 1.0,
        'importance': 1.0,
        'user_messages': 1.2,
        'thread_continuity': 1.0,
    })
    
    @classmethod
    def from_strategy(cls, strategy_config: Dict) -> 'PruningConfig':
        """Create PruningConfig from strategy configuration dict."""
        return cls(
            max_context_tokens=strategy_config.get('max_context_tokens', 8000),
            preserve_recent_messages=strategy_config.get('preserve_recent_messages', 5),
            pruning_method=strategy_config.get('pruning_method', 'oldest_first'),
            weights=strategy_config.get('weights', {
                'recency': 1.0,
                'importance': 1.0,
                'user_messages': 1.2,
                'thread_continuity': 1.0,
            }),
        )


class PruningStrategy(ABC):
    """Abstract base class for pruning strategies."""

    def __init__(self, config: PruningConfig):
        self.config = config

    @abstractmethod
    def select_messages(
        self,
        messages: List[CLIMessage],
        available_tokens: int
    ) -> List[CLIMessage]:
        """
        Select messages within the available token budget.
        
        Args:
            messages: List of messages to select from
            available_tokens: Maximum tokens available for selection
            
        Returns:
            Selected messages within token budget
        """
        pass

    @staticmethod
    def get_token_count(message: CLIMessage) -> int:
        """Extract token count from message."""
        return message.token_count


class OldestFirstStrategy(PruningStrategy):
    """
    Select messages starting from newest until token limit is reached.
    
    This effectively drops the oldest messages first when context is full.
    """

    def select_messages(
        self,
        messages: List[CLIMessage],
        available_tokens: int
    ) -> List[CLIMessage]:
        selected = []
        current_tokens = 0

        # Sort by index descending (newest first)
        sorted_messages = sorted(messages, key=lambda x: x.index, reverse=True)

        for message in sorted_messages:
            msg_tokens = self.get_token_count(message)
            if current_tokens + msg_tokens <= available_tokens:
                selected.append(message)
                current_tokens += msg_tokens
            else:
                break

        # Return in original order (oldest first)
        selected.sort(key=lambda x: x.index)
        return selected


class ImportanceBasedStrategy(PruningStrategy):
    """Select messages based on calculated importance scores."""

    def select_messages(
        self,
        messages: List[CLIMessage],
        available_tokens: int
    ) -> List[CLIMessage]:
        # Calculate importance scores
        scored_messages = []
        for message in messages:
            score = self._calculate_importance_score(message)
            scored_messages.append((score, message))

        # Sort by importance (highest first)
        scored_messages.sort(key=lambda x: x[0], reverse=True)

        # Select until token limit
        selected = []
        current_tokens = 0

        for score, message in scored_messages:
            msg_tokens = self.get_token_count(message)
            if current_tokens + msg_tokens <= available_tokens:
                selected.append(message)
                current_tokens += msg_tokens

        # Return in original order
        selected.sort(key=lambda x: x.index)
        return selected

    def _calculate_importance_score(self, message: CLIMessage) -> float:
        """Calculate importance score for a message."""
        base_score = message.priority
        weight = message.weight

        # Factor in message length (longer messages might be more important)
        token_count = message.token_count
        length_factor = min(1.5, token_count / 100)  # Cap at 1.5x

        # Factor in replies (messages with replies might be more important)
        reply_factor = 1.2 if message.reply_to_id else 1.0

        # Factor in user vs assistant messages
        weights = self.config.weights
        role_factor = 1.0
        if message.role == 'user':
            role_factor = weights.get('user_messages', 1.0)
        elif message.role == 'system':
            role_factor = 1.5  # System messages are usually important

        # Factor in recency (newer messages get higher scores)
        recency_weight = weights.get('recency', 1.0)
        # Simple recency factor based on index
        recency_factor = 1.0 + (message.index * 0.01 * recency_weight)

        return base_score * weight * length_factor * reply_factor * role_factor * recency_factor


class PruningStrategyFactory:
    """Factory for creating pruning strategy instances."""

    _strategies: Dict[str, Type[PruningStrategy]] = {
        'oldest_first': OldestFirstStrategy,
        'importance_based': ImportanceBasedStrategy,
    }

    @classmethod
    def create(cls, strategy_name: str, config: PruningConfig) -> PruningStrategy:
        """
        Create a pruning strategy instance.
        
        Args:
            strategy_name: Name of the strategy ('oldest_first', 'importance_based')
            config: Configuration for the strategy
            
        Returns:
            PruningStrategy instance
            
        Raises:
            ValueError: If strategy_name is not recognized
        """
        strategy_class = cls._strategies.get(strategy_name)
        if not strategy_class:
            available = list(cls._strategies.keys())
            raise ValueError(
                f"Unknown pruning strategy: {strategy_name}. "
                f"Available strategies: {available}"
            )
        return strategy_class(config)

    @classmethod
    def register_strategy(cls, name: str, strategy_class: Type[PruningStrategy]):
        """Register a custom pruning strategy."""
        cls._strategies[name] = strategy_class

    @classmethod
    def available_strategies(cls) -> List[str]:
        """Get list of available strategy names."""
        return list(cls._strategies.keys())


class PruningOrchestrator:
    """
    Orchestrates the pruning process by applying strategies with token budgets.
    
    Handles preserving recent messages, calculating available token budgets,
    and coordinating strategy application.
    """

    def __init__(self, strategy_config: Dict):
        """
        Initialize the orchestrator with strategy configuration.
        
        Args:
            strategy_config: Configuration dictionary containing:
                - pruning_method: Strategy name to use
                - preserve_recent_messages: Number of recent messages to preserve
                - max_context_tokens: Maximum tokens allowed
                - weights: Weighting configuration for strategies
        """
        self.strategy_config = strategy_config
        self.pruning_config = PruningConfig.from_strategy(strategy_config)

    def apply_pruning(
        self,
        messages: List[CLIMessage],
        summaries: Optional[List[dict]] = None,
        summary_tokens: int = 0,
    ) -> List[CLIMessage]:
        """
        Apply pruning strategy to reduce context size.
        
        Args:
            messages: List of messages to prune
            summaries: List of summaries (for token calculation)
            summary_tokens: Pre-calculated summary token count
            
        Returns:
            List of messages to include in context (with included=True)
        """
        strategy_method = self.strategy_config.get('pruning_method', 'oldest_first')
        preserve_recent = self.strategy_config.get('preserve_recent_messages', 5)
        max_tokens = self.strategy_config.get('max_context_tokens', 8000)

        # Split into recent (always preserved) and older messages
        if preserve_recent > 0 and len(messages) > preserve_recent:
            recent_messages = messages[-preserve_recent:]
            older_messages = messages[:-preserve_recent]
        else:
            recent_messages = messages
            older_messages = []

        # Calculate tokens used by preserved recent messages and summaries
        preserved_tokens = sum(m.token_count for m in recent_messages)
        preserved_tokens += summary_tokens

        available_tokens = max_tokens - preserved_tokens

        if available_tokens <= 0 or not older_messages:
            # Mark older messages as excluded
            for msg in older_messages:
                msg.included = False
            return recent_messages

        # Apply pruning strategy to older messages
        try:
            strategy = PruningStrategyFactory.create(strategy_method, self.pruning_config)
            selected_older = strategy.select_messages(older_messages, available_tokens)
        except ValueError:
            # Fallback to oldest_first
            strategy = PruningStrategyFactory.create('oldest_first', self.pruning_config)
            selected_older = strategy.select_messages(older_messages, available_tokens)

        # Mark messages as included/excluded
        selected_indices = {m.index for m in selected_older}
        for msg in older_messages:
            msg.included = msg.index in selected_indices

        # Combine and sort by index
        final_selection = selected_older + recent_messages
        final_selection.sort(key=lambda x: x.index)

        return final_selection
