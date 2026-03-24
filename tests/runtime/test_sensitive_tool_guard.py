import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt
from langgraph.graph.state import CompiledStateGraph

from alita_sdk.runtime.langchain.assistant import Assistant
from alita_sdk.runtime.langchain.langraph_agent import LangGraphAgentRunnable
from alita_sdk.runtime.middleware.sensitive_tool_guard import SensitiveToolGuardMiddleware
from alita_sdk.runtime.middleware.strategies import LoggingStrategy
from alita_sdk.runtime.middleware.tool_exception_handler import ToolExceptionHandlerMiddleware
from alita_sdk.runtime.toolkits.security import configure_sensitive_tools, reset_sensitive_tools
from alita_sdk.runtime.tools.llm import LLMNode


@pytest.fixture(autouse=True)
def reset_sensitive_tools_config():
    reset_sensitive_tools()
    yield
    reset_sensitive_tools()


class FakeLLMClient:
    def __init__(self, final_message: str):
        self.final_message = final_message
        self.bound_tools = []
        self.bound_kwargs = {}
        self.invoke_calls = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = list(tools)
        self.bound_kwargs = dict(kwargs)
        return self

    def invoke(self, messages, config=None):
        self.invoke_calls.append((list(messages), config))
        return AIMessage(content=self.final_message)


class DummyAlitaRuntime:
    def get_mcp_toolkits(self):
        return []


class ResumeReplayLLM:
    def __init__(self):
        self.calls = []
        self.temperature = 0
        self.max_tokens = 1000

    @property
    def _get_model_default_parameters(self):
        return {'temperature': self.temperature, 'max_tokens': self.max_tokens}

    def bind_tools(self, tools, **kwargs):
        return _ResumeReplayLLMBound(self, tools, kwargs)

    def invoke(self, messages, config=None):
        return _ResumeReplayLLMBound(self, [], {}).invoke(messages, config=config)


class _ResumeReplayLLMBound:
    def __init__(self, root, tools, kwargs):
        self.root = root
        self.tools = list(tools)
        self.kwargs = dict(kwargs)

    def invoke(self, messages, config=None):
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        tool_contents = [str(message.content) for message in tool_messages]
        ai_tool_calls = [
            getattr(message, 'tool_calls', None)
            for message in messages
            if isinstance(message, AIMessage)
        ]
        self.root.calls.append(
            {
                'bound_tools': [tool.name for tool in self.tools],
                'tool_contents': tool_contents,
                'ai_tool_calls': ai_tool_calls,
            }
        )

        if {'safe1-ok', 'safe2-ok', 'danger-ok'}.issubset(set(tool_contents)):
            return AIMessage(content='FINAL')

        if 'danger-ok' in tool_contents:
            return AIMessage(
                content='',
                tool_calls=[
                    {'name': 'safe1', 'args': {}, 'id': 'redo-safe1'},
                    {'name': 'safe2', 'args': {}, 'id': 'redo-safe2'},
                ],
            )

        return AIMessage(
            content='',
            tool_calls=[
                {'name': 'safe1', 'args': {}, 'id': 'call-safe1'},
                {'name': 'safe2', 'args': {}, 'id': 'call-safe2'},
                {'name': 'danger', 'args': {}, 'id': 'call-danger'},
            ],
        )


def _build_resume_repro_runnable(memory, llm):
    assistant = Assistant(
        alita=DummyAlitaRuntime(),
        data={'instructions': 'Use tools', 'tools': [], 'meta': {}},
        client=llm,
        tools=[
            StructuredTool.from_function(
                func=lambda: 'safe1-ok',
                name='safe1',
                description='safe1',
                metadata={'toolkit_type': 'dummy', 'toolkit_name': 'dummy', 'tool_name': 'safe1'},
            ),
            StructuredTool.from_function(
                func=lambda: 'safe2-ok',
                name='safe2',
                description='safe2',
                metadata={'toolkit_type': 'dummy', 'toolkit_name': 'dummy', 'tool_name': 'safe2'},
            ),
            StructuredTool.from_function(
                func=lambda: 'danger-ok',
                name='danger',
                description='danger',
                metadata={'toolkit_type': 'dummy', 'toolkit_name': 'dummy', 'tool_name': 'danger'},
            ),
        ],
        memory=memory,
        app_type='predict',
        middleware=[SensitiveToolGuardMiddleware()],
    )
    return assistant.runnable()


def test_hitl_resume_restores_pending_messages_before_replaying_llm():
    configure_sensitive_tools({'dummy': ['danger']})

    memory = MemorySaver()
    thread_config = {'configurable': {'thread_id': 'resume-repro-thread'}}

    initial_llm = ResumeReplayLLM()
    initial_runnable = _build_resume_repro_runnable(memory, initial_llm)

    initial_result = initial_runnable.invoke(
        {'messages': [HumanMessage(content='do the thing')]},
        config=thread_config,
    )

    assert initial_result['execution_finished'] is False
    assert initial_result['hitl_interrupt']['tool_name'] == 'danger'

    resume_llm = ResumeReplayLLM()
    resumed_runnable = _build_resume_repro_runnable(memory, resume_llm)

    resume_result = resumed_runnable.invoke(
        {'hitl_resume': True, 'hitl_action': 'approve', 'hitl_value': ''},
        config={'configurable': {'thread_id': 'resume-repro-thread'}},
    )

    assert resume_result['execution_finished'] is True
    assert resume_result['output'] == 'FINAL'
    assert len(resume_llm.calls) == 1
    assert {'safe1-ok', 'safe2-ok', 'danger-ok'} == set(resume_llm.calls[0]['tool_contents'])
    assert not any(
        tool_call and tool_call[0]['id'].startswith('redo-')
        for tool_call in resume_llm.calls[0]['ai_tool_calls']
        if tool_call
    )


def test_hitl_reject_continues_tool_loop():
    tool = StructuredTool.from_function(
        func=lambda repo: SensitiveToolGuardMiddleware._build_blocked_tool_result(
            action_label='github.delete_repo',
            tool_name='delete_repo',
            toolkit_name='github',
            toolkit_type='github',
        ),
        name='delete_repo',
        description='Delete a repository.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_repo'},
    )
    alternative_tools = [
        StructuredTool.from_function(
            func=lambda repo, result=result: f'{result} for {repo}',
            name=name,
            description=description,
            metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': name},
        )
        for name, description, result in [
            ('get_repo_details', 'Get repository details and current status.', 'details'),
            ('list_open_pull_requests', 'List open pull requests for the repository.', 'pull requests'),
            ('search_repo_issues', 'Search repository issues relevant to the request.', 'issues'),
            ('show_repo_activity', 'Show recent repository activity.', 'activity'),
        ]
    ]
    client = FakeLLMClient('I cannot run that deletion, but I can suggest safer alternatives.')
    node = LLMNode(
        client=client,
        available_tools=[tool, *alternative_tools],
        tool_names=['delete_repo', *(item.name for item in alternative_tools)],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    result = node.invoke(
        {'messages': [HumanMessage(content='Delete the demo repository.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'reject',
                    'tool_name': 'delete_repo',
                    'tool_args': {'repo': 'demo'},
                    'tool_call_id': 'hitl_call_1',
                }
            }
        },
    )

    assert len(client.invoke_calls) >= 1
    invoked_messages, _ = client.invoke_calls[0]
    tool_messages = [message for message in invoked_messages if isinstance(message, ToolMessage)]
    assert tool_messages
    blocked_payload = json.loads(tool_messages[0].content)
    assert blocked_payload['type'] == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE
    assert blocked_payload['status'] == 'blocked'
    assert blocked_payload['blocked_tool_name'] == 'delete_repo'
    assert blocked_payload['equivalent_action_via_other_tool_allowed'] is True
    assert 'continuation_message' not in blocked_payload
    assert 'continuation_hint' not in blocked_payload
    assert 'safe_alternatives' not in blocked_payload
    assert 'recovery_instruction' not in blocked_payload
    assert isinstance(result['messages'][-1], AIMessage)
    assert result['messages'][-1].content == client.final_message
    assert any(
        isinstance(message, HumanMessage)
        and 'This is a continuation turn after the blocked action(s): github.delete_repo.' in message.content
        for messages, _ in client.invoke_calls[1:]
        for message in messages
    )
    # Verify constrained binding: recovery turn bound only alternative tools, not the blocked one
    recovery_tool_names = {t.name for t in client.bound_tools}
    assert 'delete_repo' not in recovery_tool_names
    assert 'get_repo_details' in recovery_tool_names
    assert client.bound_kwargs.get('tool_choice') is None
    assert client.bound_kwargs.get('parallel_tool_calls') is False


def test_sensitive_tool_guard_reject_message_discourages_retry():
    configure_sensitive_tools({'github': ['delete_repo']})
    middleware = SensitiveToolGuardMiddleware()
    executed = {'value': False}

    def delete_repo(repo):
        executed['value'] = True
        return f'deleted {repo}'

    tool = StructuredTool.from_function(
        func=delete_repo,
        name='delete_repo',
        description='Delete a repository.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github'},
    )
    wrapped_tool = middleware.wrap_tool(tool)

    with patch.object(
        SensitiveToolGuardMiddleware,
        '_review_sensitive_tool_call',
        return_value={'action': 'reject', 'value': ''},
    ):
        result = wrapped_tool.invoke({'repo': 'demo'})

    assert executed['value'] is False
    payload = json.loads(result)
    assert payload['type'] == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE
    assert payload['blocked_tool_name'] == 'delete_repo'
    assert payload['blocked_toolkit_name'] == 'github'
    assert payload['retry_allowed'] is False
    assert payload['equivalent_action_via_other_tool_allowed'] is True
    assert "This tool call was skipped and not executed." in payload['message']
    assert 'continuation_message' not in payload
    assert 'continuation_hint' not in payload


