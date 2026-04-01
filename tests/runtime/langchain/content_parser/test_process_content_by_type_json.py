"""
Unit tests for process_content_by_type — .json files.

Focus areas
-----------
chunking_config
  Mirrors the UI flow where a user submits {".json": {"max_tokens": 512}}.
  Unlike AlitaMarkdownLoader, AlitaJSONLoader reads max_tokens directly from
  **kwargs, so process_content_by_type wires it correctly.  These tests confirm
  that correct wiring and will catch any regression that breaks it.

  Key implementation detail: AlitaJSONLoader passes max_tokens as max_chunk_size
  to RecursiveJsonSplitter — so the unit is characters, not BPE tokens.
  DEFAULT_ALLOWED_BASE = {'max_tokens': 512}.

llm parameter
  .json loader has no 'use_llm' flag in loaders_map kwargs, so the llm argument
  is never forwarded. A mock LLM must be ignored (no error, same output, never called).

Smoke tests  — minimal wiring sanity checks including empty / array JSON.
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

_JSON_SIMPLE = _TEST_DATA / "AlitaJSONLoader" / "files" / "json_simple.json"
_JSON_LARGE  = _TEST_DATA / "AlitaJSONLoader" / "files" / "json_large.json"
_JSON_EMPTY  = _TEST_DATA / "AlitaJSONLoader" / "files" / "json_empty.json"
_JSON_ARRAY  = _TEST_DATA / "AlitaJSONLoader" / "files" / "json_array.json"


# ===========================================================================
# Smoke
# ===========================================================================

class TestSmokeJson:
    """Minimal wiring sanity checks for .json."""

    def test_processes_content(self):
        docs = list(process_content_by_type(_read_bytes(_JSON_SIMPLE), "file.json"))
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_none_content_returns_empty(self):
        assert list(process_content_by_type(None, "file.json")) == []

    def test_returns_generator(self):
        assert isinstance(
            process_content_by_type(b'{"a": 1}', "f.json"), types.GeneratorType
        )

    def test_empty_json_object_yields_no_docs(self):
        """
        Empty JSON object {} passes through RecursiveJsonSplitter which returns []
        for an empty dict — so no documents are produced.
        This is the current behavior; a caller should handle the empty-result case.
        """
        docs = list(process_content_by_type(_read_bytes(_JSON_EMPTY), "empty.json"))
        assert docs == []

    def test_json_array_is_processed(self):
        """JSON arrays are converted to {str(i): item} dicts before splitting."""
        docs = list(process_content_by_type(_read_bytes(_JSON_ARRAY), "arr.json"))
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_output_is_valid_json_per_chunk(self):
        """Each page_content must be valid JSON (the loader dumps each chunk)."""
        docs = list(process_content_by_type(_read_bytes(_JSON_SIMPLE), "f.json"))
        for doc in docs:
            parsed = json.loads(doc.page_content)
            assert isinstance(parsed, dict)


# ===========================================================================
# chunking_config — UI scenarios for .json
# ===========================================================================

class TestChunkingConfigJson:
    """
    UI sends {".json": {"max_tokens": <value>}} from the chunking panel.

    AlitaJSONLoader reads max_tokens directly from **kwargs, so
    process_content_by_type correctly propagates it.  All tests here are
    expected to PASS — they are regression guards, not known-bug trackers.
    """

    def test_max_tokens_512_equals_default_is_noop(self):
        """
        UI sends {".json": {"max_tokens": 512}}.
        512 == LOADER_MAX_TOKENS_DEFAULT → != guard fires → NOT forwarded.
        Output must be identical to no-config call.
        """
        content = _read_bytes(_JSON_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.json"))
        docs_ui_config = list(process_content_by_type(
            content, "f.json",
            chunking_config={".json": {"max_tokens": LOADER_MAX_TOKENS_DEFAULT}},
        ))
        assert _page_contents(docs_ui_config) == _page_contents(docs_no_config)

    def test_smaller_max_tokens_produces_more_chunks(self):
        """
        UI sends {".json": {"max_tokens": 50}}.
        max_tokens is forwarded as max_chunk_size=50 to RecursiveJsonSplitter.
        json_large.json (4 KB) at max_chunk_size=512 → 2 chunks;
        at max_chunk_size=50 → 3+ chunks.
        """
        content = _read_bytes(_JSON_LARGE)
        docs_default = list(process_content_by_type(content, "big.json"))
        docs_ui = list(process_content_by_type(
            content, "big.json",
            chunking_config={".json": {"max_tokens": 50}},
        ))
        assert len(docs_ui) > len(docs_default), (
            f"max_tokens=50 should yield more chunks than default {LOADER_MAX_TOKENS_DEFAULT}, "
            f"got {len(docs_ui)} vs {len(docs_default)}"
        )

    def test_larger_max_tokens_produces_fewer_chunks(self):
        """
        UI sends {".json": {"max_tokens": 4096}}.
        json_large.json at max_chunk_size=512 → 2 chunks;
        at max_chunk_size=4096 the whole file fits in one chunk → 1 chunk.
        """
        content = _read_bytes(_JSON_LARGE)
        docs_default = list(process_content_by_type(content, "big.json"))
        docs_ui = list(process_content_by_type(
            content, "big.json",
            chunking_config={".json": {"max_tokens": 4096}},
        ))
        assert len(docs_ui) < len(docs_default), (
            f"max_tokens=4096 should yield fewer chunks than default {LOADER_MAX_TOKENS_DEFAULT}, "
            f"got {len(docs_ui)} vs {len(docs_default)}"
        )

    def test_config_for_other_extension_not_applied(self):
        """chunking_config keyed on .txt must not bleed into .json processing."""
        content = _read_bytes(_JSON_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.json"))
        docs_wrong_ext = list(process_content_by_type(
            content, "f.json",
            chunking_config={".txt": {"max_tokens": 1}},
        ))
        assert _page_contents(docs_no_config) == _page_contents(docs_wrong_ext)


# ===========================================================================
# llm parameter — .json
# ===========================================================================

class TestLlmJson:
    """
    .json loader has no 'use_llm' flag in loaders_map kwargs, so the llm
    argument is never forwarded. Mock LLM must be a clean no-op.
    """

    def test_with_mock_llm_produces_same_docs(self):
        content = _read_bytes(_JSON_SIMPLE)
        mock_llm = MagicMock(name="mock_llm")
        docs_no_llm   = list(process_content_by_type(content, "f.json"))
        docs_with_llm = list(process_content_by_type(content, "f.json", llm=mock_llm))
        assert _page_contents(docs_with_llm) == _page_contents(docs_no_llm)

    def test_mock_llm_never_called(self):
        mock_llm = MagicMock(name="mock_llm")
        list(process_content_by_type(b'{"key": "value"}', "f.json", llm=mock_llm))
        mock_llm.assert_not_called()

    def test_llm_and_chunking_config_combined(self):
        """llm is ignored; chunking_config override IS applied."""
        content = _read_bytes(_JSON_LARGE)
        mock_llm = MagicMock(name="mock_llm")
        docs = list(process_content_by_type(
            content, "big.json",
            llm=mock_llm,
            chunking_config={".json": {"max_tokens": 50}},
        ))
        assert len(docs) >= 1
        mock_llm.assert_not_called()


# ===========================================================================
# loaders_map mutation guard — .json
# ===========================================================================

class TestLoadersMapNotMutatedJson:
    """Regression: shared loaders_map[".json"]["kwargs"] must never be mutated."""

    def test_kwargs_unchanged_after_calls(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".json"]["kwargs"])
        list(process_content_by_type(b'{"a": 1}', "a.json"))
        list(process_content_by_type(b'{"b": 2}', "b.json"))
        assert loaders_map[".json"]["kwargs"] == original

    def test_kwargs_unchanged_with_chunking_config(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".json"]["kwargs"])
        list(process_content_by_type(
            b'{"key": "val"}', "c.json",
            chunking_config={".json": {"max_tokens": 100}},
        ))
        assert loaders_map[".json"]["kwargs"] == original
