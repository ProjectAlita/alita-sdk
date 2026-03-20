"""Tests for sensitive tools pipeline trust model and clean termination."""
import json
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.tools import BaseTool, StructuredTool

from alita_sdk.runtime.tools.function import (
    FunctionTool,
    PIPELINE_BLOCKED_KEY,
)
from alita_sdk.runtime.middleware.sensitive_tool_guard import (
    SensitiveToolGuardMiddleware,
    _HITL_APPROVED_TOOLS,
)
from alita_sdk.runtime.langchain.langraph_agent import (
    TransitionalEdge,
    ConditionalEdge,
)
from langgraph.graph import END


def _make_mock_tool(tool_name="my_tool"):
    """Create a BaseTool mock with proper name attribute and tool_call_schema."""
    mock = MagicMock(spec=BaseTool)
    mock.name = tool_name
    mock.description = "mock tool"
    mock.tool_call_schema = None
    mock.args_schema = None
    return mock


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_blocked_json(**overrides):
    payload = {
        "type": "sensitive_tool_blocked",
        "status": "blocked",
        "blocked_tool_name": "create_issue",
        "action_label": "github.create_issue",
        "blocked_toolkit_name": "github",
        "message": "Blocked",
    }
    payload.update(overrides)
    return json.dumps(payload)


# ── P0: Clean Termination ────────────────────────────────────────────────

class TestIsBlockedDetection:
    def test_detects_blocked_json(self):
        assert FunctionTool._is_sensitive_tool_blocked(_make_blocked_json())

    def test_rejects_normal_string(self):
        assert not FunctionTool._is_sensitive_tool_blocked("normal result")

    def test_rejects_dict(self):
        assert not FunctionTool._is_sensitive_tool_blocked({"key": "val"})

    def test_rejects_none(self):
        assert not FunctionTool._is_sensitive_tool_blocked(None)

    def test_rejects_empty_string(self):
        assert not FunctionTool._is_sensitive_tool_blocked("")

    def test_rejects_json_without_type(self):
        assert not FunctionTool._is_sensitive_tool_blocked('{"status": "ok"}')

    def test_rejects_json_with_wrong_type(self):
        assert not FunctionTool._is_sensitive_tool_blocked('{"type": "tool_result"}')


class TestBuildBlockedTermination:
    def setup_method(self):
        mock_tool = _make_mock_tool("create_issue")
        self.ft = FunctionTool(
            name="test_node",
            tool=mock_tool,
            output_variables=["issue_result", "messages"],
        )

    def test_returns_blocked_flag(self):
        result = self.ft._build_blocked_termination(_make_blocked_json())
        assert isinstance(result[PIPELINE_BLOCKED_KEY], str)
        assert "blocked" in result[PIPELINE_BLOCKED_KEY].lower()

    def test_nulls_output_variables(self):
        result = self.ft._build_blocked_termination(_make_blocked_json())
        assert result["issue_result"] is None

    def test_has_assistant_message(self):
        result = self.ft._build_blocked_termination(_make_blocked_json())
        assert len(result["messages"]) == 1
        assert "blocked" in result["messages"][0]["content"].lower()

    def test_message_includes_tool_and_node(self):
        result = self.ft._build_blocked_termination(_make_blocked_json(
            action_label="github.create_issue",
            blocked_toolkit_type="github",
        ))
        content = result["messages"][0]["content"]
        assert "create_issue" in content
        assert "test_node" in content
        assert "github" in content
        # The _pipeline_blocked value must also carry the same message
        assert "create_issue" in result[PIPELINE_BLOCKED_KEY]


class TestFunctionToolInvokeBlocked:
    """Test that FunctionTool.invoke() returns clean termination on blocked result."""

    @patch('alita_sdk.runtime.tools.function.convert_to_openai_tool',
           return_value={'function': {'parameters': {'properties': {}}}})
    @patch('alita_sdk.runtime.tools.function.dispatch_custom_event')
    def test_blocked_result_triggers_clean_termination(self, _mock_dispatch, _mock_convert):
        blocked_json = _make_blocked_json()
        mock_tool = _make_mock_tool("create_issue")
        mock_tool.invoke.return_value = blocked_json

        ft = FunctionTool(
            name="test_node",
            tool=mock_tool,
            output_variables=["issue_result"],
            input_mapping={"title": {"type": "fixed", "value": "Test"}},
            input_variables=["messages"],
        )

        result = ft.invoke({"messages": [], "input": "test"})
        assert isinstance(result[PIPELINE_BLOCKED_KEY], str)
        assert "blocked" in result[PIPELINE_BLOCKED_KEY].lower()
        assert result["issue_result"] is None
        assert "blocked" in result["messages"][0]["content"].lower()

    @patch('alita_sdk.runtime.tools.function.convert_to_openai_tool',
           return_value={'function': {'parameters': {'properties': {}}}})
    @patch('alita_sdk.runtime.tools.function.dispatch_custom_event')
    def test_normal_result_passes_through(self, _mock_dispatch, _mock_convert):
        mock_tool = _make_mock_tool("get_issue")
        mock_tool.invoke.return_value = {"number": 42, "title": "Test"}

        ft = FunctionTool(
            name="test_node",
            tool=mock_tool,
            output_variables=["issue_result"],
            input_mapping={"issue_number": {"type": "fixed", "value": "42"}},
            input_variables=["messages"],
        )

        result = ft.invoke({"messages": [], "input": "test"})
        assert PIPELINE_BLOCKED_KEY not in result