def test_sensitive_tool_guard_continuation_guidance_keeps_tool_loop_open():
    node = LLMNode(client=None, lazy_tools_mode=False)
    enriched = node._enrich_blocked_tool_payload(
        blocked_payload={
            'type': SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE,
            'status': 'blocked',
            'blocked_tool_name': 'delete_repo',
            'action_label': 'github.delete_repo',
            'message': "User blocked the sensitive action 'github.delete_repo'. This tool call was skipped and not executed.",
            'retry_allowed': False,
            'equivalent_action_via_other_tool_allowed': True,
        },
    )

    assert 'Rethink the tool strategy' in enriched['continuation_message']
    assert 'other allowed tool calls' in enriched['continuation_message']
    assert 'reviewed separately' in enriched['continuation_message']
    assert 'Continue the tool-using reasoning loop' in enriched['continuation_hint']
    assert 'separate review for that tool call' in enriched['continuation_hint']
    assert 'Do not immediately stop and ask the user' in enriched['continuation_hint']


def test_prefixed_direct_sensitive_tool_still_requires_review():
    configure_sensitive_tools({'elitea_core': ['list_branches_in_repo']})

    prefixed_tool = StructuredTool.from_function(
        func=lambda repo=None: 'should not execute directly',
        name='elitea_core:list_branches_in_repo',
        description='List branches in repo.',
        metadata={'toolkit_name': 'elitea_core', 'toolkit_type': 'elitea_core'},
    )

    middleware = SensitiveToolGuardMiddleware()
    wrapped_tool = middleware.wrap_tool(prefixed_tool)

    with patch.object(
        SensitiveToolGuardMiddleware,
        '_review_sensitive_tool_call',
        return_value={'action': 'reject', 'value': ''},
    ):
        payload = json.loads(wrapped_tool.invoke({'repo': 'demo'}))

    assert payload['type'] == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE
    assert payload['blocked_tool_name'] == 'list_branches_in_repo'


def test_prefixed_followup_tool_is_excluded_when_base_name_is_blocked():
    node = LLMNode(client=None, lazy_tools_mode=False)
    prefixed_tool = StructuredTool.from_function(
        func=lambda repo=None: 'details',
        name='elitea_core:list_branches_in_repo',
        description='List branches in repo.',
        metadata={'toolkit_name': 'elitea_core', 'toolkit_type': 'elitea_core'},
    )

    assert node._is_allowed_followup_tool(
        candidate=prefixed_tool,
        blocked_tool_names={'list_branches_in_repo'},
    ) is False


