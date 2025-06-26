import pandas as pd
from unittest.mock import MagicMock, Mock, patch
import logging
import types
import tempfile
import os

import pytest

from alita_sdk.runtime.utils.utils import clean_string
from alita_sdk.runtime.utils.save_dataframe import save_dataframe_to_artifact
from alita_sdk.runtime.utils.evaluate import EvaluateTemplate, END, TransformationError, MyABC
from alita_sdk.runtime.llms.preloaded import PreloadedChatModel
from alita_sdk.runtime.clients.prompt import AlitaPrompt
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

def test_clean_string():
    assert clean_string('hello world!') == 'helloworld'
    assert clean_string('a_b-c.d') == 'a_b-c.d'

def test_save_dataframe_success():
    df = pd.DataFrame({'a': [1,2]})
    mock_wrapper = MagicMock()
    mock_wrapper.bucket = 'bucket'
    save_dataframe_to_artifact(mock_wrapper, df, 'file.csv')
    mock_wrapper.create_file.assert_called_once()
    args, _ = mock_wrapper.create_file.call_args
    assert args[0] == 'file.csv'

def test_save_dataframe_failure():
    df = pd.DataFrame({'a': [1]})
    mock_wrapper = MagicMock()
    mock_wrapper.bucket = 'bucket'
    def raise_error(*a, **k):
        raise RuntimeError('fail')
    mock_wrapper.create_file.side_effect = raise_error
    err = save_dataframe_to_artifact(mock_wrapper, df, 'file.csv')
    assert err.args[0].startswith('Failed to save DataFrame')

def test_evaluate_template():
    et = EvaluateTemplate('{{ value }}', {'value': 'ok'})
    assert et.evaluate() == 'ok'
    et2 = EvaluateTemplate('END', {})
    assert et2.evaluate() == END

def test_remove_non_system_messages():
    msgs = [
        {"role": "system", "content": "s"},
        {"role": "human", "content": "h1"},
        {"role": "ai", "content": "a1"},
        {"role": "human", "content": "h2"},
    ]
    result, removed = PreloadedChatModel._remove_non_system_messages(msgs, 2)
    assert removed == 2
    assert result == [
        {"role": "system", "content": "s"},
        {"role": "human", "content": "h2"},
    ]


def test_count_tokens():
    tokens = PreloadedChatModel._count_tokens([
        {"content": "hello"},
        {"content": "world"},
    ])
    single = PreloadedChatModel._count_tokens("hello") + PreloadedChatModel._count_tokens("world")
    assert tokens == single


class FakeAlita:
    def predict(self, messages, llm_settings, variables=None):
        return [AIMessage(content="one"), AIMessage(content="two")]

def test_alita_prompt():
    prompt = ChatPromptTemplate.from_messages([("human", "{text}")])
    ap = AlitaPrompt(FakeAlita(), prompt, "name", "desc", {})
    Model = ap.create_pydantic_model()
    assert set(Model.__fields__.keys()) == {"text", "input"}
    result = ap.predict({"text": "foo", "input": "bar"})
    assert result == "one\n\ntwo"

def test_evaluate_template_invalid():
    et = EvaluateTemplate('{% for x in %}', {})
    with pytest.raises(Exception):
        et.evaluate()


def test_limit_tokens():
    model = PreloadedChatModel.model_construct(token_limit=4, max_tokens=1)
    msgs = [
        {"role": "system", "content": "s"},
        {"role": "human", "content": "hello"},
        {"role": "ai", "content": "world"},
        {"role": "human", "content": "again"},
    ]
    result = model._limit_tokens(msgs)
    assert result == [
        {"role": "system", "content": "s"},
        {"role": "human", "content": "again"},
    ]


def test_transformation_error():
    """Test TransformationError exception"""
    error = TransformationError("Test transformation error")
    assert str(error) == "Test transformation error"
    assert isinstance(error, Exception)
    
    with pytest.raises(TransformationError):
        raise TransformationError("Custom error message")


def test_my_abc_metaclass():
    """Test MyABC metaclass functionality"""
    # Test that registry exists
    assert hasattr(MyABC, 'meta_registry')
    assert isinstance(MyABC.meta_registry, dict)
    
    # The metaclass only registers classes with bases and 'TransformerEvaluate' in name
    initial_count = len(MyABC.meta_registry)
    
    # Create a base class first
    class BaseClass(metaclass=MyABC):
        pass
    
    # This won't be registered because it has no bases (direct metaclass usage)
    assert len(MyABC.meta_registry) == initial_count
    
    # Create a derived class that should be registered
    class MyTestTransformerEvaluate(BaseClass):
        pass
    
    # Should be registered in meta_registry with key "mytest"
    assert 'mytest' in MyABC.meta_registry
    assert MyABC.meta_registry['mytest'] is MyTestTransformerEvaluate
    assert hasattr(MyTestTransformerEvaluate, '_output_format')
    assert MyTestTransformerEvaluate._output_format == 'mytest'


def test_evaluate_template_with_logging():
    """Test EvaluateTemplate logging functionality"""
    with patch('alita_sdk.runtime.utils.evaluate.logger') as mock_logger:
        context = {"name": "test", "value": 42}
        tpl = "Hello {{ name }}, value is {{ value }}"
        et = EvaluateTemplate(tpl, context)
        result = et.extract()
        
        # Should log context
        mock_logger.info.assert_called_with(f"Condition context: {context}")
        assert result == "Hello test, value is 42"