# ── P0: Edge routing ─────────────────────────────────────────────────────

class TestTransitionalEdgeBlocked:
    def test_routes_to_end_when_blocked(self):
        edge = TransitionalEdge("next_node")
        state = {"_pipeline_blocked": "Pipeline stopped: blocked.", "messages": []}
        result = edge.invoke(state, config={"callbacks": []})
        assert result == END

    @patch('alita_sdk.runtime.langchain.langraph_agent.dispatch_custom_event')
    def test_routes_normally_when_not_blocked(self, _mock_dispatch):
        edge = TransitionalEdge("next_node")
        state = {"_pipeline_blocked": None, "messages": []}
        result = edge.invoke(state, config={"callbacks": []})
        assert result == "next_node"

    @patch('alita_sdk.runtime.langchain.langraph_agent.dispatch_custom_event')
    def test_routes_normally_when_key_missing(self, _mock_dispatch):
        edge = TransitionalEdge("next_node")
        state = {"messages": []}
        result = edge.invoke(state, config={"callbacks": []})
        assert result == "next_node"


# ── P1: API Trust (trust_sensitive_tools) ────────────────────────────────

class TestApiTrustModel:
    def test_hitl_approved_tools_preapprove(self):
        """set_hitl_approved_tools should cause auto-approve in _review_sensitive_tool_call."""
        from alita_sdk.runtime.middleware.sensitive_tool_guard import (
            set_hitl_approved_tools,
            reset_hitl_approved_tools,
        )
        token = set_hitl_approved_tools({"create_issue", "close_issue"})
        try:
            ctx = {
                "tool_name": "create_issue",
                "toolkit_name": "github",
                "toolkit_type": "github",
                "action_label": "github.create_issue",
                "policy_message": "Approval required",
                "tool_args": {},
            }
            result = SensitiveToolGuardMiddleware._review_sensitive_tool_call(ctx)
            assert result["action"] == "approve"
        finally:
            reset_hitl_approved_tools(token)


# ── Output extraction for _pipeline_blocked ──────────────────────────────

class TestBlockedOutputExtraction:
    """When _pipeline_blocked carries the message string in the graph result,
    the output must be that message, not 'True' from the old bool flag."""

    def test_output_is_blocked_message_not_true(self):
        """_pipeline_blocked now carries the message string directly."""
        blocked_msg = (
            "**Pipeline stopped** — the action **create_issue** "
            "(toolkit type: *github*, node: *github-node*) was **blocked** by user.\n\n"
            "Downstream nodes that depend on `create_issue` output "
            "were skipped to prevent invalid data.\n\n"
            "> **Tip:** Regenerate this message to re-trigger the approval "
            "request and try again."
        )
        result = {
            'input': 'test',
            'messages': [],
            '_pipeline_blocked': blocked_msg,
        }

        # Reproduce the _pipeline_blocked fast path
        _blocked_output = None
        if isinstance(result, dict) and result.get('_pipeline_blocked'):
            _blocked_output = str(result['_pipeline_blocked'])

        assert _blocked_output == blocked_msg, (
            f"Expected blocked termination message but got: {_blocked_output!r}"
        )

    def test_fallback_when_pipeline_blocked_is_none(self):
        """If _pipeline_blocked is None, no blocked output is produced."""
        result = {
            'messages': [],
            '_pipeline_blocked': None,
        }

        _blocked_output = None
        if isinstance(result, dict) and result.get('_pipeline_blocked'):
            _blocked_output = str(result['_pipeline_blocked'])

        assert _blocked_output is None

    def test_old_fallback_would_produce_true(self):
        """Demonstrate the old bug: str(list(result.values())[-1]) == 'True'."""
        result = {
            'input': '',
            'messages': [],
            '_pipeline_blocked': True,
        }
        # The old fallback
        old_output = str(list(result.values())[-1])
        assert old_output == "True", "Confirms the old bug produced literal 'True'"

    def test_blocked_output_survives_exception_in_hitl_detection(self):
        """If get_state() or HITL detection throws, _blocked_output is already
        set before the try block and used as the except-handler output."""
        blocked_msg = "Pipeline stopped: the sensitive action ..."
        result = {
            'messages': [],
            '_pipeline_blocked': blocked_msg,
        }

        # Phase 1: isolated extraction (before try block)
        _blocked_output = None
        if isinstance(result, dict) and result.get('_pipeline_blocked'):
            _blocked_output = str(result['_pipeline_blocked'])

        # Phase 2: simulate exception in the main try block (HITL/printer)
        output = None
        try:
            raise RuntimeError("Simulated get_state() failure")
        except Exception:
            if _blocked_output is not None:
                output = _blocked_output
            else:
                output = str(list(result.values())[-1]) if result else 'Output is undefined'

        assert output == blocked_msg, (
            f"Blocked output must survive exceptions — got: {output!r}"
        )

    def test_blocked_output_with_empty_string(self):
        """An empty string for _pipeline_blocked is falsy, no blocked output."""
        result = {
            'messages': [],
            '_pipeline_blocked': '',
        }

        _blocked_output = None
        if isinstance(result, dict) and result.get('_pipeline_blocked'):
            _blocked_output = str(result['_pipeline_blocked'])

        assert _blocked_output is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
