"""Sensitive tool authorization guard middleware."""

import types
from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import interrupt

from .base import Middleware
from ..tools.application import Application
from ..toolkits.security import get_sensitive_tool_policy, has_sensitive_tools_config, find_sensitive_tool_match


def normalize_tool_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """Normalize tool arguments into a single payload."""
    if kwargs:
        return kwargs
    if len(args) == 1:
        return args[0]
    if not args:
        return {}
    return list(args)


class SensitiveToolGuardMiddleware(Middleware):
    """Pause execution before running configured sensitive tools."""

    def __init__(
        self,
        conversation_id: Optional[str] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
        **kwargs,
    ):
        super().__init__(conversation_id=conversation_id, callbacks=callbacks, **kwargs)
        self._wrapped_tools_cache: Dict[int, BaseTool] = {}

    def get_tools(self) -> List[BaseTool]:
        return []

    def get_system_prompt(self) -> str:
        return ""

    @staticmethod
    def _get_tool_metadata_value(tool: BaseTool, *keys: str) -> Optional[str]:
        metadata = getattr(tool, 'metadata', None) or {}
        for key in keys:
            value = metadata.get(key)
            if value:
                return str(value)
        return None

    @staticmethod
    def _get_tool_function(tool: BaseTool) -> Callable:
        if hasattr(tool, 'func') and callable(tool.func):
            return tool.func
        if hasattr(tool, '_run') and callable(tool._run):
            return tool._run
        if callable(tool):
            return tool
        raise ValueError(f"Cannot extract callable from tool '{tool.name}'")

    @staticmethod
    def _get_async_tool_function(tool: BaseTool) -> Optional[Callable]:
        if hasattr(tool, 'coroutine') and callable(tool.coroutine):
            return tool.coroutine
        if tool.__class__._arun is not BaseTool._arun and hasattr(tool, '_arun') and callable(tool._arun):
            return tool._arun
        return None

    @staticmethod
    def _mask_sensitive_tool_args(value: Any, field_name: Optional[str] = None) -> Any:
        sensitive_markers = (
            'password',
            'secret',
            'token',
            'api_key',
            'apikey',
            'authorization',
            'credential',
            'private_key',
            'access_key',
            'client_secret',
            'refresh_token',
            'session_token',
            'cookie',
            'pat',
        )

        normalized_field_name = str(field_name or '').strip().lower()
        if normalized_field_name and any(marker in normalized_field_name for marker in sensitive_markers):
            return '***'

        if isinstance(value, dict):
            return {
                key: SensitiveToolGuardMiddleware._mask_sensitive_tool_args(item, key)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [SensitiveToolGuardMiddleware._mask_sensitive_tool_args(item, field_name) for item in value]
        if isinstance(value, tuple):
            return tuple(SensitiveToolGuardMiddleware._mask_sensitive_tool_args(item, field_name) for item in value)

        return value

    def _build_sensitive_tool_context(self, tool_to_execute: BaseTool, tool_input: Any) -> Optional[dict[str, Any]]:
        toolkit_name = self._get_tool_metadata_value(tool_to_execute, 'toolkit_name')
        toolkit_type = self._get_tool_metadata_value(tool_to_execute, 'toolkit_type', 'type')
        resolved_tool_name = self._get_tool_metadata_value(tool_to_execute, 'tool_name') or tool_to_execute.name
        display_args: Any = tool_input

        if tool_to_execute.name == 'invoke_tool' and isinstance(tool_input, dict):
            toolkit_name = str(tool_input.get('toolkit') or '') or toolkit_name
            resolved_tool_name = str(tool_input.get('tool') or '') or resolved_tool_name
            display_args = tool_input.get('arguments', {}) or {}
            registry = getattr(tool_to_execute, 'registry', None)
            if registry and toolkit_name:
                toolkit_type = registry.get_toolkit_type(toolkit_name) or toolkit_type

        if not resolved_tool_name:
            return None

        toolkit_label = toolkit_name or toolkit_type or 'this toolkit'
        policy = get_sensitive_tool_policy(
            tool_name=resolved_tool_name,
            toolkit_identifiers=[toolkit_type, toolkit_name],
            toolkit_label=toolkit_label,
        )
        if not policy:
            return None

        return {
            'tool_name': resolved_tool_name,
            'toolkit_name': toolkit_name,
            'toolkit_type': toolkit_type,
            'action_label': policy['action_name'],
            'policy_message': policy['policy_message'],
            'tool_args': self._mask_sensitive_tool_args(display_args),
            'tool_args_raw': display_args,
        }

    @staticmethod
    def _review_sensitive_tool_call(sensitive_tool_context: dict[str, Any]) -> dict[str, str]:
        interrupt_payload = {
            'type': 'hitl',
            'guardrail_type': 'sensitive_tool',
            'node_name': 'sensitive_tool_guard',
            'message': sensitive_tool_context['policy_message'],
            'available_actions': ['approve', 'reject'],
            'routes': {},
            'tool_name': sensitive_tool_context['tool_name'],
            'toolkit_name': sensitive_tool_context['toolkit_name'],
            'toolkit_type': sensitive_tool_context['toolkit_type'],
            'action_label': sensitive_tool_context['action_label'],
            'tool_args': sensitive_tool_context['tool_args'],
            'tool_args_raw': sensitive_tool_context.get('tool_args_raw', sensitive_tool_context['tool_args']),
            'policy_message': sensitive_tool_context['policy_message'],
        }

        resume_value = interrupt(interrupt_payload)
        if not isinstance(resume_value, dict):
            return {'action': 'approve', 'value': str(resume_value or '')}

        action = str(resume_value.get('action', 'approve')).strip().lower()
        if action not in {'approve', 'reject'}:
            action = 'approve'

        return {
            'action': action,
            'value': str(resume_value.get('value', '') or ''),
        }

    def _could_be_sensitive(self, tool: BaseTool) -> bool:
        """Quick check whether a tool could match any sensitive tools config entry."""
        tool_name = self._get_tool_metadata_value(tool, 'tool_name') or tool.name
        toolkit_name = self._get_tool_metadata_value(tool, 'toolkit_name')
        toolkit_type = self._get_tool_metadata_value(tool, 'toolkit_type', 'type')
        identifiers = [i for i in [toolkit_type, toolkit_name] if i]
        if find_sensitive_tool_match(tool_name, identifiers) is not None:
            return True
        # invoke_tool (lazy mode) can invoke any tool dynamically
        if tool.name == 'invoke_tool':
            return True
        return False

    @staticmethod
    def _rebind_invoke_after_copy(copied: BaseTool) -> None:
        """Re-bind any instance-level ``invoke`` method to the new copy.

        ``_patch_tool_invoke`` uses ``types.MethodType`` to bind a metadata-
        forwarding wrapper to a specific tool instance.  ``model_copy()``
        preserves this bound method in ``__dict__``, but it remains bound to
        the *original* instance — so ``invoke()`` on the copy routes execution
        back to the original, bypassing ``_run``/``func`` patches on the copy.
        """
        if 'invoke' in copied.__dict__:
            stale = copied.__dict__['invoke']
            if callable(stale) and hasattr(stale, '__func__'):
                object.__setattr__(
                    copied, 'invoke',
                    types.MethodType(stale.__func__, copied),
                )

    def wrap_tool(self, tool: BaseTool) -> BaseTool:
        if not has_sensitive_tools_config():
            return tool

        if not self._could_be_sensitive(tool):
            return tool

        cache_key = id(tool)
        if cache_key in self._wrapped_tools_cache:
            return self._wrapped_tools_cache[cache_key]

        # Use model_copy to preserve the exact tool type, class, and all attributes.
        # Only the execution functions (_run/_arun or func/coroutine) are replaced.
        guard = self
        original_tool = tool

        if isinstance(tool, StructuredTool) and hasattr(tool, 'func'):
            copied = tool.model_copy()
            self._rebind_invoke_after_copy(copied)
            original_func = tool.func
            original_coroutine = getattr(tool, 'coroutine', None)

            def guarded_func(*args: Any, **kwargs: Any) -> Any:
                tool_input = normalize_tool_input(args, kwargs)
                ctx = guard._build_sensitive_tool_context(original_tool, tool_input)
                if ctx:
                    review = guard._review_sensitive_tool_call(ctx)
                    if review['action'] == 'reject':
                        return review['value'] or (
                            f"User blocked the sensitive action '{ctx['action_label']}'."
                        )
                return original_func(*args, **kwargs)

            copied.func = guarded_func

            if original_coroutine is not None:
                async def guarded_coroutine(*args: Any, **kwargs: Any) -> Any:
                    tool_input = normalize_tool_input(args, kwargs)
                    ctx = guard._build_sensitive_tool_context(original_tool, tool_input)
                    if ctx:
                        review = guard._review_sensitive_tool_call(ctx)
                        if review['action'] == 'reject':
                            return review['value'] or (
                                f"User blocked the sensitive action '{ctx['action_label']}'."
                            )
                    return await original_coroutine(*args, **kwargs)

                copied.coroutine = guarded_coroutine

            self._wrapped_tools_cache[cache_key] = copied
            return copied

        if isinstance(tool, Application):
            copied = tool.model_copy()
            self._rebind_invoke_after_copy(copied)
            original_invoke = tool.invoke
            original_ainvoke = tool.ainvoke

            def guarded_invoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
                ctx = guard._build_sensitive_tool_context(original_tool, input)
                if ctx:
                    review = guard._review_sensitive_tool_call(ctx)
                    if review['action'] == 'reject':
                        return review['value'] or (
                            f"User blocked the sensitive action '{ctx['action_label']}'."
                        )
                return original_invoke(input, config=config, **kwargs)

            async def guarded_ainvoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
                ctx = guard._build_sensitive_tool_context(original_tool, input)
                if ctx:
                    review = guard._review_sensitive_tool_call(ctx)
                    if review['action'] == 'reject':
                        return review['value'] or (
                            f"User blocked the sensitive action '{ctx['action_label']}'."
                        )
                return await original_ainvoke(input, config=config, **kwargs)

            copied.invoke = guarded_invoke
            copied.ainvoke = guarded_ainvoke
            self._wrapped_tools_cache[cache_key] = copied
            return copied

        # Generic BaseTool subclass (e.g. BaseAction): patch _run/_arun on a copy
        copied = tool.model_copy()
        self._rebind_invoke_after_copy(copied)
        original_run = tool._run
        original_async_func = self._get_async_tool_function(tool)

        def guarded_run(*args: Any, run_manager: Any = None, **kwargs: Any) -> Any:
            tool_input = normalize_tool_input(args, kwargs)
            ctx = guard._build_sensitive_tool_context(original_tool, tool_input)
            if ctx:
                review = guard._review_sensitive_tool_call(ctx)
                if review['action'] == 'reject':
                    return review['value'] or (
                        f"User blocked the sensitive action '{ctx['action_label']}'."
                    )
            return original_run(*args, run_manager=run_manager, **kwargs)

        # Set as instance attribute to shadow the class method
        copied._run = guarded_run

        if original_async_func is not None:
            async def guarded_arun(*args: Any, run_manager: Any = None, **kwargs: Any) -> Any:
                tool_input = normalize_tool_input(args, kwargs)
                ctx = guard._build_sensitive_tool_context(original_tool, tool_input)
                if ctx:
                    review = guard._review_sensitive_tool_call(ctx)
                    if review['action'] == 'reject':
                        return review['value'] or (
                            f"User blocked the sensitive action '{ctx['action_label']}'."
                        )
                return await original_async_func(*args, run_manager=run_manager, **kwargs)

            copied._arun = guarded_arun

        self._wrapped_tools_cache[cache_key] = copied
        return copied