def test_evaluate_template_syntax_error_logging():
    """Test EvaluateTemplate error logging"""
    with patch('alita_sdk.runtime.utils.evaluate.logger') as mock_logger:
        et = EvaluateTemplate('{% invalid syntax %}', {})
        
        with pytest.raises(Exception, match="Invalid jinja template"):
            et.extract()
        
        # Should log critical error and template
        mock_logger.critical.assert_called_once()
        mock_logger.info.assert_called_with('Template str: %s', '{% invalid syntax %}')


def test_evaluate_template_json_filter_error_handling():
    """Test json_loads filter error handling"""
    et = EvaluateTemplate("{{ 'invalid json' | json_loads }}", {})
    
    with pytest.raises(Exception):
        et.extract()


def test_evaluate_template_extract_vs_evaluate():
    """Test difference between extract and evaluate methods"""
    # Test normal case
    et = EvaluateTemplate('Hello {{ name }}', {'name': 'World'})
    extracted = et.extract()
    evaluated = et.evaluate()
    
    assert extracted == 'Hello World'
    assert evaluated == 'Hello World'
    
    # Test END case
    et_end = EvaluateTemplate('This contains END somewhere', {})
    extracted = et_end.extract()
    evaluated = et_end.evaluate()
    
    assert extracted == 'This contains END somewhere'
    assert evaluated == END  # Should return END constant


def test_evaluate_template_whitespace_handling():
    """Test template whitespace handling"""
    # Test with leading/trailing whitespace
    et = EvaluateTemplate('  {{ value }}  ', {'value': 'test'})
    result = et.evaluate()
    assert result == 'test'  # Should be stripped
    
    # Test with END and whitespace
    et_end = EvaluateTemplate('  END  ', {})
    result = et_end.evaluate()
    assert result == END


def test_evaluate_template_complex_jinja():
    """Test complex Jinja2 templates"""
    context = {
        'items': ['a', 'b', 'c'],
        'user': {'name': 'John', 'age': 30}
    }
    
    template = """
    User: {{ user.name }} ({{ user.age }} years old)
    Items: {% for item in items %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}
    """
    
    et = EvaluateTemplate(template, context)
    result = et.extract()
    
    assert 'User: John (30 years old)' in result
    assert 'Items: a, b, c' in result


def test_preloaded_chat_model_edge_cases():
    """Test edge cases for PreloadedChatModel"""
    model = PreloadedChatModel.model_construct(token_limit=100, max_tokens=50)
    
    # Test with None messages
    with pytest.raises((TypeError, AttributeError)):
        model._count_tokens(None)
    
    # Test with nested message structures
    complex_msgs = [
        {"role": "system", "content": "System message with unicode: 🚀"},
        {"role": "human", "content": "Message with\nmultiple\nlines"},
        {"role": "ai", "content": ""}  # Empty content
    ]
    
    count = PreloadedChatModel._count_tokens(complex_msgs)
    assert isinstance(count, int)
    assert count >= 0


def test_save_dataframe_comprehensive():
    """Test save_dataframe with comprehensive scenarios"""
    # Test with different DataFrame types
    dfs_to_test = [
        pd.DataFrame({'int': [1, 2, 3]}),
        pd.DataFrame({'float': [1.1, 2.2, 3.3]}),
        pd.DataFrame({'string': ['a', 'b', 'c']}),
        pd.DataFrame({'bool': [True, False, True]}),
        pd.DataFrame(),  # Empty DataFrame
        pd.DataFrame({'mixed': [1, 'text', 3.14, True]})
    ]
    
    for i, df in enumerate(dfs_to_test):
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        result = save_dataframe_to_artifact(mock_wrapper, df, f'test_{i}.csv')
        
        # Should not return error for valid DataFrames
        assert result is None
        mock_wrapper.create_file.assert_called_once()
        mock_wrapper.reset_mock()


def test_alita_prompt_edge_cases():
    """Test AlitaPrompt edge cases"""
    class ErrorAlita:
        def predict(self, messages, llm_settings, variables=None):
            raise ValueError("Prediction failed")
    
    prompt = ChatPromptTemplate.from_messages([("human", "test")])
    ap = AlitaPrompt(ErrorAlita(), prompt, "test", "desc", {})
    
    with pytest.raises(ValueError):
        ap.predict({})


def test_clean_string_comprehensive():
    """Test clean_string with comprehensive inputs"""
    test_cases = [
        # (input, expected_output)
        ('', ''),
        ('simple', 'simple'),
        ('with spaces', 'withspaces'),
        ('with-dashes_and.dots', 'with-dashes_and.dots'),
        ('UPPER_case', 'UPPER_case'),
        ('123numbers', '123numbers'),
        ('special!@#$%chars', 'specialchars'),
        ('unicode🚀test', 'unicodetest'),
        ('file[1].txt', 'file1.txt'),
        ('path\\to\\file', 'pathtofile'),
        ('email@domain.com', 'emaildomain.com'),
        ('mix_ALL-types.123!@#', 'mix_ALL-types.123')
    ]
    
    for input_val, expected in test_cases:
        result = clean_string(input_val)
        assert result == expected, f"Failed for input: '{input_val}'"
