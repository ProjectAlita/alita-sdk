"""
Unit tests for process_content_by_type — .jsonl files.

Focus areas
-----------
chunking_config
  Mirrors the UI flow where a user submits {".jsonl": {"max_tokens": 512}}.
  AlitaJSONLinesLoader inherits max_tokens handling from AlitaJSONLoader and
  reads it directly from **kwargs — process_content_by_type wires it correctly.
  These tests confirm that correct wiring and will catch any regression.

  Key behavior: each non-empty line is processed by a per-line AlitaJSONLoader
  instance.  max_tokens controls the RecursiveJsonSplitter max_chunk_size for
  each line.  jsonl_large.jsonl (5 lines, heavily nested) at max_chunk_size=512
  yields 15 chunks; at max_chunk_size=50 yields 74 chunks; at max_chunk_size=4096
  yields 15 chunks (same as default — RecursiveJsonSplitter naturally splits at
  JSON structure boundaries regardless of the larger limit).

llm parameter
  .jsonl loader has no 'use_llm' flag in loaders_map kwargs.

Smoke tests  — empty file, unicode content, multi-line sanity.
loaders_map mutation guard — regression for the dict-copy fix.
"""

import json
import types
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from alita_sdk.runtime.langchain.constants import LOADER_MAX_TOKENS_DEFAULT
from alita_sdk.tools.utils.content_parser import process_content_by_type
from helpers import _TEST_DATA, read_bytes as _read_bytes, page_contents as _page_contents

# ---------------------------------------------------------------------------
# Paths to shared fixture files
# ---------------------------------------------------------------------------

_JSONL_SIMPLE  = _TEST_DATA / "AlitaJSONLinesLoader" / "files" / "jsonl_simple.jsonl"
_JSONL_LARGE   = _TEST_DATA / "AlitaJSONLinesLoader" / "files" / "jsonl_large.jsonl"
_JSONL_EMPTY   = _TEST_DATA / "AlitaJSONLinesLoader" / "files" / "jsonl_empty.jsonl"
_JSONL_UNICODE = _TEST_DATA / "AlitaJSONLinesLoader" / "files" / "jsonl_unicode.jsonl"


# ===========================================================================
# Smoke
# ===========================================================================

class TestSmokeJsonl:
    """Minimal wiring sanity checks for .jsonl."""

    def test_processes_content(self):
        docs = list(process_content_by_type(_read_bytes(_JSONL_SIMPLE), "file.jsonl"))
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_none_content_returns_empty(self):
        assert list(process_content_by_type(None, "file.jsonl")) == []

    def test_empty_file_returns_empty(self):
        assert list(process_content_by_type(_read_bytes(_JSONL_EMPTY), "empty.jsonl")) == []

    def test_returns_generator(self):
        line = b'{"a": 1}\n'
        assert isinstance(process_content_by_type(line, "f.jsonl"), types.GeneratorType)

    def test_each_line_produces_at_least_one_doc(self):
        """jsonl_simple.jsonl has 3 lines → at least 3 documents."""
        docs = list(process_content_by_type(_read_bytes(_JSONL_SIMPLE), "f.jsonl"))
        assert len(docs) >= 3

    def test_output_is_valid_json_per_chunk(self):
        """Each page_content must be valid JSON."""
        docs = list(process_content_by_type(_read_bytes(_JSONL_SIMPLE), "f.jsonl"))
        for doc in docs:
            parsed = json.loads(doc.page_content)
            assert isinstance(parsed, dict)

    def test_unicode_content_processed(self):
        """Unicode JSONL must not raise."""
        docs = list(process_content_by_type(_read_bytes(_JSONL_UNICODE), "unicode.jsonl"))
        assert len(docs) >= 1


# ===========================================================================
# chunking_config — UI scenarios for .jsonl
# ===========================================================================

