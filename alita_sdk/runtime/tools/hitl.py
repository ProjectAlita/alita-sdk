"""
Human-in-the-Loop (HITL) Node for LangGraph pipelines.

Uses LangGraph's dynamic interrupt() pattern to pause execution and wait for human input.
The node presents a configured message to the user and routes based on their action:
  - Approve: routes to configured next node (pure routing)
  - Reject: routes to configured node (typically END)
  - Edit: routes to configured node with state update from user's edited input

Resume is handled via Command(resume={"action": "approve|reject|edit", "value": "..."})
"""

import logging
from typing import Optional

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.types import interrupt, Command

from ..langchain.utils import propagate_the_input_mapping

logger = logging.getLogger(__name__)

# HITL action constants
HITL_ACTION_APPROVE = "approve"
HITL_ACTION_REJECT = "reject"
HITL_ACTION_EDIT = "edit"

HITL_VALID_ACTIONS = {HITL_ACTION_APPROVE, HITL_ACTION_REJECT, HITL_ACTION_EDIT}

# State key used for HITL interrupt metadata
HITL_STATE_KEY = "hitl_interrupt"


class HITLNode(Runnable):
    """
    Human-in-the-Loop node that uses dynamic interrupt() to pause pipeline execution
    and wait for human decision (Approve / Reject / Edit).

    YAML spec example:
        - id: review_step
          type: hitl
          input:
            - summary
            - messages
          user_message:
            type: fstring        # fixed | variable | fstring
            value: "Please review the following summary:\n\n{summary}"
          routes:
            approve: next_processing_node
            reject: END
            edit: next_processing_node
          edit_state_key: summary   # which state key to update on edit

    The node:
    1. Builds user message from input_mapping pattern
    2. Calls interrupt() with HITL metadata (message, available actions, routes)
    3. Receives resume value: {"action": "approve|reject|edit", "value": "..."}
    4. Returns Command(goto=target_node) for approve/reject
       or Command(goto=target_node, update={edit_state_key: value}) for edit
    """

    name: str = "HITLNode"

    def __init__(
        self,
        name: str,
        input_variables: Optional[list[str]] = None,
        user_message: Optional[dict[str, str]] = None,
        routes: Optional[dict[str, str]] = None,
        edit_state_key: Optional[str] = None,
    ):
        self.name = name
        self.input_variables = input_variables or ["messages"]
        self.user_message_config = user_message or {"type": "fixed", "value": "Please review and approve to continue."}
        self.routes = routes or {}
        self.edit_state_key = edit_state_key

        # Validate routes - at minimum approve should exist
        if not self.routes.get(HITL_ACTION_APPROVE):
            logger.warning(f"HITL node '{name}' has no 'approve' route configured. "
                          f"Defaulting to END.")

    def _build_user_message(self, state: dict) -> str:
        """Build the user-facing message from the configured message pattern and current state."""
        msg_type = self.user_message_config.get("type", "fixed")
        msg_value = self.user_message_config.get("value", "")

        if msg_type == "fixed":
            return msg_value
        elif msg_type == "variable":
            # value is a state key name
            return str(state.get(msg_value, msg_value))
        elif msg_type == "fstring":
            # value is an f-string template with {state_key} placeholders
            input_data = {}
            for key in self.input_variables:
                if key != "messages":
                    input_data[key] = state.get(key, "")
            try:
                return msg_value.format(**input_data)
            except KeyError as e:
                logger.warning(f"HITL node '{self.name}': missing state key {e} in fstring template, "
                              f"trying full state fallback")
                try:
                    # Fallback: try with full state (excluding messages to avoid serialization issues)
                    safe_state = {k: v for k, v in state.items() if k != "messages"}
                    return msg_value.format(**safe_state)
                except KeyError:
                    logger.error(f"HITL node '{self.name}': cannot resolve fstring template, returning raw")
                    return msg_value
        else:
            logger.warning(f"HITL node '{self.name}': unknown message type '{msg_type}', using value as-is")
            return str(msg_value)

    def _resolve_route(self, action: str) -> str:
        """Get the target node for a given action, with fallback to END."""
        from langgraph.graph import END
        target = self.routes.get(action)
        if not target or target == "END":
            return "__end__"
        return target

    def _get_available_actions(self) -> list[str]:
        """Return only the actions that are correctly configured for runtime use."""
        available_actions: list[str] = []

        if self.routes.get(HITL_ACTION_APPROVE):
            available_actions.append(HITL_ACTION_APPROVE)

        if self.routes.get(HITL_ACTION_REJECT):
            available_actions.append(HITL_ACTION_REJECT)

        if self.routes.get(HITL_ACTION_EDIT):
            if self.routes.get(HITL_ACTION_EDIT) == "END":
                logger.warning(
                    "HITL node '%s': edit route cannot target END. The edit action will be hidden.",
                    self.name,
                )
            elif self.edit_state_key:
                available_actions.append(HITL_ACTION_EDIT)
            else:
                logger.warning(
                    "HITL node '%s': edit route is configured but edit_state_key is missing. "
                    "The edit action will be hidden.",
                    self.name,
                )

        return available_actions

    def invoke(self, state: dict, config: Optional[RunnableConfig] = None) -> Command:
        """
        Execute the HITL node:
        1. Build user message from state
        2. Call interrupt() to pause and send HITL metadata to the user
        3. Receive user's decision via Command(resume=...)
        4. Route accordingly
        """
        logger.info(f"HITL Node '{self.name}' - Building user message from state")

        # Build the user-facing message
        user_message = self._build_user_message(state)

        # Determine available actions from configured routes
        available_actions = self._get_available_actions()

        # Build interrupt payload with all metadata the UI needs
        interrupt_payload = {
            "type": "hitl",
            "node_name": self.name,
            "message": user_message,
            "available_actions": available_actions,
            "routes": self.routes,
            "edit_state_key": self.edit_state_key,
        }

        # Dispatch custom event for observability/callbacks
        dispatch_custom_event(
            "on_hitl_interrupt",
            {
                "node_name": self.name,
                "message": user_message,
                "available_actions": available_actions,
            },
            config=config,
        )

        logger.info(f"HITL Node '{self.name}' - Interrupting for human input. "
                    f"Actions: {available_actions}")

        # === DYNAMIC INTERRUPT ===
        # This pauses the graph execution and returns the payload to the caller.
        # Execution resumes when Command(resume=...) is sent.
        resume_value = interrupt(interrupt_payload)

        # === RESUME PATH ===
        # resume_value should be: {"action": "approve|reject|edit", "value": "..."}
        logger.info(f"HITL Node '{self.name}' - Resumed with: {resume_value}")

        if not isinstance(resume_value, dict):
            # Backward compat: if someone sends a plain string, treat as approve
            logger.warning(f"HITL node '{self.name}': expected dict resume value, got {type(resume_value)}. "
                          f"Treating as approve.")
            resume_value = {"action": HITL_ACTION_APPROVE, "value": str(resume_value)}

        action = resume_value.get("action", HITL_ACTION_APPROVE).lower()
        value = resume_value.get("value", "")

        if action not in HITL_VALID_ACTIONS:
            logger.warning(f"HITL node '{self.name}': unknown action '{action}', defaulting to approve")
            action = HITL_ACTION_APPROVE

        if action not in available_actions:
            raise ValueError(
                f"HITL node '{self.name}': action '{action}' is not configured for this node. "
                f"Available actions: {available_actions}"
            )

        if action == HITL_ACTION_EDIT and not self.edit_state_key:
            raise ValueError(
                f"HITL node '{self.name}': edit action requires a configured edit_state_key"
            )

        if action == HITL_ACTION_EDIT and self.routes.get(HITL_ACTION_EDIT) == "END":
            raise ValueError(
                f"HITL node '{self.name}': edit action must route to a node, not END"
            )

        target_node = self._resolve_route(action)
        logger.info(f"HITL Node '{self.name}' - Action: {action}, routing to: {target_node}")

        # Dispatch post-resume event
        dispatch_custom_event(
            "on_hitl_resume",
            {
                "node_name": self.name,
                "action": action,
                "target_node": target_node,
                "has_edit": action == HITL_ACTION_EDIT,
            },
            config=config,
        )

        if action == HITL_ACTION_EDIT:
            # Edit: route to target AND update the state key with the user's edited value
            return Command(
                goto=target_node,
                update={self.edit_state_key: value},
            )
        else:
            # Approve or Reject: pure routing, no state mutation
            return Command(goto=target_node)
