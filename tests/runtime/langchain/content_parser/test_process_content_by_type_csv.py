"""
Unit tests for process_content_by_type — .csv files.

Focus areas
-----------
chunking_config
  Mirrors the UI flow where a user submits {".csv": {"max_tokens": 512}}.
  Verifies the same-as-default no-op guard, that non-default values don't raise,
  and that disallowed keys (encoding) are silently ignored.

llm parameter
  .csv loader has no 'use_llm' flag in loaders_map kwargs, so the llm argument
  is never forwarded. A mock LLM must be ignored (no error, same output, never called).

Smoke tests  — minimal wiring sanity checks.
loaders_map mutation guard — regression for the dict-copy fix.
"""

import types
from unittest.mock import MagicMock

from langchain_core.documents import Document

from alita_sdk.runtime.langchain.constants import LOADER_MAX_TOKENS_DEFAULT
from alita_sdk.tools.utils.content_parser import process_content_by_type
from helpers import _TEST_DATA, read_bytes as _read_bytes, page_contents as _page_contents

# ---------------------------------------------------------------------------
# Paths to shared fixture files
# ---------------------------------------------------------------------------

_CSV_SIMPLE = _TEST_DATA / "AlitaCSVLoader" / "files" / "csv_simple.csv"


# ===========================================================================
# Smoke
# ===========================================================================

class TestSmokeCsv:
    """Minimal wiring sanity checks for .csv."""

    def test_processes_content(self):
        docs = list(process_content_by_type(_read_bytes(_CSV_SIMPLE), "file.csv"))
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_none_content_returns_empty(self):
        assert list(process_content_by_type(None, "file.csv")) == []

    def test_returns_generator(self):
        assert isinstance(process_content_by_type(b"a,b\n1,2\n", "f.csv"), types.GeneratorType)


# ===========================================================================
# chunking_config — UI scenarios for .csv
# ===========================================================================

class TestChunkingConfigCsv:
    """
    UI sends {".csv": {"max_tokens": <value>}} from the chunking panel.
    """

    def test_max_tokens_512_equals_default_is_noop(self):
        """
        UI sends {".csv": {"max_tokens": 512}}.
        512 == LOADER_MAX_TOKENS_DEFAULT → != guard fires → NOT forwarded.
        AlitaCSVLoader ignores the kwarg anyway; output count must be unchanged.
        """
        content = _read_bytes(_CSV_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.csv"))
        docs_ui_config = list(process_content_by_type(
            content, "f.csv",
            chunking_config={".csv": {"max_tokens": LOADER_MAX_TOKENS_DEFAULT}},
        ))
        assert len(docs_ui_config) == len(docs_no_config)

    def test_non_default_max_tokens_does_not_raise(self):
        """
        UI sends {".csv": {"max_tokens": 256}}.
        AlitaCSVLoader silently ignores the extra kwarg; must not raise and must
        return the same documents as without a config.
        """
        content = _read_bytes(_CSV_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.csv"))
        docs_ui = list(process_content_by_type(
            content, "data.csv",
            chunking_config={".csv": {"max_tokens": 256}},
        ))
        assert len(docs_ui) == len(docs_no_config)

    def test_disallowed_key_encoding_silently_ignored(self):
        """
        'encoding' is a CSV loader kwarg but NOT in allowed_to_override
        (DEFAULT_ALLOWED_BASE only contains max_tokens). Must be skipped silently.
        """
        content = _read_bytes(_CSV_SIMPLE)
        docs = list(process_content_by_type(
            content, "data.csv",
            chunking_config={".csv": {"encoding": "latin-1"}},
        ))
        assert len(docs) >= 1


# ===========================================================================
# llm parameter — .csv
# ===========================================================================

class TestLlmCsv:
    """
    .csv loader has no 'use_llm' flag in loaders_map kwargs, so the llm
    argument is never forwarded. Mock LLM must be a clean no-op.
    """

    def test_with_mock_llm_produces_same_docs(self):
        content = _read_bytes(_CSV_SIMPLE)
        mock_llm = MagicMock(name="mock_llm")
        docs_no_llm   = list(process_content_by_type(content, "f.csv"))
        docs_with_llm = list(process_content_by_type(content, "f.csv", llm=mock_llm))
        assert _page_contents(docs_with_llm) == _page_contents(docs_no_llm)

    def test_mock_llm_never_called(self):
        mock_llm = MagicMock(name="mock_llm")
        list(process_content_by_type(b"a,b\n1,2\n", "f.csv", llm=mock_llm))
        mock_llm.assert_not_called()


# ===========================================================================
# loaders_map mutation guard — .csv
# ===========================================================================

class TestLoadersMapNotMutatedCsv:
    """Regression: shared loaders_map[".csv"]["kwargs"] must never be mutated."""

    def test_kwargs_unchanged_after_calls(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".csv"]["kwargs"])
        list(process_content_by_type(b"x,y\n1,2\n", "a.csv"))
        list(process_content_by_type(b"x,y\n3,4\n", "b.csv"))
        assert loaders_map[".csv"]["kwargs"] == original
