"""
PlanningMiddleware - Provides task planning and tracking capabilities to agents.

Inspired by LangChain's TodoListMiddleware pattern, this middleware:
1. Injects planning tools (update_plan, start_step, complete_step, get_plan_status, delete_plan)
2. Adds system prompt guidance for effective planning (from constants.PLAN_ADDON)
3. Restores plan state when resuming conversations
4. Supports callbacks for UI updates

The system prompt comes from constants.py (PLAN_ADDON) as the single source of truth.

Usage:
    from alita_sdk.runtime.middleware.planning import PlanningMiddleware

    # Create middleware
    middleware = PlanningMiddleware(
        conversation_id="session-123",
        connection_string="postgresql://...",  # Optional - uses filesystem if not provided
        callbacks={"plan_updated": my_callback}
    )

    # Pass to Assistant - tools and prompts are automatically integrated
    assistant = Assistant(
        alita=client,
        data=agent_data,
        client=llm,
        middleware=[middleware]
    )
"""

import logging
from typing import Any, List, Optional, Dict, Callable

from langchain_core.tools import BaseTool

from ..base import Middleware
from .wrapper import PlanningWrapper, PlanState
# Import BaseAction directly from the specific module to avoid circular import through __init__
from alita_sdk.tools.base.tool import BaseAction
# Import the canonical planning prompt from constants (single source of truth)
from ...langchain.constants import PLAN_ADDON

logger = logging.getLogger(__name__)


class PlanningMiddleware(Middleware):
    """
    Middleware that provides task planning and tracking capabilities.

    This middleware adds planning tools to agents and provides system prompt
    guidance for effective task planning. It supports both PostgreSQL and
    filesystem storage backends.

    Args:
        conversation_id: Conversation ID for scoping plans
        connection_string: PostgreSQL connection string. If not provided, uses filesystem.
        storage_dir: Directory for filesystem storage (when no connection_string)
        callbacks: Optional dict of callback functions:
            - 'plan_updated': Called when plan changes, receives PlanState
        custom_system_prompt: Optional custom system prompt to append/replace default
        **kwargs: Additional arguments passed to base class
    """

    def __init__(
        self,
        conversation_id: Optional[str] = None,
        connection_string: Optional[str] = None,
        storage_dir: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        custom_system_prompt: Optional[str] = None,
        **kwargs
    ):
        super().__init__(conversation_id=conversation_id, callbacks=callbacks, **kwargs)

        self.connection_string = connection_string
        self.storage_dir = storage_dir
        self.custom_system_prompt = custom_system_prompt

        # Create wrapper with plan_callback to fire our callbacks
        self._wrapper = PlanningWrapper(
            connection_string=connection_string,
            conversation_id=conversation_id,
            storage_dir=storage_dir,
            plan_callback=self._on_plan_change
        )

        self._tools: Optional[List[BaseTool]] = None
        logger.info(f"PlanningMiddleware initialized (conversation_id={conversation_id})")

    def _on_plan_change(self, plan: PlanState) -> None:
        """Internal callback when plan changes."""
        self._fire_callback('plan_updated', plan)

    def get_tools(self) -> List[BaseTool]:
        """
        Return list of planning tools.

        Tools provided:
        - update_plan: Create or replace the current plan
        - start_step: Mark a step as in progress
        - complete_step: Mark a step as completed
        - get_plan_status: Get current plan status
        - delete_plan: Delete the current plan

        Returns:
            List of BaseTool instances
        """
        if self._tools is not None:
            return self._tools

        tools = []
        available_tools = self._wrapper.get_available_tools()

        for tool in available_tools:
            tools.append(BaseAction(
                api_wrapper=self._wrapper,
                name=tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))

        self._tools = tools
        logger.debug(f"Created {len(tools)} planning tools")
        return tools

    def get_system_prompt(self) -> str:
        """
        Return system prompt addition for planning.

        Uses PLAN_ADDON from constants.py as the canonical source.
        If custom_system_prompt is provided, it will be appended.

        Returns:
            System prompt string
        """
        if self.custom_system_prompt:
            return f"{PLAN_ADDON}\n\n{self.custom_system_prompt}"
        return PLAN_ADDON

    def on_conversation_start(self, conversation_id: str) -> Optional[str]:
        """
        Called when a conversation starts or resumes.

        Restores plan state and returns context message if a plan exists.

        Args:
            conversation_id: The conversation ID being started/resumed

        Returns:
            Context message with current plan state, or None if no plan
        """
        self.conversation_id = conversation_id

        # Update wrapper's conversation_id
        self._wrapper.conversation_id = conversation_id

        # Try to restore existing plan
        try:
            plan = self._wrapper._storage.get_plan(conversation_id)
            if plan and plan.steps:
                # Notify callback of restored plan
                self._fire_callback('plan_updated', plan)

                # Return context message
                completed = sum(1 for s in plan.steps if s.completed)
                in_progress = sum(1 for s in plan.steps if s.in_progress)
                total = len(plan.steps)

                if completed == total:
                    return f"[Plan '{plan.title}' is complete ({completed}/{total} steps done)]"
                else:
                    status = f"{completed}/{total} completed"
                    if in_progress:
                        status += f", {in_progress} in progress"
                    return f"[Resuming plan '{plan.title}' - {status}]\n\n{plan.render()}"

        except Exception as e:
            logger.warning(f"Failed to restore plan on conversation start: {e}")

        return None

    def on_conversation_end(self, conversation_id: str) -> None:
        """
        Called when a conversation ends.

        Currently no cleanup needed - plans are persisted.

        Args:
            conversation_id: The conversation ID ending
        """
        pass

    def get_current_plan(self) -> Optional[PlanState]:
        """
        Get the current plan state (if any).

        Useful for external access to plan state.

        Returns:
            Current PlanState or None
        """
        if not self.conversation_id:
            return None
        try:
            return self._wrapper._storage.get_plan(self.conversation_id)
        except Exception as e:
            logger.warning(f"Failed to get current plan: {e}")
            return None
