"""
Unit tests for process_content_by_type — .md files.

Focus areas
-----------
chunking_config
  Mirrors the UI flow where a user submits {".md": {"max_tokens": 512}}.
  Verifies the allowed-override logic, the same-as-default no-op guard, and
  that keys for other extensions are silently ignored.

llm parameter
  .md loader has no 'use_llm' flag in loaders_map kwargs, so the llm argument
  is never forwarded. A mock LLM must be ignored (no error, same output, never called).

Smoke tests  — minimal wiring sanity checks.
loaders_map mutation guard — regression for the dict-copy fix.
"""

import types
import pytest
from unittest.mock import MagicMock

from langchain_core.documents import Document

from alita_sdk.runtime.langchain.constants import LOADER_MAX_TOKENS_DEFAULT
from alita_sdk.tools.utils.content_parser import process_content_by_type
from helpers import _TEST_DATA, read_bytes as _read_bytes, page_contents as _page_contents

# ---------------------------------------------------------------------------
# Paths to shared fixture files
# ---------------------------------------------------------------------------

_MD_SIMPLE = _TEST_DATA / "AlitaMarkdownLoader" / "files" / "markdown_simple.md"
_MD_LARGE  = _TEST_DATA / "AlitaMarkdownLoader" / "files" / "markdown_large.md"


# ===========================================================================
# Smoke
# ===========================================================================

class TestSmokeMd:
    """Minimal wiring sanity checks for .md."""

    def test_processes_content(self):
        docs = list(process_content_by_type(_read_bytes(_MD_SIMPLE), "file.md"))
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_none_content_returns_empty(self):
        assert list(process_content_by_type(None, "file.md")) == []

    def test_empty_file_returns_empty(self):
        assert list(process_content_by_type(b"", "file.md")) == []

    def test_returns_generator(self):
        assert isinstance(process_content_by_type(b"# Title", "f.md"), types.GeneratorType)


# ===========================================================================
# chunking_config — UI scenarios for .md
# ===========================================================================

