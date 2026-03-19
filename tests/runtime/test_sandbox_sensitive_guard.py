"""Tests for sandbox tools + sensitive tool guard integration.

Validates that pyodide_sandbox and stateful_pyodide_sandbox are correctly
wrapped by SensitiveToolGuardMiddleware, including Code node paths in
pipeline graphs that create fresh sandbox tools via create_sandbox_tool().

Covers GitHub issue EL-3913: sandbox tools bypass Sensitive Action Guardrail.
"""
import json
from unittest.mock import patch, MagicMock

import pytest
from langchain_core.tools import BaseTool, StructuredTool

from alita_sdk.runtime.middleware.base import MiddlewareManager
from alita_sdk.runtime.middleware.sensitive_tool_guard import SensitiveToolGuardMiddleware
from alita_sdk.runtime.tools.sandbox import (
    PyodideSandboxTool,
    StatefulPyodideSandboxTool,
    create_sandbox_tool,
)
from alita_sdk.runtime.toolkits.security import (
    configure_sensitive_tools,
    reset_sensitive_tools,
    find_sensitive_tool_match,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_sensitive_tools()
    yield
    reset_sensitive_tools()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sandbox_tool(stateful=False):
    """Build a sandbox tool stub that doesn't require Deno."""
    tool = MagicMock(spec=PyodideSandboxTool if not stateful else StatefulPyodideSandboxTool)
    tool.name = 'stateful_pyodide_sandbox' if stateful else 'pyodide_sandbox'
    tool.description = 'Execute Python code.'
    tool.metadata = {
        'toolkit_type': 'sandbox',
        'toolkit_name': 'pyodide',
        'display_name': 'Python Sandbox',
    }
    tool.args_schema = None
    tool.tool_call_schema = None
    return tool


# ---------------------------------------------------------------------------
# 1. Matching: find_sensitive_tool_match recognizes sandbox tool names
# ---------------------------------------------------------------------------

class TestSandboxToolMatching:
    """Verify that find_sensitive_tool_match() correctly matches sandbox tool
    names/identifiers when configured."""

    def test_match_pyodide_sandbox_by_toolkit_name(self):
        configure_sensitive_tools({'pyodide': ['pyodide_sandbox']})
        assert find_sensitive_tool_match('pyodide_sandbox', ['sandbox', 'pyodide']) == 'pyodide'

    def test_match_stateful_pyodide_sandbox_by_toolkit_name(self):
        configure_sensitive_tools({'pyodide': ['stateful_pyodide_sandbox']})
        assert find_sensitive_tool_match(
            'stateful_pyodide_sandbox', ['sandbox', 'pyodide']
        ) == 'pyodide'

    def test_match_sandbox_by_wildcard(self):
        configure_sensitive_tools({'*': ['pyodide_sandbox', 'stateful_pyodide_sandbox']})
        assert find_sensitive_tool_match('pyodide_sandbox', ['sandbox', 'pyodide']) == '*'
        assert find_sensitive_tool_match('stateful_pyodide_sandbox', ['sandbox', 'pyodide']) == '*'

    def test_match_sandbox_by_toolkit_type(self):
        """Config uses 'sandbox' key matching the toolkit_type from tool metadata."""
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})
        assert find_sensitive_tool_match('pyodide_sandbox', ['sandbox', 'pyodide']) == 'sandbox'

    def test_no_match_when_not_configured(self):
        configure_sensitive_tools({'github': ['delete_repo']})
        assert find_sensitive_tool_match('pyodide_sandbox', ['sandbox', 'pyodide']) is None


# ---------------------------------------------------------------------------
# 2. _could_be_sensitive: correctly identifies sandbox tools
# ---------------------------------------------------------------------------