def test_hitl_reject_uses_continuation_hook_before_allowed_tool_call():
    configure_sensitive_tools({'github': ['delete_repo', 'delete_branch']})

    blocked_tool = StructuredTool.from_function(
        func=lambda repo: SensitiveToolGuardMiddleware._build_blocked_tool_result(
            action_label='github.delete_repo',
            tool_name='delete_repo',
            toolkit_name='github',
            toolkit_type='github',
        ),
        name='delete_repo',
        description='Delete a repository.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_repo'},
    )
    other_sensitive_tool = StructuredTool.from_function(
        func=lambda repo: f'delete branch in {repo}',
        name='delete_branch',
        description='Delete a branch.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_branch'},
    )
    allowed_tool = StructuredTool.from_function(
        func=lambda repo: f'details for {repo}',
        name='get_repo_details',
        description='Get repository details.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'get_repo_details'},
    )

    class ContinuationClient:
        def __init__(self):
            self.bound_tools = []
            self.bound_kwargs = {}
            self.bind_history = []
            self.invoke_calls = []

        def bind_tools(self, tools, **kwargs):
            self.bound_tools = list(tools)
            self.bound_kwargs = dict(kwargs)
            self.bind_history.append((list(self.bound_tools), dict(self.bound_kwargs)))
            return self

        def invoke(self, messages, config=None):
            self.invoke_calls.append((list(messages), dict(self.bound_kwargs), config))
            if any(isinstance(message, ToolMessage) and message.content == 'details for demo' for message in messages):
                return AIMessage(content='Recovered through allowed tool call.')
            if any(
                isinstance(message, HumanMessage)
                and 'This is a continuation turn after the blocked action(s): github.delete_repo.' in message.content
                for message in messages
            ):
                return AIMessage(
                    content='',
                    tool_calls=[{'name': 'get_repo_details', 'args': {'repo': 'demo'}, 'id': 'safe_call_1'}],
                )
            return AIMessage(content='Plain text fallback.')

    client = ContinuationClient()
    node = LLMNode(
        client=client,
        available_tools=[blocked_tool, other_sensitive_tool, allowed_tool],
        tool_names=['delete_repo', 'delete_branch', 'get_repo_details'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    result = node.invoke(
        {'messages': [HumanMessage(content='Delete the demo repository.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'reject',
                    'tool_name': 'delete_repo',
                    'tool_args': {'repo': 'demo'},
                    'tool_call_id': 'hitl_call_1',
                }
            }
        },
    )

    continuation_bindings = [
        (tools, kwargs)
        for tools, kwargs in client.bind_history
        if 'get_repo_details' in [tool.name for tool in tools]
    ]
    assert continuation_bindings
    continuation_tools, continuation_kwargs = continuation_bindings[-1]
    continuation_tool_names = [tool.name for tool in continuation_tools]
    assert 'get_repo_details' in continuation_tool_names
    assert 'delete_branch' in continuation_tool_names
    assert 'delete_repo' not in continuation_tool_names
    assert continuation_kwargs.get('tool_choice') is None
    assert continuation_kwargs['parallel_tool_calls'] is False

    assert any(
        isinstance(message, HumanMessage)
        and 'This is a continuation turn after the blocked action(s): github.delete_repo.' in message.content
        for message in result['messages']
    )

    assert any(
        isinstance(message, AIMessage)
        and getattr(message, 'tool_calls', None)
        and message.tool_calls[0]['name'] == 'get_repo_details'
        for message in result['messages']
    )
    assert any(
        isinstance(message, ToolMessage) and message.content == 'details for demo'
        for message in result['messages']
    )
    assert result['messages'][-1].content == 'Recovered through allowed tool call.'


def test_lazy_mode_uses_continuation_hook_with_real_tools_from_registry():
    """In lazy-tools mode, _get_forced_followup_tools must pull real tools from
    available_tools / tool_registry instead of get_filtered_tools (which returns
    only meta-tools). The continuation hook should then nudge the model back
    into the loop while the actual follow-up tool still resolves via the real
    tool lookup fallbacks."""
    from alita_sdk.runtime.tools.lazy_tools import ToolRegistry

    configure_sensitive_tools({'github': ['delete_repo']})

    blocked_tool = StructuredTool.from_function(
        func=lambda repo: SensitiveToolGuardMiddleware._build_blocked_tool_result(
            action_label='github.delete_repo',
            tool_name='delete_repo',
            toolkit_name='github',
            toolkit_type='github',
        ),
        name='delete_repo',
        description='Delete a repository.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_repo'},
    )
    allowed_tool = StructuredTool.from_function(
        func=lambda repo: f'details for {repo}',
        name='get_repo_details',
        description='Get repository details.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'get_repo_details'},
    )

    # Build a real ToolRegistry so the LLMNode is in full lazy mode.
    tool_registry = ToolRegistry.from_tools([blocked_tool, allowed_tool])

    class LazyContinuationClient:
        def __init__(self):
            self.bind_history = []
            self.invoke_calls = []

        def bind_tools(self, tools, **kwargs):
            self.bind_history.append(([t.name for t in tools], dict(kwargs)))
            return self

        def invoke(self, messages, config=None):
            self.invoke_calls.append(list(messages))
            # If the follow-up tool already ran, return a final text answer.
            if any(isinstance(m, ToolMessage) and m.content == 'details for demo' for m in messages):
                return AIMessage(content='Recovered in lazy mode.')
            if any(
                isinstance(message, HumanMessage)
                and 'This is a continuation turn after the blocked action(s): github.delete_repo.' in message.content
                for message in messages
            ):
                return AIMessage(
                    content='',
                    tool_calls=[{'name': 'get_repo_details', 'args': {'repo': 'demo'}, 'id': 'safe_call_1'}],
                )
            return AIMessage(content='Fallback text.')

    client = LazyContinuationClient()
    node = LLMNode(
        client=client,
        available_tools=[blocked_tool, allowed_tool],
        tool_names=[],
        lazy_tools_mode=True,
        tool_registry=tool_registry,
        input_mapping={},
        output_variables=['messages'],
    )

    result = node.invoke(
        {'messages': [HumanMessage(content='Delete the demo repository.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'reject',
                    'tool_name': 'delete_repo',
                    'tool_args': {'repo': 'demo'},
                    'tool_call_id': 'hitl_call_1',
                }
            }
        },
    )

    # Verify continuation binding happened with the real allowed tool (not meta-tools).
    continuation_bindings = [
        (tools, kwargs)
        for tools, kwargs in client.bind_history
        if 'get_repo_details' in tools
    ]
    assert continuation_bindings, 'Expected at least one blocked-tool continuation bind_tools call'
    continuation_tool_names, continuation_kwargs = continuation_bindings[-1]
    assert 'get_repo_details' in continuation_tool_names
    assert 'delete_repo' not in continuation_tool_names
    assert continuation_kwargs.get('tool_choice') is None
    assert continuation_kwargs['parallel_tool_calls'] is False

    assert any(
        isinstance(message, HumanMessage)
        and 'This is a continuation turn after the blocked action(s): github.delete_repo.' in message.content
        for message in result['messages']
    )

    # Verify the tool was actually executed (resolved via _forced_followup_lookup).
    assert any(
        isinstance(m, ToolMessage) and m.content == 'details for demo'
        for m in result['messages']
    ), "Expected get_repo_details to be executed and produce a ToolMessage"

    assert result['messages'][-1].content == 'Recovered in lazy mode.'


def test_hitl_reject_uses_last_resort_when_no_safe_alternatives_exist():
    tool = StructuredTool.from_function(
        func=lambda repo: SensitiveToolGuardMiddleware._build_blocked_tool_result(
            action_label='github.delete_repo',
            tool_name='delete_repo',
            toolkit_name='github',
            toolkit_type='github',
        ),
        name='delete_repo',
        description='Delete a repository.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_repo'},
    )
    client = FakeLLMClient('Deletion remains blocked without a safe tool alternative.')
    node = LLMNode(
        client=client,
        available_tools=[tool],
        tool_names=['delete_repo'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    result = node.invoke(
        {'messages': [HumanMessage(content='Delete the demo repository.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'reject',
                    'tool_name': 'delete_repo',
                    'tool_args': {'repo': 'demo'},
                    'tool_call_id': 'hitl_call_1',
                }
            }
        },
    )

    invoked_messages, _ = client.invoke_calls[0]
    tool_messages = [message for message in invoked_messages if isinstance(message, ToolMessage)]
    blocked_payload = json.loads(tool_messages[0].content)
    assert blocked_payload['type'] == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE
    assert blocked_payload['blocked_tool_name'] == 'delete_repo'
    assert 'safe_alternatives' not in blocked_payload
    assert 'recovery_instruction' not in blocked_payload
    assert result['messages'][-1].content == 'Deletion remains blocked without a safe tool alternative.'


def test_langgraph_runnable_ignores_stale_hitl_interrupt_after_sensitive_reject_resume():
    runnable = LangGraphAgentRunnable.__new__(LangGraphAgentRunnable)
    runnable.tool_registry = None
    runnable.output_variables = None
    runnable.checkpointer = SimpleNamespace(get_tuple=lambda config: object())

    interrupt_payload = {
        'type': 'hitl',
        'guardrail_type': 'sensitive_tool',
        'message': 'Please approve the sensitive tool call.',
        'tool_name': 'delete_repo',
        'tool_args': {'repo': 'demo'},
        'tool_args_raw': {'repo': 'demo'},
    }

    checkpoint_state = SimpleNamespace(
        next=['agent'],
        tasks=[SimpleNamespace(interrupts=[SimpleNamespace(value=interrupt_payload)])],
        values={'messages': [HumanMessage(content='Delete the demo repository.')]},
    )
    finished_state_with_stale_interrupt = SimpleNamespace(
        next=[],
        tasks=[SimpleNamespace(interrupts=[SimpleNamespace(value=interrupt_payload)])],
        values={'messages': [AIMessage(content='Recovered through allowed tool call.')]},
    )

    state_sequence = [
        checkpoint_state,
        finished_state_with_stale_interrupt,
        finished_state_with_stale_interrupt,
    ]

    def fake_get_state(config):
        return state_sequence.pop(0)

    runnable.get_state = fake_get_state
    runnable.update_state = lambda config, input_data: None

    config = {'configurable': {'thread_id': 'resume-thread'}}
    result_payload = {'messages': [AIMessage(content='Recovered through allowed tool call.')]}

    with patch.object(CompiledStateGraph, 'invoke', return_value=result_payload):
        result = runnable.invoke(
            {
                'hitl_resume': True,
                'hitl_action': 'reject',
                'hitl_value': '',
            },
            config=config,
        )

    assert result['output'] == 'Recovered through allowed tool call.'
    assert result['execution_finished'] is True
    assert 'hitl_interrupt' not in result
    assert config['configurable'].get('_hitl_resume_context') is None


def test_langgraph_runnable_surfaces_new_sensitive_interrupt_after_reject_resume():
    runnable = LangGraphAgentRunnable.__new__(LangGraphAgentRunnable)
    runnable.tool_registry = None
    runnable.output_variables = None
    runnable.checkpointer = SimpleNamespace(get_tuple=lambda config: object())

    first_interrupt_payload = {
        'type': 'hitl',
        'guardrail_type': 'sensitive_tool',
        'message': 'Approve listing branches.',
        'tool_name': 'list_branches_in_repo',
        'tool_args': {'max_count': 100},
        'tool_args_raw': {'max_count': 100},
    }
    second_interrupt_payload = {
        'type': 'hitl',
        'guardrail_type': 'sensitive_tool',
        'message': 'Approve generic GitHub API call.',
        'tool_name': 'generic_github_api_call',
        'tool_args': {'method': 'get_repo'},
        'tool_args_raw': {'method': 'get_repo'},
    }

    checkpoint_state = SimpleNamespace(
        next=['agent'],
        tasks=[SimpleNamespace(interrupts=[SimpleNamespace(value=first_interrupt_payload)])],
        values={'messages': [HumanMessage(content='List branches in repo.')]},
    )
    finished_state_with_new_interrupt = SimpleNamespace(
        next=[],
        tasks=[SimpleNamespace(interrupts=[SimpleNamespace(value=second_interrupt_payload)])],
        values={'messages': [AIMessage(content='[ATTACHMENTS] fallback text that should be ignored.')]},
    )

    state_sequence = [
        checkpoint_state,
        finished_state_with_new_interrupt,
        finished_state_with_new_interrupt,
    ]

    def fake_get_state(config):
        return state_sequence.pop(0)

    runnable.get_state = fake_get_state
    runnable.update_state = lambda config, input_data: None

    config = {'configurable': {'thread_id': 'resume-thread'}}
    result_payload = {'messages': [AIMessage(content='[ATTACHMENTS] fallback text that should be ignored.')]}

    with patch.object(CompiledStateGraph, 'invoke', return_value=result_payload):
        result = runnable.invoke(
            {
                'hitl_resume': True,
                'hitl_action': 'reject',
                'hitl_value': '',
            },
            config=config,
        )

    assert result['output'] == 'Approve generic GitHub API call.'
    assert result['execution_finished'] is False
    assert result['hitl_interrupt']['tool_name'] == 'generic_github_api_call'
    assert config['configurable'].get('_hitl_resume_context') is None


def test_hitl_resume_filters_orphaned_tool_calls_before_recovery_turn():
    tool = StructuredTool.from_function(
        func=lambda repo: SensitiveToolGuardMiddleware._build_blocked_tool_result(
            action_label='github.delete_repo',
            tool_name='delete_repo',
            toolkit_name='github',
            toolkit_type='github',
        ),
        name='delete_repo',
        description='Delete a repository.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_repo'},
    )
    client = FakeLLMClient('Deletion remains blocked without a safe tool alternative.')
    node = LLMNode(
        client=client,
        available_tools=[tool],
        tool_names=['delete_repo'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    node.invoke(
        {
            'messages': [
                HumanMessage(content='Delete the demo repository.'),
                AIMessage(content='', tool_calls=[{
                    'name': 'delete_repo',
                    'args': {'repo': 'demo'},
                    'id': 'orphaned_call_1',
                }]),
            ]
        },
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'reject',
                    'tool_name': 'delete_repo',
                    'tool_args': {'repo': 'demo'},
                    'tool_call_id': 'hitl_call_1',
                }
            }
        },
    )

    invoked_messages, _ = client.invoke_calls[0]
    replayed_tool_call_ids = {
        tool_call.get('id', '')
        for message in invoked_messages
        if isinstance(message, AIMessage) and getattr(message, 'tool_calls', None)
        for tool_call in message.tool_calls
    }
    assert 'orphaned_call_1' not in replayed_tool_call_ids
    assert 'hitl_call_1' in replayed_tool_call_ids