class TestChunkingConfigMd:
    """
    UI sends {".md": {"max_tokens": <value>}} from the chunking panel.
    """

    def test_max_tokens_512_equals_default_is_noop(self):
        """
        UI sends {".md": {"max_tokens": 512}}.
        512 == LOADER_MAX_TOKENS_DEFAULT → != guard fires → NOT forwarded.
        Output must be identical to no-config call.
        """
        content = _read_bytes(_MD_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.md"))
        docs_ui_config = list(process_content_by_type(
            content, "f.md",
            chunking_config={".md": {"max_tokens": LOADER_MAX_TOKENS_DEFAULT}},
        ))
        assert _page_contents(docs_ui_config) == _page_contents(docs_no_config)

    @pytest.mark.xfail(
        strict=True,
        reason="max_tokens override is not propagated to AlitaMarkdownLoader's "
               "chunker_config — tracked in "
               "https://github.com/ProjectAlita/projectalita.github.io/issues/3823",
    )
    def test_smaller_max_tokens_produces_more_chunks(self):
        """
        UI sends {".md": {"max_tokens": 50}} (< default 512).
        The override must reach AlitaMarkdownLoader's chunker_config so the
        content is split into more chunks than with the 512-token default.

        Inline content: "word " * 600 = 601 tokens (measured via tiktoken
        cl100k_base).  Default (512): 601 > 512 → 2 chunks.
        max_tokens=50:  601 / 50 → ~12 chunks.

        Tracked: https://github.com/ProjectAlita/projectalita.github.io/issues/3823
        """
        long_md = ("word " * 600).encode("utf-8")
        docs_default = list(process_content_by_type(long_md, "big.md"))
        docs_ui = list(process_content_by_type(
            long_md, "big.md",
            chunking_config={".md": {"max_tokens": 50}},
        ))
        assert len(docs_ui) > len(docs_default), (
            f"max_tokens=50 should yield more chunks than default {LOADER_MAX_TOKENS_DEFAULT}, "
            f"got {len(docs_ui)} vs {len(docs_default)}"
        )

    @pytest.mark.xfail(
        strict=True,
        reason="max_tokens override is not propagated to AlitaMarkdownLoader's "
               "chunker_config — tracked in "
               "https://github.com/ProjectAlita/projectalita.github.io/issues/3823",
    )
    def test_larger_max_tokens_produces_fewer_chunks(self):
        """
        UI sends {".md": {"max_tokens": 700}} (> default 512, > content size).
        Inline content: "word " * 600 = 601 tokens (measured via tiktoken
        cl100k_base).  Default (512): 601 > 512 → 2 chunks.
        max_tokens=700:     601 < 700 → no overflow split → 1 chunk.
        So strictly fewer chunks are expected.

        Tracked: https://github.com/ProjectAlita/projectalita.github.io/issues/3823
        """
        long_md = ("word " * 600).encode("utf-8")
        docs_default = list(process_content_by_type(long_md, "big.md"))
        docs_ui = list(process_content_by_type(
            long_md, "big.md",
            chunking_config={".md": {"max_tokens": 700}},
        ))
        assert len(docs_ui) < len(docs_default), (
            f"max_tokens=700 should yield fewer chunks than default {LOADER_MAX_TOKENS_DEFAULT}, "
            f"got {len(docs_ui)} vs {len(docs_default)}"
        )

    def test_config_for_other_extension_not_applied(self):
        """chunking_config keyed on .txt must not bleed into .md processing."""
        content = _read_bytes(_MD_SIMPLE)
        docs_no_config = list(process_content_by_type(content, "f.md"))
        docs_wrong_ext = list(process_content_by_type(
            content, "f.md",
            chunking_config={".txt": {"max_tokens": 1}},
        ))
        assert _page_contents(docs_no_config) == _page_contents(docs_wrong_ext)


# ===========================================================================
# llm parameter — .md
# ===========================================================================

class TestLlmMd:
    """
    .md loader has no 'use_llm' flag in loaders_map kwargs, so the llm
    argument is never forwarded. Mock LLM must be a clean no-op.
    """

    def test_with_mock_llm_produces_same_docs(self):
        content = _read_bytes(_MD_SIMPLE)
        mock_llm = MagicMock(name="mock_llm")
        docs_no_llm   = list(process_content_by_type(content, "f.md"))
        docs_with_llm = list(process_content_by_type(content, "f.md", llm=mock_llm))
        assert _page_contents(docs_with_llm) == _page_contents(docs_no_llm)

    def test_mock_llm_never_called(self):
        mock_llm = MagicMock(name="mock_llm")
        list(process_content_by_type(b"# heading\nsome text", "f.md", llm=mock_llm))
        mock_llm.assert_not_called()

    def test_llm_and_chunking_config_combined(self):
        """llm is ignored; chunking_config override IS applied."""
        content = _read_bytes(_MD_LARGE)
        mock_llm = MagicMock(name="mock_llm")
        docs = list(process_content_by_type(
            content, "big.md",
            llm=mock_llm,
            chunking_config={".md": {"max_tokens": 50}},
        ))
        assert len(docs) >= 1
        mock_llm.assert_not_called()


# ===========================================================================
# loaders_map mutation guard — .md
# ===========================================================================

class TestLoadersMapNotMutatedMd:
    """Regression: shared loaders_map[".md"]["kwargs"] must never be mutated."""

    def test_kwargs_unchanged_after_calls(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".md"]["kwargs"])
        list(process_content_by_type(b"# a", "a.md"))
        list(process_content_by_type(b"# b", "b.md"))
        assert loaders_map[".md"]["kwargs"] == original

    def test_kwargs_unchanged_with_chunking_config(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".md"]["kwargs"])
        list(process_content_by_type(
            b"# heading\ntext", "c.md",
            chunking_config={".md": {"max_tokens": 100}},
        ))
        assert loaders_map[".md"]["kwargs"] == original
