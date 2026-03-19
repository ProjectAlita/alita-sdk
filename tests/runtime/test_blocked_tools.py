"""Tests for blocked tools security enforcement across all code paths."""
import json
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.tools import BaseTool, StructuredTool

from alita_sdk.runtime.toolkits.security import (
    configure_blocklist,
    is_tool_blocked,
    is_toolkit_blocked,
    get_blocked_tools_for_toolkit,
    normalize_tool_name,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_blocklist():
    """Reset global blocklist state before each test."""
    configure_blocklist(blocked_toolkits=[], blocked_tools={})
    yield
    configure_blocklist(blocked_toolkits=[], blocked_tools={})


def _make_mock_tool(name: str, toolkit_type: str = "", toolkit_name: str = "") -> MagicMock:
    """Create a mock BaseTool with metadata."""
    mock = MagicMock(spec=BaseTool)
    mock.name = name
    mock.description = f"mock {name}"
    mock.metadata = {}
    if toolkit_type:
        mock.metadata["toolkit_type"] = toolkit_type
    if toolkit_name:
        mock.metadata["toolkit_name"] = toolkit_name
    return mock


# ── Core blocklist checks ────────────────────────────────────────────────

class TestBlocklistConfiguration:
    def test_configure_blocked_tools(self):
        configure_blocklist(blocked_tools={"github": ["create_issue", "delete_repo"]})
        assert is_tool_blocked("github", "create_issue")
        assert is_tool_blocked("github", "delete_repo")
        assert not is_tool_blocked("github", "get_issue")

    def test_configure_blocked_toolkits(self):
        configure_blocklist(blocked_toolkits=["shell"])
        assert is_toolkit_blocked("shell")
        assert not is_toolkit_blocked("github")

    def test_blocked_toolkit_blocks_all_tools(self):
        configure_blocklist(blocked_toolkits=["shell"])
        assert is_tool_blocked("shell", "execute_command")
        assert is_tool_blocked("shell", "any_other_tool")

    def test_case_insensitive(self):
        configure_blocklist(blocked_tools={"GitHub": ["Create_Issue"]})
        assert is_tool_blocked("github", "create_issue")

    def test_tool_name_alias_normalization(self):
        configure_blocklist(blocked_tools={"github": ["create_issue"]})
        # Prefixed variants should also be blocked
        assert is_tool_blocked("github", "github___create_issue")
        assert is_tool_blocked("github", "github:create_issue")

    def test_empty_blocklist(self):
        configure_blocklist(blocked_toolkits=[], blocked_tools={})
        assert not is_tool_blocked("github", "create_issue")
        assert not is_toolkit_blocked("github")


# ── _filter_blocked_tools (tools/__init__.py) ────────────────────────────

class TestFilterBlockedTools:
    def test_filters_blocked_tool_from_toolkit(self):
        from alita_sdk.tools import _filter_blocked_tools
        configure_blocklist(blocked_tools={"github": ["create_issue"]})
        tools = [
            _make_mock_tool("create_issue"),
            _make_mock_tool("get_issue"),
        ]
        result = _filter_blocked_tools(tools, "github")
        assert len(result) == 1
        assert result[0].name == "get_issue"

    def test_passes_through_when_no_blocklist(self):
        from alita_sdk.tools import _filter_blocked_tools
        tools = [_make_mock_tool("create_issue"), _make_mock_tool("get_issue")]
        result = _filter_blocked_tools(tools, "github")
        assert len(result) == 2

    def test_handles_prefixed_tool_names(self):
        from alita_sdk.tools import _filter_blocked_tools
        configure_blocklist(blocked_tools={"github": ["create_issue"]})
        tools = [
            _make_mock_tool("github___create_issue"),
            _make_mock_tool("get_issue"),
        ]
        result = _filter_blocked_tools(tools, "github")
        assert len(result) == 1
        assert result[0].name == "get_issue"


# ── _final_blocked_tools_filter (runtime/toolkits/tools.py) ──────────────

class TestFinalBlockedToolsFilter:
    def test_filters_by_metadata_toolkit_type(self):
        from alita_sdk.runtime.toolkits.tools import _final_blocked_tools_filter
        configure_blocklist(blocked_tools={"github": ["create_issue"]})
        tools = [
            _make_mock_tool("create_issue", toolkit_type="github"),
            _make_mock_tool("get_issue", toolkit_type="github"),
        ]
        result = _final_blocked_tools_filter(tools)
        assert len(result) == 1
        assert result[0].name == "get_issue"

    def test_passes_non_basetool_objects(self):
        from alita_sdk.runtime.toolkits.tools import _final_blocked_tools_filter
        configure_blocklist(blocked_tools={"github": ["create_issue"]})
        tools = ["not_a_tool", 42]
        result = _final_blocked_tools_filter(tools)
        assert len(result) == 2

    def test_passes_tools_without_metadata(self):
        from alita_sdk.runtime.toolkits.tools import _final_blocked_tools_filter
        configure_blocklist(blocked_tools={"github": ["create_issue"]})
        tool = _make_mock_tool("create_issue")
        tool.metadata = {}  # no toolkit_type
        result = _final_blocked_tools_filter([tool])
        # Without toolkit_type we can't match → tool passes through
        assert len(result) == 1


# ── InvokeToolTool blocklist gate (lazy_tools.py) ────────────────────────

class TestInvokeToolBlockedGate:
    def test_invoke_tool_rejects_blocked_tool(self):
        from alita_sdk.runtime.tools.lazy_tools import InvokeToolTool, ToolRegistry

        configure_blocklist(blocked_tools={"github": ["create_issue"]})

        mock_tool = _make_mock_tool("create_issue", toolkit_type="github", toolkit_name="gh")
        registry = ToolRegistry()
        registry._toolkits["gh"] = {"create_issue": mock_tool}
        registry._tool_to_toolkit["create_issue"] = "gh"
        registry._toolkit_types["gh"] = "github"

        invoke = InvokeToolTool(registry=registry)
        result = invoke._run(toolkit="gh", tool="create_issue", arguments={})

        assert "blocked" in result.lower()
        assert "security policy" in result.lower()
        # The actual tool must NOT have been invoked
        mock_tool.invoke.assert_not_called()

    def test_invoke_tool_allows_non_blocked_tool(self):
        from alita_sdk.runtime.tools.lazy_tools import InvokeToolTool, ToolRegistry

        configure_blocklist(blocked_tools={"github": ["delete_repo"]})

        mock_tool = _make_mock_tool("get_issue", toolkit_type="github", toolkit_name="gh")
        mock_tool.invoke.return_value = '{"number": 42}'
        registry = ToolRegistry()
        registry._toolkits["gh"] = {"get_issue": mock_tool}
        registry._tool_to_toolkit["get_issue"] = "gh"
        registry._toolkit_types["gh"] = "github"

        invoke = InvokeToolTool(registry=registry)
        result = invoke._run(toolkit="gh", tool="get_issue", arguments={})

        assert "42" in result
        mock_tool.invoke.assert_called_once()

    def test_invoke_tool_rejects_blocked_toolkit(self):
        from alita_sdk.runtime.tools.lazy_tools import InvokeToolTool, ToolRegistry

        configure_blocklist(blocked_toolkits=["shell"])

        mock_tool = _make_mock_tool("execute", toolkit_type="shell", toolkit_name="sh")
        registry = ToolRegistry()
        registry._toolkits["sh"] = {"execute": mock_tool}
        registry._tool_to_toolkit["execute"] = "sh"
        registry._toolkit_types["sh"] = "shell"

        invoke = InvokeToolTool(registry=registry)
        result = invoke._run(toolkit="sh", tool="execute", arguments={})

        assert "blocked" in result.lower()
        mock_tool.invoke.assert_not_called()