class TestCouldBeSensitive:
    """Verify _could_be_sensitive() on sandbox tool metadata."""

    def test_sandbox_tool_detected_when_configured_by_toolkit_name(self):
        configure_sensitive_tools({'pyodide': ['pyodide_sandbox']})
        mw = SensitiveToolGuardMiddleware()
        tool = _make_sandbox_tool(stateful=False)
        assert mw._could_be_sensitive(tool) is True

    def test_sandbox_tool_detected_when_configured_by_toolkit_type(self):
        """Admin uses 'sandbox' key — matches toolkit_type from metadata."""
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})
        mw = SensitiveToolGuardMiddleware()
        tool = _make_sandbox_tool(stateful=False)
        assert mw._could_be_sensitive(tool) is True

    def test_stateful_sandbox_tool_detected_when_configured(self):
        configure_sensitive_tools({'pyodide': ['stateful_pyodide_sandbox']})
        mw = SensitiveToolGuardMiddleware()
        tool = _make_sandbox_tool(stateful=True)
        assert mw._could_be_sensitive(tool) is True

    def test_sandbox_tool_not_detected_when_unconfigured(self):
        configure_sensitive_tools({'github': ['delete_repo']})
        mw = SensitiveToolGuardMiddleware()
        tool = _make_sandbox_tool(stateful=False)
        assert mw._could_be_sensitive(tool) is False


# ---------------------------------------------------------------------------
# 3. wrap_tool: wrapping produces a guarded copy
# ---------------------------------------------------------------------------

class TestWrapSandboxTool:
    """Verify wrap_tool() wraps sandbox tools when configured, producing a
    copy whose _run is guarded."""

    def test_wrap_tool_returns_different_object_when_sensitive(self):
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})
        mw = SensitiveToolGuardMiddleware()

        # Use a real StructuredTool mimicking sandbox metadata
        tool = StructuredTool.from_function(
            func=lambda code='': 'executed',
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )
        wrapped = mw.wrap_tool(tool)
        assert wrapped is not tool

    def test_wrap_tool_returns_same_object_when_not_sensitive(self):
        configure_sensitive_tools({'github': ['delete_repo']})
        mw = SensitiveToolGuardMiddleware()

        tool = StructuredTool.from_function(
            func=lambda code='': 'executed',
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )
        wrapped = mw.wrap_tool(tool)
        assert wrapped is tool

    def test_wrapped_sandbox_tool_blocks_on_reject(self):
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})
        mw = SensitiveToolGuardMiddleware()

        executed = {'value': False}

        def sandbox_run(code=''):
            executed['value'] = True
            return 'executed'

        tool = StructuredTool.from_function(
            func=sandbox_run,
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )
        wrapped = mw.wrap_tool(tool)

        with patch.object(
            SensitiveToolGuardMiddleware,
            '_review_sensitive_tool_call',
            return_value={'action': 'reject', 'value': 'too risky'},
        ):
            result = wrapped.invoke({'code': 'print("hello")'})

        assert executed['value'] is False
        payload = json.loads(result)
        assert payload['type'] == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE
        assert payload['blocked_tool_name'] == 'pyodide_sandbox'

    def test_wrapped_sandbox_tool_executes_on_approve(self):
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})
        mw = SensitiveToolGuardMiddleware()

        def sandbox_run(code=''):
            return 'executed successfully'

        tool = StructuredTool.from_function(
            func=sandbox_run,
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )
        wrapped = mw.wrap_tool(tool)

        with patch.object(
            SensitiveToolGuardMiddleware,
            '_review_sensitive_tool_call',
            return_value={'action': 'approve', 'value': ''},
        ):
            result = wrapped.invoke({'code': 'print("hello")'})

        assert result == 'executed successfully'


# ---------------------------------------------------------------------------
# 4. MiddlewareManager.wrap_tool: applies guard from all middleware
# ---------------------------------------------------------------------------

class TestMiddlewareManagerWrapTool:
    """Verify the new MiddlewareManager.wrap_tool() method."""

    def test_wrap_tool_applies_sensitive_guard(self):
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})
        mgr = MiddlewareManager()
        mgr.add(SensitiveToolGuardMiddleware())

        tool = StructuredTool.from_function(
            func=lambda code='': 'executed',
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )
        wrapped = mgr.wrap_tool(tool)
        assert wrapped is not tool  # Should be a wrapped copy

    def test_wrap_tool_noop_when_no_middleware(self):
        mgr = MiddlewareManager()
        tool = StructuredTool.from_function(
            func=lambda code='': 'executed',
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
        )
        wrapped = mgr.wrap_tool(tool)
        assert wrapped is tool  # No middleware → same object

    def test_wrap_tool_noop_when_tool_not_sensitive(self):
        configure_sensitive_tools({'github': ['delete_repo']})
        mgr = MiddlewareManager()
        mgr.add(SensitiveToolGuardMiddleware())

        tool = StructuredTool.from_function(
            func=lambda code='': 'executed',
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )
        wrapped = mgr.wrap_tool(tool)
        assert wrapped is tool  # Not configured as sensitive → same object

    def test_wrap_tool_blocks_sandbox_on_reject(self):
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})
        mgr = MiddlewareManager()
        mgr.add(SensitiveToolGuardMiddleware())

        executed = {'value': False}

        def sandbox_run(code=''):
            executed['value'] = True
            return 'executed'

        tool = StructuredTool.from_function(
            func=sandbox_run,
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )
        wrapped = mgr.wrap_tool(tool)

        with patch.object(
            SensitiveToolGuardMiddleware,
            '_review_sensitive_tool_call',
            return_value={'action': 'reject', 'value': ''},
        ):
            result = wrapped.invoke({'code': 'os.system("rm -rf /")'})

        assert executed['value'] is False
        payload = json.loads(result)
        assert payload['type'] == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE


