import logging
import pytest
from alita_sdk.runtime.utils.logging import StreamlitCallbackHandler, setup_streamlit_logging, with_streamlit_logs


def test_streamlit_handler_emit(monkeypatch):
    events = {}
    def fake_dispatch(name, data):
        events['name'] = name
        events['data'] = data
    monkeypatch.setattr('alita_sdk.runtime.utils.logging.dispatch_custom_event', fake_dispatch)
    handler = StreamlitCallbackHandler('mytool')
    record = logging.LogRecord('x', logging.INFO, 'f', 1, 'msg', None, None)
    handler.emit(record)
    assert events == {
        'name': 'thinking_step',
        'data': {
            'message': 'msg',
            'tool_name': 'mytool',
            'toolkit': 'logging'
        }
    }


def test_streamlit_handler_ignore_debug(monkeypatch):
    called = False
    def fake_dispatch(*a, **k):
        nonlocal called
        called = True
    monkeypatch.setattr('alita_sdk.runtime.utils.logging.dispatch_custom_event', fake_dispatch)
    handler = StreamlitCallbackHandler()
    record = logging.LogRecord('x', logging.DEBUG, 'f', 1, 'msg', None, None)
    handler.emit(record)
    assert not called


def test_setup_streamlit_logging(monkeypatch):
    monkeypatch.setattr('alita_sdk.runtime.utils.logging.dispatch_custom_event', lambda *a, **k: None)
    logger = logging.getLogger('test_logger')
    logger.handlers.clear()
    handler = setup_streamlit_logging('test_logger', tool_name='t')
    assert isinstance(handler, StreamlitCallbackHandler)
    assert any(isinstance(h, StreamlitCallbackHandler) for h in logger.handlers)


def test_with_streamlit_logs(monkeypatch, caplog):
    events = []
    def fake_dispatch(name, data):
        events.append((name, data))
    monkeypatch.setattr('alita_sdk.runtime.utils.logging.dispatch_custom_event', fake_dispatch)

    @with_streamlit_logs(logger_name='tmp', tool_name='tool')
    def func():
        log = logging.getLogger('tmp')
        log.setLevel(logging.INFO)
        log.info('hi')

    func()
    assert events[0][1]['tool_name'] == 'tool'
