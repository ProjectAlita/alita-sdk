import logging
import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import sys

import alita_sdk.runtime.utils.logging as logmod


class DummyEvent:
    def __init__(self):
        self.events = []

    def __call__(self, name, data):
        self.events.append((name, data))


def test_streamlit_callback_handler_emit(monkeypatch):
    dummy = DummyEvent()
    # Patch the dispatch_custom_event function in module
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    handler = logmod.StreamlitCallbackHandler(tool_name='testtool')
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    # Debug should be ignored
    record_debug = logging.LogRecord(name="test", level=logging.DEBUG, pathname=__file__, lineno=1,
                                     msg="debug msg", args=(), exc_info=None)
    handler.emit(record_debug)
    assert dummy.events == []
    # Info should dispatch
    record_info = logging.LogRecord(name="test", level=logging.INFO, pathname=__file__, lineno=2,
                                    msg="info msg", args=(), exc_info=None)
    handler.emit(record_info)
    assert len(dummy.events) == 1
    name, data = dummy.events[0]
    assert name == 'thinking_step'
    assert data['message'].endswith('INFO: info msg')
    assert data['tool_name'] == 'testtool'


def test_streamlit_callback_handler_different_levels(monkeypatch):
    """Test that different log levels are handled correctly"""
    dummy = DummyEvent()
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    handler = logmod.StreamlitCallbackHandler(tool_name='testlevel')
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    
    # Test WARNING level
    record_warning = logging.LogRecord(name="test", level=logging.WARNING, pathname=__file__, lineno=3,
                                      msg="warning msg", args=(), exc_info=None)
    handler.emit(record_warning)
    assert len(dummy.events) == 1
    
    # Test ERROR level
    record_error = logging.LogRecord(name="test", level=logging.ERROR, pathname=__file__, lineno=4,
                                    msg="error msg", args=(), exc_info=None)
    handler.emit(record_error)
    assert len(dummy.events) == 2
    
    # Test CRITICAL level
    record_critical = logging.LogRecord(name="test", level=logging.CRITICAL, pathname=__file__, lineno=5,
                                       msg="critical msg", args=(), exc_info=None)
    handler.emit(record_critical)
    assert len(dummy.events) == 3


def test_streamlit_callback_handler_default_tool_name(monkeypatch):
    """Test StreamlitCallbackHandler with default tool name"""
    dummy = DummyEvent()
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    handler = logmod.StreamlitCallbackHandler()  # No tool_name provided
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    
    record_info = logging.LogRecord(name="test", level=logging.INFO, pathname=__file__, lineno=1,
                                   msg="test msg", args=(), exc_info=None)
    handler.emit(record_info)
    assert len(dummy.events) == 1
    name, data = dummy.events[0]
    assert data['tool_name'] == 'logging'  # Default value


def test_streamlit_callback_handler_with_args(monkeypatch):
    """Test logging with formatted arguments"""
    dummy = DummyEvent()
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    handler = logmod.StreamlitCallbackHandler(tool_name='testargs')
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    
    record_info = logging.LogRecord(name="test", level=logging.INFO, pathname=__file__, lineno=1,
                                   msg="Hello %s, you have %d messages", args=("John", 5), exc_info=None)
    handler.emit(record_info)
    assert len(dummy.events) == 1
    name, data = dummy.events[0]
    assert "Hello John, you have 5 messages" in data['message']


def test_setup_streamlit_logging_and_with_streamlit_logs(monkeypatch, caplog):
    dummy = DummyEvent()
    # patch module dispatch
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    # Use a custom logger
    logger_name = 'my.logger'
    logger = logging.getLogger(logger_name)
    # Ensure no handlers initially
    for h in list(logger.handlers):
        logger.removeHandler(h)
    # Setup handler via setup_streamlit_logging
    handler = logmod.setup_streamlit_logging(logger_name=logger_name, tool_name='toolA')
    assert isinstance(handler, logmod.StreamlitCallbackHandler)
    # Log an info message
    logger.info('hello world')
    # dispatch should be called once
    assert dummy.events, "No events dispatched"
    name, data = dummy.events[-1]
    assert 'hello world' in data['message']  # Should contain the log message
    # Test decorator
    @logmod.with_streamlit_logs(logger_name=logger_name, tool_name='toolB')
    def fn():
        logging.getLogger(logger_name).info('decorated')
        return 'ok'
    result = fn()
    assert result == 'ok'
    # Last event corresponds to decorated call
    assert dummy.events[-1][1]['tool_name'] == 'toolB'


def test_setup_streamlit_logging_duplicate_handler(monkeypatch):
    """Test that duplicate handlers are not added"""
    dummy = DummyEvent()
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    logger_name = 'test.duplicate'
    logger = logging.getLogger(logger_name)
    
    # Clear any existing handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)
    
    # Setup handler twice
    handler1 = logmod.setup_streamlit_logging(logger_name=logger_name, tool_name='tool1')
    handler2 = logmod.setup_streamlit_logging(logger_name=logger_name, tool_name='tool2')
    
    # Should still only have one StreamlitCallbackHandler
    streamlit_handlers = [h for h in logger.handlers if isinstance(h, logmod.StreamlitCallbackHandler)]
    assert len(streamlit_handlers) == 1


def test_setup_streamlit_logging_root_logger(monkeypatch):
    """Test setup with root logger (empty string)"""
    dummy = DummyEvent()
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    
    # Get initial handler count for root logger
    root_logger = logging.getLogger("")
    initial_handler_count = len(root_logger.handlers)
    
    handler = logmod.setup_streamlit_logging(logger_name="", tool_name='root_tool')
    assert isinstance(handler, logmod.StreamlitCallbackHandler)
    assert root_logger.level == logging.INFO