def test_sensitive_tool_guard_system_prompt_guides_alternatives():
    prompt = SensitiveToolGuardMiddleware().get_system_prompt()
    # No sensitive tools configured → no prompt overhead
    assert prompt == ''


def test_sensitive_tool_guard_system_prompt_present_when_configured():
    configure_sensitive_tools({'github': ['delete_repo']})
    prompt = SensitiveToolGuardMiddleware().get_system_prompt()
    assert prompt == ''


def test_assistant_fallback_prioritizes_sensitive_tool_prompt():
    captured = {}

    class DummyClient:
        temperature = 0
        max_tokens = 0

    def fake_create_graph(**kwargs):
        captured['yaml_schema'] = kwargs['yaml_schema']
        return object()

    data = {
        'meta': {},
        'tools': [],
        'instructions': '',
        'variables': [],
    }

    configure_sensitive_tools({'github': ['delete_repo']})

    with patch('alita_sdk.runtime.toolkits.tools.get_tools', return_value=[]), patch(
        'alita_sdk.runtime.langchain.langraph_agent.create_graph',
        side_effect=fake_create_graph,
    ):
        assistant = Assistant(
            alita=object(),
            data=data,
            client=DummyClient(),
            middleware=[SensitiveToolGuardMiddleware()],
        )
        assistant.getLangGraphReactAgent()

    yaml_schema = yaml.safe_load(captured['yaml_schema'])
    template = yaml_schema['nodes'][0]['prompt']['template']
    assert template.startswith(SensitiveToolGuardMiddleware().get_system_prompt())
    assert 'You are **Alita**' in template


def test_assistant_combines_sensitive_and_error_middleware_prompts():
    captured = {}

    class DummyClient:
        temperature = 0
        max_tokens = 0

    def fake_create_graph(**kwargs):
        captured['yaml_schema'] = kwargs['yaml_schema']
        return object()

    data = {
        'meta': {},
        'tools': [],
        'instructions': '',
        'variables': [],
    }

    configure_sensitive_tools({'github': ['delete_repo']})

    with patch('alita_sdk.runtime.toolkits.tools.get_tools', return_value=[]), patch(
        'alita_sdk.runtime.langchain.langraph_agent.create_graph',
        side_effect=fake_create_graph,
    ):
        assistant = Assistant(
            alita=object(),
            data=data,
            client=DummyClient(),
            middleware=[
                SensitiveToolGuardMiddleware(),
                ToolExceptionHandlerMiddleware(strategies=[LoggingStrategy()]),
            ],
        )
        assistant.getLangGraphReactAgent()

    yaml_schema = yaml.safe_load(captured['yaml_schema'])
    template = yaml_schema['nodes'][0]['prompt']['template']
    assert SensitiveToolGuardMiddleware().get_system_prompt() in template
    assert 'You are **Alita**' in template


def test_blocked_tool_visible_payload_omits_internal_enrichment():
    """The ToolMessage payload should stay compact; continuation guidance remains internal."""
    node = LLMNode(client=None, lazy_tools_mode=False)
    payload = node._build_visible_blocked_tool_payload({
        'type': SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE,
        'status': 'blocked',
        'blocked_tool_name': 'delete_repo',
        'action_label': 'github.delete_repo',
        'message': 'blocked',
        'retry_allowed': False,
        'equivalent_action_via_other_tool_allowed': True,
        'continuation_message': 'internal only',
        'continuation_hint': 'internal only',
        'safe_alternatives': [{'tool_name': 'get_repo_details'}],
        'recovery_instruction': 'internal only',
    })
    assert payload['blocked_tool_name'] == 'delete_repo'
    assert 'continuation_message' not in payload
    assert 'continuation_hint' not in payload
    assert 'safe_alternatives' not in payload
    assert 'recovery_instruction' not in payload