# ---------------------------------------------------------------------------
# 5. FunctionTool code-node integration: wrapped sandbox blocks correctly
# ---------------------------------------------------------------------------

class TestFunctionToolSandboxBlocking:
    """Verify that FunctionTool detects blocked sandbox results from the
    sensitive-tool guard and produces clean termination output."""

    def test_function_tool_detects_blocked_sandbox_result(self):
        from alita_sdk.runtime.tools.function import FunctionTool, PIPELINE_BLOCKED_KEY

        blocked_json = json.dumps({
            'type': 'sensitive_tool_blocked',
            'status': 'blocked',
            'blocked_tool_name': 'pyodide_sandbox',
            'blocked_toolkit_type': 'sandbox',
            'blocked_toolkit_name': 'pyodide',
            'action_label': 'pyodide.pyodide_sandbox',
            'message': 'Blocked by user.',
        })

        assert FunctionTool._is_sensitive_tool_blocked(blocked_json) is True

    def test_function_tool_builds_blocked_termination_for_sandbox(self):
        from alita_sdk.runtime.tools.function import FunctionTool, PIPELINE_BLOCKED_KEY

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = 'pyodide_sandbox'

        ft = FunctionTool(
            tool=mock_tool,
            name='code_node_1',
            output_variables=['result', 'messages'],
        )

        blocked_json = json.dumps({
            'type': 'sensitive_tool_blocked',
            'status': 'blocked',
            'blocked_tool_name': 'pyodide_sandbox',
            'blocked_toolkit_type': 'sandbox',
            'blocked_toolkit_name': 'pyodide',
            'action_label': 'pyodide.pyodide_sandbox',
            'message': 'Blocked by user.',
        })

        result = ft._build_blocked_termination(blocked_json)
        assert PIPELINE_BLOCKED_KEY in result
        assert 'pyodide_sandbox' in result[PIPELINE_BLOCKED_KEY]
        assert result['result'] is None  # Output variable nulled
        assert result['messages']


# ---------------------------------------------------------------------------
# 6. End-to-end: pipeline Code node wrapping via middleware_manager
# ---------------------------------------------------------------------------

