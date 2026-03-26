from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver

from alita_sdk.runtime.langchain.assistant import Assistant
from alita_sdk.runtime.middleware.sensitive_tool_guard import SensitiveToolGuardMiddleware
from alita_sdk.runtime.toolkits.security import configure_sensitive_tools, reset_sensitive_tools


def setup_function() -> None:
    reset_sensitive_tools()


def teardown_function() -> None:
    reset_sensitive_tools()


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