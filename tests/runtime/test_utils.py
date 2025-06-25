import pandas as pd
from unittest.mock import MagicMock
import logging
import types

import pytest

from alita_sdk.runtime.utils.utils import clean_string
from alita_sdk.runtime.utils.save_dataframe import save_dataframe_to_artifact
from alita_sdk.runtime.utils.evaluate import EvaluateTemplate, END
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