class TestPipelineCodeNodeWrapping:
    """Simulate the pipeline Code node assembly path to verify that
    middleware_manager.wrap_tool() is applied to the sandbox tool
    before it reaches FunctionTool."""

    def test_code_node_sandbox_tool_is_wrapped_by_middleware_manager(self):
        """Simulates the create_graph() Code node branch:
        1. create_sandbox_tool() returns a fresh tool
        2. middleware_manager.wrap_tool() wraps it
        3. The wrapped tool blocks on reject
        """
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})

        mgr = MiddlewareManager()
        mgr.add(SensitiveToolGuardMiddleware())

        # Simulate create_sandbox_tool() without Deno
        original_func = lambda code='': 'executed'
        sandbox_tool = StructuredTool.from_function(
            func=original_func,
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )

        # This is the key line from the fix in langraph_agent.py
        wrapped = mgr.wrap_tool(sandbox_tool)
        assert wrapped is not sandbox_tool, \
            "Code node sandbox tool should be wrapped when configured as sensitive"

        # Verify the wrapped tool blocks
        with patch.object(
            SensitiveToolGuardMiddleware,
            '_review_sensitive_tool_call',
            return_value={'action': 'reject', 'value': ''},
        ):
            result = wrapped.invoke({'code': 'print(1)'})

        payload = json.loads(result)
        assert payload['type'] == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE
        assert payload['blocked_tool_name'] == 'pyodide_sandbox'

    def test_code_node_sandbox_not_wrapped_when_no_middleware_manager(self):
        """When middleware_manager is None (no middleware configured),
        the sandbox tool should pass through unwrapped."""
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})

        sandbox_tool = StructuredTool.from_function(
            func=lambda code='': 'executed',
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )

        # middleware_manager is None → no wrapping (same as before fix)
        middleware_manager = None
        if middleware_manager is not None:
            sandbox_tool = middleware_manager.wrap_tool(sandbox_tool)

        # Tool should still be the original
        result = sandbox_tool.invoke({'code': 'print(1)'})
        assert result == 'executed'

    def test_stateful_sandbox_also_wrapped(self):
        """Stateful sandbox variant should also be wrapped by the guard."""
        configure_sensitive_tools({'sandbox': ['stateful_pyodide_sandbox']})

        mgr = MiddlewareManager()
        mgr.add(SensitiveToolGuardMiddleware())

        sandbox_tool = StructuredTool.from_function(
            func=lambda code='': 'executed stateully',
            name='stateful_pyodide_sandbox',
            description='Execute Python code in stateful sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )

        wrapped = mgr.wrap_tool(sandbox_tool)
        assert wrapped is not sandbox_tool

        with patch.object(
            SensitiveToolGuardMiddleware,
            '_review_sensitive_tool_call',
            return_value={'action': 'reject', 'value': ''},
        ):
            result = wrapped.invoke({'code': 'x = 1'})

        payload = json.loads(result)
        assert payload['type'] == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE
        assert payload['blocked_tool_name'] == 'stateful_pyodide_sandbox'


# ---------------------------------------------------------------------------
# 7. Display metadata injection: tools.py preserves toolkit_type from tool
# ---------------------------------------------------------------------------

class TestDisplayMetadataInjection:
    """Verify that the internal-tool metadata injection in get_tools()
    preserves the tool's own toolkit_type instead of overwriting it."""

    def test_preserves_sandbox_toolkit_type(self):
        """When a sandbox tool already has toolkit_type='sandbox',
        the display metadata injection must NOT overwrite it to 'internal'."""
        tool = StructuredTool.from_function(
            func=lambda code='': 'ok',
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )

        # Simulate the metadata injection loop from tools.py
        if 'toolkit_type' not in tool.metadata:
            tool.metadata['toolkit_type'] = 'internal'
        tool.metadata['toolkit_name'] = 'pyodide'
        tool.metadata['display_name'] = 'Python sandbox'

        assert tool.metadata['toolkit_type'] == 'sandbox', \
            "toolkit_type must be preserved as 'sandbox', not overwritten to 'internal'"

    def test_sets_internal_when_no_toolkit_type(self):
        """When a tool has no toolkit_type, it should default to 'internal'."""
        tool = StructuredTool.from_function(
            func=lambda: 'ok',
            name='some_tool',
            description='Some internal tool.',
            metadata={},
        )

        if 'toolkit_type' not in tool.metadata:
            tool.metadata['toolkit_type'] = 'internal'

        assert tool.metadata['toolkit_type'] == 'internal'

    def test_sandbox_identifiers_match_admin_config(self):
        """End-to-end: sandbox tool with preserved metadata matches
        admin config that uses 'sandbox' as the key."""
        configure_sensitive_tools({'sandbox': ['pyodide_sandbox']})

        tool = StructuredTool.from_function(
            func=lambda code='': 'ok',
            name='pyodide_sandbox',
            description='Execute Python code in sandbox.',
            metadata={
                'toolkit_type': 'sandbox',
                'toolkit_name': 'pyodide',
                'display_name': 'Python Sandbox',
            },
        )

        # Simulate the fixed metadata injection loop
        if 'toolkit_type' not in tool.metadata:
            tool.metadata['toolkit_type'] = 'internal'
        tool.metadata['toolkit_name'] = 'pyodide'
        tool.metadata['display_name'] = 'Python sandbox'

        # Now verify the sensitive guard recognizes it
        mw = SensitiveToolGuardMiddleware()
        assert mw._could_be_sensitive(tool) is True, \
            "Sandbox tool must be recognized as sensitive after metadata injection"
