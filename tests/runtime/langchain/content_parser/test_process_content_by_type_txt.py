"""
Unit tests for process_content_by_type — .txt files.

Focus areas
-----------
chunking_config
  Mirrors the UI flow where a user submits {".txt": {"max_tokens": 512}}.
  Verifies the allowed-override logic, the same-as-default no-op guard, and
  that keys for other extensions are silently ignored.

llm parameter
  .txt loader has no 'use_llm' flag in loaders_map kwargs, so the llm argument
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

_TXT_SIMPLE = _TEST_DATA / "AlitaTextLoader" / "files" / "text_simple.txt"


# ===========================================================================
# Smoke
# ===========================================================================

class TestSmokeTxt:
    """Minimal wiring sanity checks for .txt."""

    def test_processes_content(self):
        docs = list(process_content_by_type(_read_bytes(_TXT_SIMPLE), "file.txt"))
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_none_content_returns_empty(self):
        assert list(process_content_by_type(None, "file.txt")) == []

    def test_unknown_extension_returns_empty(self):
        assert list(process_content_by_type(b"data", "file.unknownxyz")) == []

    def test_returns_generator(self):
        assert isinstance(process_content_by_type(b"hi", "f.txt"), types.GeneratorType)


# ===========================================================================
# chunking_config — UI scenarios for .txt
# ===========================================================================

class TestChunkingConfigTxt:
    """
    UI sends {".txt": {"max_tokens": <value>}} from the chunking panel.
    """

    def test_max_tokens_512_equals_default_is_noop(self):
        """
        UI sends {".txt": {"max_tokens": 512}}.
        512 == LOADER_MAX_TOKENS_DEFAULT → != guard fires → NOT forwarded.
        Output must be identical to no-config call.
        """
        content = _read_bytes(_TXT_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.txt"))
        docs_ui_config = list(process_content_by_type(
            content, "f.txt",
            chunking_config={".txt": {"max_tokens": LOADER_MAX_TOKENS_DEFAULT}},
        ))
        assert _page_contents(docs_ui_config) == _page_contents(docs_no_config)

    def test_smaller_max_tokens_produces_more_chunks(self):
        """
        UI sends {".txt": {"max_tokens": 50}} (< default 512).
        Value differs → applied → large content split into more chunks.
        """
        long_content = ("word " * 3000).encode("utf-8")
        docs_default = list(process_content_by_type(long_content, "big.txt"))
        docs_ui = list(process_content_by_type(
            long_content, "big.txt",
            chunking_config={".txt": {"max_tokens": 50}},
        ))
        assert len(docs_ui) > len(docs_default), (
            f"max_tokens=50 should yield more chunks than default {LOADER_MAX_TOKENS_DEFAULT}, "
            f"got {len(docs_ui)} vs {len(docs_default)}"
        )

    def test_larger_max_tokens_produces_fewer_or_equal_chunks(self):
        """
        UI sends {".txt": {"max_tokens": 4096}} (> default 512).
        Larger window → same content fits in fewer chunks.
        """
        long_content = ("word " * 3000).encode("utf-8")
        docs_default = list(process_content_by_type(long_content, "big.txt"))
        docs_ui = list(process_content_by_type(
            long_content, "big.txt",
            chunking_config={".txt": {"max_tokens": 4096}},
        ))
        assert len(docs_ui) <= len(docs_default)

    def test_config_for_other_extension_not_applied(self):
        """chunking_config keyed on .csv must not bleed into .txt processing."""
        content = b"unchanged txt content"
        docs_no_config = list(process_content_by_type(content, "f.txt"))
        docs_wrong_ext = list(process_content_by_type(
            content, "f.txt",
            chunking_config={".csv": {"max_tokens": 1}},
        ))
        assert _page_contents(docs_no_config) == _page_contents(docs_wrong_ext)


# ===========================================================================
# llm parameter — .txt
# ===========================================================================

class TestLlmTxt:
    """
    .txt loader has no 'use_llm' flag in loaders_map kwargs, so the llm
    argument is never forwarded. Mock LLM must be a clean no-op.
    """

    def test_with_mock_llm_produces_same_docs(self):
        content = _read_bytes(_TXT_SIMPLE)
        mock_llm = MagicMock(name="mock_llm")
        docs_no_llm   = list(process_content_by_type(content, "f.txt"))
        docs_with_llm = list(process_content_by_type(content, "f.txt", llm=mock_llm))
        assert _page_contents(docs_with_llm) == _page_contents(docs_no_llm)

    def test_mock_llm_never_called(self):
        mock_llm = MagicMock(name="mock_llm")
        list(process_content_by_type(b"some text", "f.txt", llm=mock_llm))
        mock_llm.assert_not_called()

    def test_llm_and_chunking_config_combined(self):
        """llm is ignored; chunking_config override IS applied."""
        long_content = ("word " * 3000).encode("utf-8")
        mock_llm = MagicMock(name="mock_llm")
        docs = list(process_content_by_type(
            long_content, "big.txt",
            llm=mock_llm,
            chunking_config={".txt": {"max_tokens": 50}},
        ))
        assert len(docs) >= 1
        mock_llm.assert_not_called()


# ===========================================================================
# loaders_map mutation guard — .txt
# ===========================================================================

class TestLoadersMapNotMutatedTxt:
    """Regression: shared loaders_map[".txt"]["kwargs"] must never be mutated."""

    def test_kwargs_unchanged_after_calls(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".txt"]["kwargs"])
        list(process_content_by_type(b"a", "a.txt"))
        list(process_content_by_type(b"b", "b.txt"))
        assert loaders_map[".txt"]["kwargs"] == original

    def test_kwargs_unchanged_with_chunking_config(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".txt"]["kwargs"])
        list(process_content_by_type(
            b"guard test", "x.txt",
            chunking_config={".txt": {"max_tokens": 128}},
        ))
        assert loaders_map[".txt"]["kwargs"] == original