def test_with_streamlit_logs_exception_handling(monkeypatch):
    """Test that decorator properly removes handler even when function raises exception"""
    dummy = DummyEvent()
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    logger_name = 'test.exception'
    logger = logging.getLogger(logger_name)
    
    # Clear any existing handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)
    
    initial_handler_count = len(logger.handlers)
    
    @logmod.with_streamlit_logs(logger_name=logger_name, tool_name='exception_tool')
    def failing_function():
        logger.info('About to fail')
        raise ValueError("Test exception")
    
    with pytest.raises(ValueError):
        failing_function()
    
    # Handler should be removed even after exception
    assert len(logger.handlers) == initial_handler_count


def test_with_streamlit_logs_nested_calls(monkeypatch):
    """Test nested decorated function calls"""
    dummy = DummyEvent()
    monkeypatch.setattr(logmod, 'dispatch_custom_event', dummy)
    logger_name = 'test.nested'
    logger = logging.getLogger(logger_name)
    
    @logmod.with_streamlit_logs(logger_name=logger_name, tool_name='outer')
    def outer_function():
        logger.info('outer log')
        
        @logmod.with_streamlit_logs(logger_name=logger_name, tool_name='inner')
        def inner_function():
            logger.info('inner log')
            return 'inner_result'
        
        result = inner_function()
        return f'outer_{result}'
    
    result = outer_function()
    assert result == 'outer_inner_result'
    assert len(dummy.events) >= 2


def test_dispatch_custom_event_fallback():
    """Test that fallback dispatch_custom_event doesn't raise errors"""
    # This tests the fallback function when langchain_core is not available
    with patch.dict('sys.modules', {'langchain_core.callbacks': None}):
        # Force re-import to trigger fallback
        import importlib
        importlib.reload(logmod)
        
        # The fallback should not raise any errors
        try:
            logmod.dispatch_custom_event("test_event", {"test": "data"})
        except Exception as e:
            pytest.fail(f"Fallback dispatch_custom_event raised an exception: {e}")


def test_json_loads_filter_and_evaluate_template():
    from alita_sdk.runtime.utils.evaluate import EvaluateTemplate, END
    # The json_loads filter is not automatically available, need to check actual behavior
    tpl = "{{ value }}"
    et = EvaluateTemplate(tpl, {'value': '[1, 2, 3]'})
    result = et.extract()
    assert result == '[1, 2, 3]'
    # Test END detection
    et_end = EvaluateTemplate('END', {})
    assert et_end.evaluate() == END
    # Invalid template raises
    et_bad = EvaluateTemplate('{% for x in %}', {})
    with pytest.raises(Exception):
        et_bad.extract()


def test_evaluate_template_json_loads_filter():
    """Test json_loads filter with various inputs"""
    from alita_sdk.runtime.utils.evaluate import EvaluateTemplate
    
    # Test the actual json_loads filter that exists in the code
    # The result will be a string representation since extract() returns string
    tpl = "{{ '[1, 2, 3]' | json_loads }}"
    et = EvaluateTemplate(tpl, {})
    result = et.extract()
    # The filter works but extract() always returns a string
    assert isinstance(result, str)
    assert '[1, 2, 3]' in result or '1' in result
    
    # Test with dictionary
    tpl = '{{ \'{"key": "value"}\' | json_loads }}'
    et = EvaluateTemplate(tpl, {})
    result = et.extract()
    assert isinstance(result, str)


def test_evaluate_template_context_variables():
    """Test template with context variables"""
    from alita_sdk.runtime.utils.evaluate import EvaluateTemplate
    
    context = {"name": "John", "age": 30, "items": ["a", "b", "c"]}
    tpl = "Hello {{ name }}, you are {{ age }} years old and have {{ items | length }} items"
    et = EvaluateTemplate(tpl, context)
    result = et.extract()
    assert result == "Hello John, you are 30 years old and have 3 items"


def test_evaluate_template_undefined_variable():
    """Test template with undefined variables"""
    from alita_sdk.runtime.utils.evaluate import EvaluateTemplate
    
    # Jinja2 has a default behavior for undefined variables - it doesn't raise by default
    # unless strict_undefined is set
    tpl = "Hello {{ undefined_var }}"
    et = EvaluateTemplate(tpl, {})
    result = et.extract()
    # Should render with empty value or "undefined_var" depending on Jinja2 configuration
    assert isinstance(result, str)
    assert "Hello" in result


def test_evaluate_template_end_detection_variations():
    """Test END detection with various formats"""
    from alita_sdk.runtime.utils.evaluate import EvaluateTemplate, END
    
    # Test exact END
    et = EvaluateTemplate('END', {})
    assert et.evaluate() == END
    
    # Test END with whitespace
    et = EvaluateTemplate('  END  ', {})
    assert et.evaluate() == END
    
    # Test END in a sentence
    et = EvaluateTemplate('This is the END of the line', {})
    assert et.evaluate() == END
    
    # Test lowercase end
    et = EvaluateTemplate('end', {})
    assert et.evaluate() != END


def test_evaluate_template_complex_expressions():
    """Test complex template expressions"""
    from alita_sdk.runtime.utils.evaluate import EvaluateTemplate
    
    context = {
        "users": [
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": 30}
        ]
    }
    
    tpl = """
    {%- for user in users -%}
    {{ user.name }}: {{ user.age }}
    {%- endfor -%}
    """
    
    et = EvaluateTemplate(tpl, context)
    result = et.extract()
    assert "Alice: 25" in result
    assert "Bob: 30" in result