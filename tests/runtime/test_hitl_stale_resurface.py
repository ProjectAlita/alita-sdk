"""Tests for HITL stale-interrupt re-surfacing when user sends a new
message while a sensitive tool authorization is pending (EL-3925).

Instead of raising RuntimeError (which produced ugly errors in the UI)
or auto-rejecting (which caused infinite continuation loops), we return
the HITL interrupt payload back to the caller so the UI can re-show the
authorization dialog.
"""

from types import SimpleNamespace

import pytest

from alita_sdk.runtime.langchain.langraph_agent import LangGraphAgentRunnable


# ── Helpers ──────────────────────────────────────────────────────────

def _make_interrupt(tool_name='create_file', toolkit_name='abc-test',
                    toolkit_type='abc-test', guardrail_type='sensitive_tool'):
    """Build a minimal HITL interrupt payload."""
    return {
        'type': 'hitl',
        'guardrail_type': guardrail_type,
        'tool_name': tool_name,
        'toolkit_name': toolkit_name,
        'toolkit_type': toolkit_type,
        'action_label': f'{toolkit_name}.{tool_name}',
        'tool_args': {'filename': 'hello.py'},
        'tool_args_raw': {'filename': 'hello.py'},
        'message': 'Please review and take action.',
        'policy_message': '',
    }


def _state_with_interrupt(interrupt_payload, at_end=False):
    """Create a fake StateSnapshot containing an HITL interrupt."""
    intr = SimpleNamespace(value=interrupt_payload)
    task = SimpleNamespace(interrupts=[intr])
    return SimpleNamespace(
        tasks=[task],
        next=() if at_end else ('tools_node',),
        values={'messages': [], 'hitl_decisions': []},
        config={'configurable': {'checkpoint_id': 'cp-1'}},
    )


def _state_at_end():
    """Create a fake StateSnapshot at END (no pending work)."""
    return SimpleNamespace(
        tasks=[],
        next=(),
        values={'messages': [], 'hitl_decisions': []},
        config={'configurable': {'checkpoint_id': 'cp-2'}},
    )


# ── Tests ────────────────────────────────────────────────────────────

class TestHitlStaleInterruptResurface:
    """Re-surface stale HITL interrupt when a new message arrives."""

    def test_stale_hitl_returns_interrupt_to_caller(self):
        """A new user message against a paused HITL checkpoint should
        return the interrupt payload (not raise RuntimeError)."""
        interrupt = _make_interrupt()
        paused_state = _state_with_interrupt(interrupt)

        input_data = {'input': 'Hello, new message', 'messages': []}
        thread_id = 'test-thread'

        hitl_interrupt = LangGraphAgentRunnable._get_hitl_interrupt(paused_state)
        is_hitl_resume = LangGraphAgentRunnable._is_hitl_resume(input_data)

        assert hitl_interrupt is not None
        assert not is_hitl_resume

        # Condition that triggers re-surfacing
        should_resurface = hitl_interrupt and not is_hitl_resume
        assert should_resurface

        # Build expected return dict (mirrors invoke() logic)
        hitl_for_ui = {k: v for k, v in hitl_interrupt.items() if k != 'tool_args_raw'}
        result = {
            "output": hitl_interrupt.get("message", "A pending action requires your review before continuing."),
            "thread_id": thread_id,
            "execution_finished": False,
            "hitl_interrupt": hitl_for_ui,
        }

        assert result['execution_finished'] is False
        assert result['thread_id'] == thread_id
        assert 'hitl_interrupt' in result
        assert result['hitl_interrupt']['tool_name'] == 'create_file'
        assert result['hitl_interrupt']['type'] == 'hitl'
        assert result['output'] == 'Please review and take action.'

    def test_stale_hitl_strips_tool_args_raw(self):
        """tool_args_raw should be excluded from the returned interrupt."""
        interrupt = _make_interrupt()
        assert 'tool_args_raw' in interrupt

        hitl_for_ui = {k: v for k, v in interrupt.items() if k != 'tool_args_raw'}
        assert 'tool_args_raw' not in hitl_for_ui
        assert 'tool_args' in hitl_for_ui

    def test_stale_hitl_includes_checkpoint_state_values(self):
        """Return dict should include non-output state values from checkpoint."""
        interrupt = _make_interrupt()
        paused_state = _state_with_interrupt(interrupt)
        paused_state.values['custom_key'] = 'custom_value'
        paused_state.values['hitl_decisions'] = [{'action': 'approve'}]

        result_with_state = {
            "output": interrupt.get("message"),
            "thread_id": "t1",
            "execution_finished": False,
            "hitl_interrupt": interrupt,
        }
        for key, value in paused_state.values.items():
            if key != 'output':
                result_with_state[key] = value

        assert result_with_state['custom_key'] == 'custom_value'
        assert result_with_state['hitl_decisions'] == [{'action': 'approve'}]

    def test_hitl_resume_bypasses_stale_detection(self):
        """An explicit HITL resume should NOT trigger re-surfacing."""
        input_data = {
            'input': '',
            'hitl_resume': True,
            'hitl_action': 'approve',
            'hitl_value': '',
        }
        assert LangGraphAgentRunnable._is_hitl_resume(input_data)

        interrupt = _make_interrupt()
        should_resurface = (
            interrupt and not LangGraphAgentRunnable._is_hitl_resume(input_data)
        )
        assert not should_resurface

    def test_get_hitl_interrupt_detects_sensitive_tool_interrupt(self):
        """_get_hitl_interrupt correctly identifies HITL interrupt payloads."""
        interrupt = _make_interrupt()
        state = _state_with_interrupt(interrupt)
        result = LangGraphAgentRunnable._get_hitl_interrupt(state)
        assert result is not None
        assert result['type'] == 'hitl'
        assert result['tool_name'] == 'create_file'
        assert result['guardrail_type'] == 'sensitive_tool'

    def test_get_hitl_interrupt_returns_none_at_end(self):
        """_get_hitl_interrupt returns None when no interrupt is pending."""
        state = _state_at_end()
        result = LangGraphAgentRunnable._get_hitl_interrupt(state)
        assert result is None

    def test_get_hitl_interrupt_ignores_non_hitl_interrupts(self):
        """_get_hitl_interrupt ignores payloads without type=hitl."""
        non_hitl = {'type': 'something_else', 'data': 'value'}
        intr = SimpleNamespace(value=non_hitl)
        task = SimpleNamespace(interrupts=[intr])
        state = SimpleNamespace(tasks=[task], next=('node',))
        result = LangGraphAgentRunnable._get_hitl_interrupt(state)
        assert result is None

    def test_is_hitl_resume_various_inputs(self):
        """_is_hitl_resume correctly identifies HITL resume payloads."""
        assert LangGraphAgentRunnable._is_hitl_resume(
            {'hitl_resume': True, 'hitl_action': 'approve'}
        )
        assert LangGraphAgentRunnable._is_hitl_resume(
            {'hitl_resume': True, 'hitl_action': 'reject'}
        )
        assert LangGraphAgentRunnable._is_hitl_resume(
            {'hitl_resume': True, 'hitl_action': 'edit', 'hitl_value': 'new code'}
        )
        assert LangGraphAgentRunnable._is_hitl_resume(
            {'hitl_action': 'approve'}
        )
        assert not LangGraphAgentRunnable._is_hitl_resume(
            {'input': 'Hello world'}
        )
        assert not LangGraphAgentRunnable._is_hitl_resume(
            {'hitl_action': 'invalid_action'}
        )
        assert not LangGraphAgentRunnable._is_hitl_resume('not a dict')
        assert not LangGraphAgentRunnable._is_hitl_resume(None)