def test_hitl_reject_auto_executes_recovery_tool_when_forced():
    tool = StructuredTool.from_function(
        func=lambda repo: SensitiveToolGuardMiddleware._build_blocked_tool_result(
            action_label='github.delete_repo',
            tool_name='delete_repo',
            toolkit_name='github',
            toolkit_type='github',
        ),
        name='delete_repo',
        description='Delete a repository.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_repo'},
    )
    alternative_tool = StructuredTool.from_function(
        func=lambda repo: f'details for {repo}',
        name='get_repo_details',
        description='Get repository details and current status.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'get_repo_details'},
    )

    class RecoveryOnlyCallsWhenForcedClient:
        def __init__(self):
            self.bound_tools = []
            self.bound_kwargs = {}
            self.bind_history = []
            self.invoke_calls = []

        def bind_tools(self, tools, **kwargs):
            self.bound_tools = list(tools)
            self.bound_kwargs = dict(kwargs)
            self.bind_history.append((list(self.bound_tools), dict(kwargs)))
            return self

        def invoke(self, messages, config=None):
            self.invoke_calls.append((list(messages), config))
            tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
            if any(message.content == 'details for demo' for message in tool_messages):
                return AIMessage(content='Recovered via safe alternative.')
            bound_tool_names = [tool.name for tool in self.bound_tools]
            if bound_tool_names == ['get_repo_details']:
                return AIMessage(
                    content='',
                    tool_calls=[{'name': 'get_repo_details', 'args': {'repo': 'demo'}, 'id': 'alt_call_1'}],
                )
            return AIMessage(content='I can suggest get_repo_details if you want.')

    client = RecoveryOnlyCallsWhenForcedClient()
    node = LLMNode(
        client=client,
        available_tools=[tool, alternative_tool],
        tool_names=['delete_repo', 'get_repo_details'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    result = node.invoke(
        {'messages': [HumanMessage(content='Delete the demo repository.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'reject',
                    'tool_name': 'delete_repo',
                    'tool_args': {'repo': 'demo'},
                    'tool_call_id': 'hitl_call_1',
                }
            }
        },
    )

    assert result['messages'][-1].content == 'Recovered via safe alternative.'
    assert any(
        isinstance(message, ToolMessage) and message.content == 'details for demo'
        for message in result['messages']
    )
    assert client.bind_history[-1][1].get('tool_choice') is None


def test_multiple_blocked_sensitive_tools_shrink_rebind_and_replace_nudges():
    configure_sensitive_tools({'github': ['delete_repo', 'delete_branch']})

    blocked_repo_tool = StructuredTool.from_function(
        func=lambda repo: SensitiveToolGuardMiddleware._build_blocked_tool_result(
            action_label='github.delete_repo',
            tool_name='delete_repo',
            toolkit_name='github',
            toolkit_type='github',
        ),
        name='delete_repo',
        description='Delete a repository.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_repo'},
    )
    blocked_branch_tool = StructuredTool.from_function(
        func=lambda repo: SensitiveToolGuardMiddleware._build_blocked_tool_result(
            action_label='github.delete_branch',
            tool_name='delete_branch',
            toolkit_name='github',
            toolkit_type='github',
        ),
        name='delete_branch',
        description='Delete a branch.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_branch'},
    )
    allowed_tool = StructuredTool.from_function(
        func=lambda repo: f'details for {repo}',
        name='get_repo_details',
        description='Get repository details.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'get_repo_details'},
    )

    class MultiBlockContinuationClient:
        def __init__(self):
            self.bound_tools = []
            self.bound_kwargs = {}
            self.bind_history = []
            self.invoke_calls = []

        def bind_tools(self, tools, **kwargs):
            self.bound_tools = list(tools)
            self.bound_kwargs = dict(kwargs)
            self.bind_history.append(([tool.name for tool in self.bound_tools], dict(self.bound_kwargs)))
            return self

        def invoke(self, messages, config=None):
            self.invoke_calls.append((list(messages), dict(self.bound_kwargs), config))

            if any(isinstance(message, ToolMessage) and message.content == 'details for demo' for message in messages):
                return AIMessage(content='Recovered after multiple blocked sensitive tools.')

            has_nudge = any(
                isinstance(message, HumanMessage)
                and 'This is a continuation turn after the blocked action(s):' in message.content
                for message in messages
            )

            blocked_tool_names = []
            for message in messages:
                if not isinstance(message, ToolMessage):
                    continue
                try:
                    payload = json.loads(message.content)
                except Exception:
                    continue
                if payload.get('type') == SensitiveToolGuardMiddleware.BLOCKED_TOOL_RESULT_TYPE:
                    name = payload.get('blocked_tool_name')
                    if name and name not in blocked_tool_names:
                        blocked_tool_names.append(name)

            if has_nudge and blocked_tool_names == ['delete_repo']:
                return AIMessage(
                    content='',
                    tool_calls=[{'name': 'delete_branch', 'args': {'repo': 'demo'}, 'id': 'blocked_branch_call'}],
                )

            if has_nudge and blocked_tool_names == ['delete_repo', 'delete_branch']:
                return AIMessage(
                    content='',
                    tool_calls=[{'name': 'get_repo_details', 'args': {'repo': 'demo'}, 'id': 'safe_call_1'}],
                )

            return AIMessage(content='Fallback text.')

    client = MultiBlockContinuationClient()
    node = LLMNode(
        client=client,
        available_tools=[blocked_repo_tool, blocked_branch_tool, allowed_tool],
        tool_names=['delete_repo', 'delete_branch', 'get_repo_details'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    result = node.invoke(
        {'messages': [HumanMessage(content='Delete the demo repository.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'reject',
                    'tool_name': 'delete_repo',
                    'tool_args': {'repo': 'demo'},
                    'tool_call_id': 'hitl_call_1',
                }
            }
        },
    )

    rebound_bindings = [
        tool_names for tool_names, _ in client.bind_history
        if tool_names and tool_names != ['delete_repo', 'delete_branch', 'get_repo_details']
    ]
    assert rebound_bindings[0] == ['delete_branch', 'get_repo_details']
    assert rebound_bindings[1] == ['get_repo_details']

    continuation_nudges = [
        message for message in result['messages']
        if isinstance(message, HumanMessage)
        and 'This is a continuation turn after the blocked action(s):' in message.content
    ]
    assert len(continuation_nudges) == 1
    assert 'github.delete_repo' in continuation_nudges[0].content
    assert 'github.delete_branch' in continuation_nudges[0].content

    blocked_tool_messages = [
        json.loads(message.content) for message in result['messages']
        if isinstance(message, ToolMessage)
        and isinstance(message.content, str)
        and message.content.startswith('{')
    ]
    assert [payload['blocked_tool_name'] for payload in blocked_tool_messages] == ['delete_repo', 'delete_branch']
    assert any(
        isinstance(message, ToolMessage) and message.content == 'details for demo'
        for message in result['messages']
    )
    assert result['messages'][-1].content == 'Recovered after multiple blocked sensitive tools.'


def test_tool_iteration_preserves_graph_interrupt_from_sync_fallback_after_ainvoke_error():
    tool = StructuredTool.from_function(
        func=lambda repo: f'unexpected {repo}',
        name='generic_github_api_call',
        description='Run a generic GitHub API call.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'generic_github_api_call'},
    )

    async def failing_ainvoke(tool_input, config=None, **kwargs):
        raise AttributeError('AuditLangChainCallback missing run_inline')

    def interrupting_invoke(tool_input, config=None, **kwargs):
        raise GraphInterrupt(('second-sensitive-interrupt',))

    object.__setattr__(tool, 'ainvoke', failing_ainvoke)
    object.__setattr__(tool, 'invoke', interrupting_invoke)

    class SingleToolCallClient:
        def __init__(self):
            self.bound_tools = []
            self.bound_kwargs = {}

        def bind_tools(self, tools, **kwargs):
            self.bound_tools = list(tools)
            self.bound_kwargs = dict(kwargs)
            return self

        def invoke(self, messages, config=None):
            return AIMessage(
                content='',
                tool_calls=[
                    {
                        'name': 'generic_github_api_call',
                        'args': {'repo': 'demo'},
                        'id': 'tool_call_1',
                    }
                ],
            )

    node = LLMNode(
        client=SingleToolCallClient(),
        available_tools=[tool],
        tool_names=['generic_github_api_call'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    with pytest.raises(GraphInterrupt):
        node.invoke({'messages': [HumanMessage(content='Call the generic GitHub API.')]})


def test_multi_block_aggregates_payloads():
    """When multiple tools are blocked in one turn, only the first gets the full payload."""
    from pydantic import create_model

    def _make_blocked(n):
        def _fn(**kwargs):
            return SensitiveToolGuardMiddleware._build_blocked_tool_result(
                action_label=f'github.{n}', tool_name=n, toolkit_name='github', toolkit_type='github',
            )
        return _fn

    blocked_tools = [
        StructuredTool.from_function(
            func=_make_blocked('delete_repo'),
            name='delete_repo',
            description='Delete a repository.',
            args_schema=create_model('DeleteRepoArgs', repo=(str, ...)),
            metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'delete_repo'},
        ),
        StructuredTool.from_function(
            func=_make_blocked('force_push'),
            name='force_push',
            description='Force push to a branch.',
            args_schema=create_model('ForcePushArgs', branch=(str, ...)),
            metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'force_push'},
        ),
    ]
    alt = StructuredTool.from_function(
        func=lambda x: 'details',
        name='get_repo_details',
        description='Get repository details.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'get_repo_details'},
    )

    # FakeLLMClient that issues two tool calls on first invoke, then stops
    class TwoToolCallClient:
        def __init__(self):
            self.invoke_calls = []
            self.bound_tools = []
            self.bound_kwargs = {}
            self._first = True

        def bind_tools(self, tools, **kwargs):
            self.bound_tools = list(tools)
            self.bound_kwargs = dict(kwargs)
            return self

        def invoke(self, messages, config=None):
            self.invoke_calls.append(list(messages))
            if self._first:
                self._first = False
                return AIMessage(content='', tool_calls=[
                    {'name': 'delete_repo', 'args': {'repo': 'demo'}, 'id': 'c1'},
                    {'name': 'force_push', 'args': {'branch': 'main'}, 'id': 'c2'},
                ])
            return AIMessage(content='Both actions are blocked.')

    client = TwoToolCallClient()
    node = LLMNode(
        client=client,
        available_tools=[*blocked_tools, alt],
        tool_names=['delete_repo', 'force_push', 'get_repo_details'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    node.invoke(
        {'messages': [HumanMessage(content='Delete repo and force push.')]},
        config={'configurable': {}},
    )

    # The second invoke (recovery turn) should have tool messages
    recovery_messages = client.invoke_calls[1]
    tool_msgs = [m for m in recovery_messages if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 2
    first_payload = json.loads(tool_msgs[0].content)
    second_payload = json.loads(tool_msgs[1].content)
    assert first_payload['blocked_tool_name'] == 'delete_repo'
    assert second_payload['blocked_tool_name'] == 'force_push'
    assert 'safe_alternatives' not in first_payload
    assert 'continuation_message' not in first_payload
    assert 'continuation_message' not in second_payload


def test_second_resume_approve_consumes_stale_replay_values():
    """Regression: approve on 2nd HITL resume must not get a stale reject value.

    LangGraph replays all previously consumed interrupt/resume values by
    positional index.  When the LLMNode creates a synthetic AIMessage with
    only the current HITL tool, the guard's interrupt() call would land at
    index 0 and receive a stale 'reject' from the first resume.

    The fix consumes the stale replay values before the synthetic AIMessage
    so the guard's interrupt() gets the correct current resume value.
    """
    import dataclasses

    # Build a minimal scratchpad mock to simulate 2nd resume state
    @dataclasses.dataclass
    class FakeScratchpad:
        resume: list
        _counter: int = 0

        def interrupt_counter(self):
            idx = self._counter
            self._counter += 1
            return idx

        def get_null_resume(self, consume=False):
            return None

    # The stale replay value from the 1st resume (reject for list_branches)
    prior_reject = {'action': 'reject', 'value': ''}

    # Guard-wrapped tool that calls interrupt()
    configure_sensitive_tools({'github': ['generic_github_api_call']})

    def do_github_api_call(method='GET', endpoint='/repos'):
        return f'API result: {method} {endpoint}'

    tool = StructuredTool.from_function(
        func=do_github_api_call,
        name='generic_github_api_call',
        description='Generic GitHub API call.',
        metadata={
            'toolkit_type': 'github',
            'toolkit_name': 'github',
            'tool_name': 'generic_github_api_call',
        },
    )

    guard = SensitiveToolGuardMiddleware()
    wrapped_tool = guard.wrap_tool(tool)

    fake_scratchpad = FakeScratchpad(resume=[prior_reject])

    client = FakeLLMClient('Here are the results.')
    node = LLMNode(
        client=client,
        available_tools=[wrapped_tool],
        tool_names=['generic_github_api_call'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    # Simulate 2nd resume: approve generic_github_api_call
    # The scratchpad has 1 stale value [reject]; current resume provides approve
    # Patch interrupt to use our fake scratchpad for replay, then approve
    from langgraph.types import interrupt as real_interrupt

    call_idx = [0]

    def fake_interrupt(value):
        idx = call_idx[0]
        call_idx[0] += 1
        if idx < len(fake_scratchpad.resume):
            # Replay stored value
            return fake_scratchpad.resume[idx]
        # New resume: approve
        approve_val = {'action': 'approve', 'value': ''}
        fake_scratchpad.resume.append(approve_val)
        return approve_val

    with patch(
        'alita_sdk.runtime.tools.llm._langgraph_interrupt',
        side_effect=fake_interrupt,
    ), patch(
        'alita_sdk.runtime.middleware.sensitive_tool_guard.interrupt',
        side_effect=fake_interrupt,
    ):
        result = node.invoke(
            {'messages': [HumanMessage(content='Call the GitHub API.')]},
            config={
                'configurable': {
                    '__pregel_scratchpad': fake_scratchpad,
                    '_hitl_resume_context': {
                        'action': 'approve',
                        'tool_name': 'generic_github_api_call',
                        'tool_args': {'method': 'GET', 'endpoint': '/repos'},
                        'tool_call_id': 'hitl_call_2',
                    },
                }
            },
        )

    # The stale value (idx=0 → reject) must have been consumed by the
    # dummy interrupt calls, NOT by the guard.  The guard should receive
    # the approve value (idx=1) and execute the tool successfully.
    messages = result['messages']
    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    assert tool_msgs, 'Expected at least one ToolMessage in output'
    # The tool should have EXECUTED (not blocked)
    for tm in tool_msgs:
        content = tm.content
        # Should NOT be a blocked payload
        try:
            payload = json.loads(content)
            assert payload.get('type') != 'sensitive_tool_blocked', (
                f'Tool was incorrectly blocked: {content}'
            )
        except (json.JSONDecodeError, TypeError):
            pass  # Not JSON → tool executed and returned text
    # Verify the actual tool result is present
    assert any('API result' in m.content for m in tool_msgs), (
        f'Expected tool execution result, got: {[m.content for m in tool_msgs]}'
    )


def test_state_persisted_hitl_decisions_exclude_blocked_tools():
    """After approving tool 2, the LLM must NOT be offered the previously blocked tool 1.

    hitl_decisions in state carries the reject for tool 1 across checkpoint
    resumes.  __perform_tool_calling reads this and excludes tool 1 from the
    LLM's tool binding when it re-invokes after tool 2 executes.
    """

    # --- Tools ---
    def list_branches(repo='demo'):
        return f'branches of {repo}'

    def generic_api(method='GET', endpoint='/repos'):
        return f'API result: {method} {endpoint}'

    tool_branches = StructuredTool.from_function(
        func=list_branches,
        name='list_branches_in_repo',
        description='List branches.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github',
                  'tool_name': 'list_branches_in_repo'},
    )
    tool_api = StructuredTool.from_function(
        func=generic_api,
        name='generic_github_api_call',
        description='Generic GitHub API call.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github',
                  'tool_name': 'generic_github_api_call'},
    )

    # --- Fake LLM that tries to call the blocked tool after the approved one ---
    class LLMThatTriesToCallBlockedTool:
        def __init__(self):
            self.invoke_calls = []
            self._call_count = 0

        def bind_tools(self, tools, **kwargs):
            # Record which tools are offered to the LLM
            clone = LLMThatTriesToCallBlockedTool()
            clone.invoke_calls = self.invoke_calls
            clone._call_count = self._call_count
            clone._bound_tool_names = {t.name for t in tools}
            return clone

        def invoke(self, messages, config=None):
            self.invoke_calls.append({
                'bound_tool_names': getattr(self, '_bound_tool_names', set()),
            })
            self._call_count += 1
            # After tool 2 results come back, try to call tool 1 (blocked)
            if self._call_count == 1:
                return AIMessage(
                    content='',
                    tool_calls=[{
                        'name': 'list_branches_in_repo',
                        'args': {'repo': 'demo'},
                        'id': 'should_not_work',
                    }],
                )
            return AIMessage(content='Here are the API results.')

    client = LLMThatTriesToCallBlockedTool()

    node = LLMNode(
        client=client,
        available_tools=[tool_branches, tool_api],
        tool_names=['list_branches_in_repo', 'generic_github_api_call'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    # Simulate 2nd resume: approve generic_github_api_call.
    # State carries the reject decision for list_branches_in_repo.
    hitl_decisions = [
        {
            'tool_name': 'list_branches_in_repo',
            'toolkit_name': 'github',
            'toolkit_type': 'github',
            'action': 'reject',
            'action_label': 'github.list_branches_in_repo',
            'user_feedback': '',
        },
    ]

    # Patch interrupt so we don't raise GraphInterrupt
    from unittest.mock import MagicMock
    call_idx = [0]

    def fake_interrupt(value):
        idx = call_idx[0]
        call_idx[0] += 1
        if idx < 1:
            return {'action': 'reject', 'value': ''}
        return {'action': 'approve', 'value': ''}

    with patch(
        'alita_sdk.runtime.tools.llm._langgraph_interrupt',
        side_effect=fake_interrupt,
    ), patch(
        'alita_sdk.runtime.middleware.sensitive_tool_guard.interrupt',
        side_effect=fake_interrupt,
    ):
        import dataclasses

        @dataclasses.dataclass
        class FakeScratchpad:
            resume: list
            _counter: int = 0

            def interrupt_counter(self):
                idx = self._counter
                self._counter += 1
                return idx

            def get_null_resume(self, consume=False):
                return None

        fake_scratchpad = FakeScratchpad(resume=[{'action': 'reject', 'value': ''}])

        result = node.invoke(
            {
                'messages': [HumanMessage(content='Call the GitHub API.')],
                'hitl_decisions': hitl_decisions,
            },
            config={
                'configurable': {
                    '__pregel_scratchpad': fake_scratchpad,
                    '_hitl_resume_context': {
                        'action': 'approve',
                        'tool_name': 'generic_github_api_call',
                        'tool_args': {'method': 'GET', 'endpoint': '/repos'},
                        'tool_call_id': 'hitl_call_2',
                    },
                }
            },
        )

    # The LLM was re-invoked after tool 2 executed.
    # The re-invocation MUST NOT have list_branches_in_repo in the bound tools.
    assert client.invoke_calls, 'Expected at least one LLM invoke call'
    last_invoke = client.invoke_calls[-1]
    bound = last_invoke.get('bound_tool_names', set())
    assert 'list_branches_in_repo' not in bound, (
        f'Blocked tool was offered to LLM in follow-up. Bound tools: {bound}'
    )
    # The result should contain the API call output, not branches
    messages = result['messages']
    assert any('API result' in m.content for m in messages if isinstance(m, ToolMessage)), (
        f'Expected API tool result in output, got: {[m.content for m in messages]}'
    )


def test_auto_approve_skips_interrupt_for_already_authorized_tool():
    """After a tool is authorized, subsequent calls to the same tool in the same
    execution batch must NOT trigger a new interrupt.  The guard should auto-
    approve based on *_HITL_APPROVED_TOOLS* context variable so the user is not
    stuck in an infinite Authorize -> Execute -> Authorize loop.
    """
    from alita_sdk.runtime.middleware.sensitive_tool_guard import (
        SensitiveToolGuardMiddleware,
        set_hitl_approved_tools,
        reset_hitl_approved_tools,
    )

    interrupt_called = []

    def tracking_interrupt(payload):
        """Record every interrupt() call.  Should NOT fire for auto-approved tools."""
        interrupt_called.append(payload)
        return {'action': 'approve', 'value': ''}

    with patch(
        'alita_sdk.runtime.middleware.sensitive_tool_guard.interrupt',
        side_effect=tracking_interrupt,
    ):
        # Create a middleware instance (auto_approve=False, the default)
        guard = SensitiveToolGuardMiddleware.__new__(SensitiveToolGuardMiddleware)
        guard._auto_approve = False

        # A sensitive tool context
        ctx = {
            'tool_name': 'generic_github_api_call',
            'toolkit_name': 'github',
            'toolkit_type': 'github',
            'action_label': 'github.generic_github_api_call',
            'policy_message': 'Authorize?',
            'tool_args': {'method': 'GET', 'endpoint': '/repos'},
        }

        # 1) Without auto-approve, the guard should interrupt.
        review1 = guard._review_sensitive_tool_call(ctx)
        assert review1['action'] == 'approve'
        assert len(interrupt_called) == 1, 'Expected exactly 1 interrupt call before auto-approve'

        # 2) Activate auto-approve for this tool (using qualified identity).
        token = set_hitl_approved_tools({'github.generic_github_api_call'})
        try:
            interrupt_called.clear()
            review2 = guard._review_sensitive_tool_call(ctx)
            assert review2['action'] == 'approve'
            assert len(interrupt_called) == 0, (
                f'Auto-approve should skip interrupt(), but got {len(interrupt_called)} call(s)'
            )
        finally:
            reset_hitl_approved_tools(token)

        # 3) After reset, interrupt should fire again.
        interrupt_called.clear()
        review3 = guard._review_sensitive_tool_call(ctx)
        assert review3['action'] == 'approve'
        assert len(interrupt_called) == 1, 'Expected interrupt to fire again after reset'


def test_auto_approve_disambiguates_across_toolkits():
    """Approving create_issue for jira must NOT auto-approve create_issue for
    github.  The approved set uses qualified identity (toolkit_name.tool_name)
    so identically-named tools in different toolkits remain independent.
    """
    from alita_sdk.runtime.middleware.sensitive_tool_guard import (
        SensitiveToolGuardMiddleware,
        set_hitl_approved_tools,
        reset_hitl_approved_tools,
    )

    interrupt_called = []

    def tracking_interrupt(payload):
        interrupt_called.append(payload)
        return {'action': 'approve', 'value': ''}

    with patch(
        'alita_sdk.runtime.middleware.sensitive_tool_guard.interrupt',
        side_effect=tracking_interrupt,
    ):
        guard = SensitiveToolGuardMiddleware.__new__(SensitiveToolGuardMiddleware)
        guard._auto_approve = False

        jira_ctx = {
            'tool_name': 'create_issue',
            'toolkit_name': 'jira',
            'toolkit_type': 'jira',
            'action_label': 'jira.create_issue',
            'policy_message': 'Approve Jira issue creation?',
            'tool_args': {'project': 'SCRUM'},
        }
        github_ctx = {
            'tool_name': 'create_issue',
            'toolkit_name': 'github',
            'toolkit_type': 'github',
            'action_label': 'github.create_issue',
            'policy_message': 'Approve GitHub issue creation?',
            'tool_args': {'repo': 'org/repo'},
        }

        # Auto-approve only jira.create_issue
        token = set_hitl_approved_tools({'jira.create_issue'})
        try:
            # Jira's create_issue should be auto-approved (no interrupt)
            review_jira = guard._review_sensitive_tool_call(jira_ctx)
            assert review_jira['action'] == 'approve'
            assert len(interrupt_called) == 0, (
                'Jira create_issue should be auto-approved without interrupt'
            )

            # GitHub's create_issue must still trigger an interrupt
            interrupt_called.clear()
            review_github = guard._review_sensitive_tool_call(github_ctx)
            assert review_github['action'] == 'approve'
            assert len(interrupt_called) == 1, (
                'GitHub create_issue should NOT be auto-approved '
                'when only jira.create_issue was approved'
            )
        finally:
            reset_hitl_approved_tools(token)


def test_auto_approve_flag_bypasses_interrupt():
    """When auto_approve=True on the middleware, _review_sensitive_tool_call
    should return approve immediately without calling interrupt()."""
    from alita_sdk.runtime.middleware.sensitive_tool_guard import (
        SensitiveToolGuardMiddleware,
    )

    interrupt_called = []

    def tracking_interrupt(payload):
        interrupt_called.append(payload)
        return {'action': 'approve', 'value': ''}

    with patch(
        'alita_sdk.runtime.middleware.sensitive_tool_guard.interrupt',
        side_effect=tracking_interrupt,
    ):
        # Create a middleware instance with auto_approve=True
        guard = SensitiveToolGuardMiddleware.__new__(SensitiveToolGuardMiddleware)
        guard._auto_approve = True

        ctx = {
            'tool_name': 'generic_github_api_call',
            'toolkit_name': 'github',
            'toolkit_type': 'github',
            'action_label': 'github.generic_github_api_call',
            'policy_message': 'Authorize?',
            'tool_args': {'method': 'GET', 'endpoint': '/repos'},
        }

        review = guard._review_sensitive_tool_call(ctx)
        assert review['action'] == 'approve'
        assert len(interrupt_called) == 0, (
            'auto_approve=True should bypass interrupt() entirely'
        )


def test_hitl_decisions_reducer_appends_and_clears():
    """The custom reducer for hitl_decisions should append on list and clear on None."""
    from alita_sdk.runtime.langchain.utils import _hitl_decisions_reducer

    # Append to empty
    assert _hitl_decisions_reducer(None, [{'action': 'reject'}]) == [{'action': 'reject'}]

    # Append to existing
    result = _hitl_decisions_reducer(
        [{'action': 'reject'}],
        [{'action': 'approve'}],
    )
    assert result == [{'action': 'reject'}, {'action': 'approve'}]

    # Clear
    assert _hitl_decisions_reducer([{'action': 'reject'}], None) == []

    # Clear on empty
    assert _hitl_decisions_reducer(None, None) == []

    # Append empty list (no-op)
    assert _hitl_decisions_reducer([{'action': 'reject'}], []) == [{'action': 'reject'}]


# ── Resume context toolkit disambiguation (Root Cause 1 of #3966) ────


def test_hitl_resume_context_ignored_when_toolkit_differs():
    """When _hitl_resume_context carries a toolkit_name that does not match
    any tool in this LLM node, the context must be discarded and the LLM
    should be called normally (no synthetic tool call)."""
    github_tool = StructuredTool.from_function(
        func=lambda title, repo: f'created {title} in {repo}',
        name='create_issue',
        description='Create a GitHub issue.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github-testing', 'tool_name': 'create_issue'},
    )
    client = FakeLLMClient('Done, I have summarised the results.')
    node = LLMNode(
        client=client,
        available_tools=[github_tool],
        tool_names=['create_issue'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    # Resume context from a JIRA toolkit node — should be ignored
    result = node.invoke(
        {'messages': [HumanMessage(content='Summarise what happened.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'approve',
                    'tool_name': 'create_issue',
                    'toolkit_name': 'SCRUMJira',
                    'tool_args': {'issue_json': '{"project": "SCRUM"}'},
                    'tool_call_id': 'hitl_call_jira',
                }
            }
        },
    )

    # LLM should have been invoked (no synthetic tool call bypass)
    assert len(client.invoke_calls) >= 1
    # The final message should be from the LLM, not a tool result
    assert isinstance(result['messages'][-1], AIMessage)
    assert result['messages'][-1].content == client.final_message


def test_hitl_resume_context_honoured_when_toolkit_matches():
    """When _hitl_resume_context toolkit_name matches a tool in this LLM
    node, the synthetic tool call should be created (approve flow)."""
    github_tool = StructuredTool.from_function(
        func=lambda title, repo: f'created {title} in {repo}',
        name='create_issue',
        description='Create a GitHub issue.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github-testing', 'tool_name': 'create_issue'},
    )
    client = FakeLLMClient('Issue created successfully.')
    node = LLMNode(
        client=client,
        available_tools=[github_tool],
        tool_names=['create_issue'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    result = node.invoke(
        {'messages': [HumanMessage(content='Create an issue.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'approve',
                    'tool_name': 'create_issue',
                    'toolkit_name': 'github-testing',
                    'tool_args': {'title': 'Bug fix', 'repo': 'org/repo'},
                    'tool_call_id': 'hitl_call_gh',
                }
            }
        },
    )

    # A synthetic AI → Tool message pair should exist before the LLM call
    tool_msgs = [m for m in result['messages'] if isinstance(m, ToolMessage)]
    assert tool_msgs, 'Expected synthetic tool execution from matched resume context'


def test_hitl_resume_context_fallback_without_toolkit_name():
    """Backward compatibility: when _hitl_resume_context lacks toolkit_name,
    the bare tool_name check is used (existing behaviour)."""
    tool = StructuredTool.from_function(
        func=lambda repo: f'details for {repo}',
        name='get_repo_details',
        description='Get repo details.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'get_repo_details'},
    )
    client = FakeLLMClient('Here are the details.')
    node = LLMNode(
        client=client,
        available_tools=[tool],
        tool_names=['get_repo_details'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    # No toolkit_name in resume context → fallback to name match
    result = node.invoke(
        {'messages': [HumanMessage(content='Show repo.')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'approve',
                    'tool_name': 'get_repo_details',
                    'tool_args': {'repo': 'org/repo'},
                    'tool_call_id': 'hitl_call_fallback',
                }
            }
        },
    )

    tool_msgs = [m for m in result['messages'] if isinstance(m, ToolMessage)]
    assert tool_msgs, 'Expected synthetic tool execution from fallback name match'


def test_hitl_resume_context_discarded_when_bare_name_foreign():
    """When _hitl_resume_context has no toolkit_name and the tool_name does
    not belong to this LLM node, the context must be discarded (fallback
    negative path)."""
    tool = StructuredTool.from_function(
        func=lambda repo: f'details for {repo}',
        name='get_repo_details',
        description='Get repo details.',
        metadata={'toolkit_type': 'github', 'toolkit_name': 'github', 'tool_name': 'get_repo_details'},
    )
    client = FakeLLMClient('Here is a summary.')
    node = LLMNode(
        client=client,
        available_tools=[tool],
        tool_names=['get_repo_details'],
        lazy_tools_mode=False,
        input_mapping={},
        output_variables=['messages'],
    )

    # Resume context for a tool this node does not own, no toolkit_name
    result = node.invoke(
        {'messages': [HumanMessage(content='What happened?')]},
        config={
            'configurable': {
                '_hitl_resume_context': {
                    'action': 'approve',
                    'tool_name': 'create_issue',
                    'tool_args': {'project': 'SCRUM'},
                    'tool_call_id': 'hitl_call_foreign',
                }
            }
        },
    )

    # LLM should be called normally, no synthetic tool execution
    assert len(client.invoke_calls) >= 1
    assert isinstance(result['messages'][-1], AIMessage)
    assert result['messages'][-1].content == client.final_message