class TestChunkingConfigJsonl:
    """
    UI sends {".jsonl": {"max_tokens": <value>}} from the chunking panel.

    max_tokens is forwarded as max_chunk_size to a per-line RecursiveJsonSplitter.
    All tests here are expected to PASS.
    """

    def test_max_tokens_512_equals_default_is_noop(self):
        """
        UI sends {".jsonl": {"max_tokens": 512}}.
        512 == LOADER_MAX_TOKENS_DEFAULT → != guard fires → NOT forwarded.
        Output must be identical to no-config call.
        """
        content = _read_bytes(_JSONL_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.jsonl"))
        docs_ui_config = list(process_content_by_type(
            content, "f.jsonl",
            chunking_config={".jsonl": {"max_tokens": LOADER_MAX_TOKENS_DEFAULT}},
        ))
        assert _page_contents(docs_ui_config) == _page_contents(docs_no_config)

    def test_smaller_max_tokens_produces_more_chunks(self):
        """
        UI sends {".jsonl": {"max_tokens": 50}}.
        jsonl_large.jsonl at max_chunk_size=512 → 15 chunks;
        at max_chunk_size=50 → 74 chunks.
        """
        content = _read_bytes(_JSONL_LARGE)
        docs_default = list(process_content_by_type(content, "big.jsonl"))
        docs_ui = list(process_content_by_type(
            content, "big.jsonl",
            chunking_config={".jsonl": {"max_tokens": 50}},
        ))
        assert len(docs_ui) > len(docs_default), (
            f"max_tokens=50 should yield more chunks than default {LOADER_MAX_TOKENS_DEFAULT}, "
            f"got {len(docs_ui)} vs {len(docs_default)}"
        )

    def test_config_for_other_extension_not_applied(self):
        """chunking_config keyed on .json must not bleed into .jsonl processing."""
        content = _read_bytes(_JSONL_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.jsonl"))
        docs_wrong_ext = list(process_content_by_type(
            content, "f.jsonl",
            chunking_config={".json": {"max_tokens": 1}},
        ))
        assert _page_contents(docs_no_config) == _page_contents(docs_wrong_ext)


# ===========================================================================
# llm parameter — .jsonl
# ===========================================================================

class TestLlmJsonl:
    """
    .jsonl loader has no 'use_llm' flag in loaders_map kwargs, so the llm
    argument is never forwarded. Mock LLM must be a clean no-op.
    """

    def test_with_mock_llm_produces_same_docs(self):
        content = _read_bytes(_JSONL_SIMPLE)
        mock_llm = MagicMock(name="mock_llm")
        docs_no_llm   = list(process_content_by_type(content, "f.jsonl"))
        docs_with_llm = list(process_content_by_type(content, "f.jsonl", llm=mock_llm))
        assert _page_contents(docs_with_llm) == _page_contents(docs_no_llm)

    def test_mock_llm_never_called(self):
        mock_llm = MagicMock(name="mock_llm")
        list(process_content_by_type(b'{"key": "value"}\n', "f.jsonl", llm=mock_llm))
        mock_llm.assert_not_called()

    def test_llm_and_chunking_config_combined(self):
        """llm is ignored; chunking_config override IS applied."""
        content = _read_bytes(_JSONL_LARGE)
        mock_llm = MagicMock(name="mock_llm")
        docs = list(process_content_by_type(
            content, "big.jsonl",
            llm=mock_llm,
            chunking_config={".jsonl": {"max_tokens": 50}},
        ))
        assert len(docs) >= 1
        mock_llm.assert_not_called()


# ===========================================================================
# loaders_map mutation guard — .jsonl
# ===========================================================================

class TestLoadersMapNotMutatedJsonl:
    """Regression: shared loaders_map[".jsonl"]["kwargs"] must never be mutated."""

    def test_kwargs_unchanged_after_calls(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".jsonl"]["kwargs"])
        list(process_content_by_type(b'{"a": 1}\n', "a.jsonl"))
        list(process_content_by_type(b'{"b": 2}\n', "b.jsonl"))
        assert loaders_map[".jsonl"]["kwargs"] == original

    def test_kwargs_unchanged_with_chunking_config(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".jsonl"]["kwargs"])
        list(process_content_by_type(
            b'{"key": "val"}\n', "c.jsonl",
            chunking_config={".jsonl": {"max_tokens": 100}},
        ))
        assert loaders_map[".jsonl"]["kwargs"] == original
