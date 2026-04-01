"""
Integration tests for AlitaPDFLoader as invoked through the production path
from base_indexer_toolkit:

    base_indexer_toolkit._apply_loaders_chunkers(document)
        → process_document_by_type(content=pdf_bytes, extension_source="file.pdf",
                                   document=base_doc, llm=None, chunking_config=...)
            → process_content_by_type(content, filename, llm, chunking_config)
                → AlitaPDFLoader(file_path=tmpfile, **loader_kwargs).load()

UI config shape sent from the platform:
    {".pdf": {"max_tokens": 512, "prompt": "", "use_default_prompt": False, "use_llm": False}}

KNOWN BUG
---------
AlitaPDFLoader.__init__ accepts **kwargs but never reads 'max_tokens'.
load() delegates entirely to PyPDFium2Loader → one Document per page.
Therefore PDF documents are NEVER chunked regardless of max_tokens value.
Tests in TestChunkingConfigPdf assert the CORRECT expected behavior and
will FAIL until the bug is fixed.
"""

import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from alita_sdk.runtime.langchain.constants import LOADER_MAX_TOKENS_DEFAULT
from alita_sdk.tools.utils.content_parser import (
    process_content_by_type,
    process_document_by_type,
)
from helpers import _TEST_DATA, read_bytes as _read_bytes, page_contents as _page_contents

# ---------------------------------------------------------------------------
# Paths to PDF test fixtures
# ---------------------------------------------------------------------------
_PDF_FILES = _TEST_DATA / "AlitaPDFLoader" / "files"
_PDF_TEXT_ONLY = _PDF_FILES / "pdf_text_only.pdf"    # 3-page text PDF, contains hyperlink on page 1
_PDF_WITH_IMAGE = _PDF_FILES / "pdf_with_image.pdf"  # 1-page PDF with embedded image


# ===========================================================================
# Smoke
# ===========================================================================

class TestSmokePdf:
    """Minimal wiring checks: pdf bytes → Documents returned."""

    def test_text_pdf_returns_documents(self):
        docs = list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf"))
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_text_pdf_page_content_is_non_empty(self):
        docs = list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf"))
        assert all(d.page_content.strip() for d in docs), (
            "All pages of a text PDF must produce non-empty page_content"
        )

    def test_image_pdf_returns_documents(self):
        """PDF with embedded image (no LLM) must still return documents."""
        docs = list(process_content_by_type(_read_bytes(_PDF_WITH_IMAGE), "img.pdf"))
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_none_content_returns_empty(self):
        assert list(process_content_by_type(None, "doc.pdf")) == []

    def test_returns_generator(self):
        result = process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf")
        assert isinstance(result, types.GeneratorType)


# ===========================================================================
# Multi-page behaviour
# ===========================================================================

class TestMultiPagePdf:
    """PyPDFium2Loader emits one Document per page; verify the count."""

    def test_three_page_pdf_yields_three_documents(self):
        """pdf_text_only.pdf has exactly 3 pages → must produce exactly 3 docs."""
        docs = list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf"))
        assert len(docs) == 3, (
            f"Expected 3 docs (one per page), got {len(docs)}"
        )

    def test_single_page_pdf_yields_one_document(self):
        docs = list(process_content_by_type(_read_bytes(_PDF_WITH_IMAGE), "img.pdf"))
        assert len(docs) == 1


# ===========================================================================
# chunking_config — UI scenarios for .pdf
# ===========================================================================

class TestChunkingConfigPdf:
    """
    UI sends {".pdf": {"max_tokens": <value>}} from the chunking panel.

    These tests assert the CORRECT expected behavior — the same contract
    that AlitaTextLoader, AlitaJSONLoader, etc. already fulfill.

    KNOWN BUG: AlitaPDFLoader ignores max_tokens entirely. load() delegates
    to PyPDFium2Loader which always emits one Document per page regardless
    of the token budget. The tests below will FAIL until that is fixed.
    """

    def test_max_tokens_512_equals_default_is_noop(self):
        """
        UI sends {".pdf": {"max_tokens": 512}}.
        512 == LOADER_MAX_TOKENS_DEFAULT → the != guard in process_content_by_type
        does NOT forward the value → identical to no-config call.
        """
        content = _read_bytes(_PDF_TEXT_ONLY)
        docs_no_config = list(process_content_by_type(content, "doc.pdf"))
        docs_ui_config = list(process_content_by_type(
            content, "doc.pdf",
            chunking_config={".pdf": {"max_tokens": LOADER_MAX_TOKENS_DEFAULT}},
        ))
        assert _page_contents(docs_ui_config) == _page_contents(docs_no_config)

    @pytest.mark.xfail(
        strict=True,
        reason="max_tokens is not consumed by AlitaPDFLoader — load() always returns "
               "one Document per page regardless of token budget — tracked in "
               "https://github.com/ProjectAlita/projectalita.github.io/issues/4081",
    )
    def test_smaller_max_tokens_should_produce_more_chunks(self):
        """
        UI sends {".pdf": {"max_tokens": 10}}.
        pdf_text_only.pdf has ~50 words per page; with a 10-token budget the
        text on each page must be split into multiple chunks, producing
        significantly more than 3 total documents.

        FAILS because of known bug: AlitaPDFLoader ignores max_tokens.
        load() → PyPDFium2Loader → always 1 doc/page regardless of budget.
        Fix: wire max_tokens through to a text splitter after extraction.
        """
        content = _read_bytes(_PDF_TEXT_ONLY)
        docs_default = list(process_content_by_type(content, "doc.pdf"))
        docs_small_tokens = list(process_content_by_type(
            content, "doc.pdf",
            chunking_config={".pdf": {"max_tokens": 10}},
        ))
        assert len(docs_small_tokens) > len(docs_default), (
            f"max_tokens=10 must split page text into more chunks than the default "
            f"{len(docs_default)} (one-per-page). Got {len(docs_small_tokens)}. "
            "AlitaPDFLoader never reads max_tokens — chunking is not implemented."
        )

    def test_config_for_other_extension_not_applied(self):
        """chunking_config keyed on .txt must not bleed into .pdf processing."""
        content = _read_bytes(_PDF_TEXT_ONLY)
        docs_no_config = list(process_content_by_type(content, "doc.pdf"))
        docs_wrong_ext = list(process_content_by_type(
            content, "doc.pdf",
            chunking_config={".txt": {"max_tokens": 1}},
        ))
        assert _page_contents(docs_wrong_ext) == _page_contents(docs_no_config)

    def test_full_ui_config_payload(self):
        """
        Replicate the exact payload the platform UI sends for a PDF:
            {".pdf": {"max_tokens": 512, "prompt": "", "use_default_prompt": False, "use_llm": False}}
        All values match defaults or are no-ops → output identical to bare call.
        """
        content = _read_bytes(_PDF_TEXT_ONLY)
        ui_config = {
            ".pdf": {
                "max_tokens": 512,          # == LOADER_MAX_TOKENS_DEFAULT → not forwarded
                "prompt": "",               # == default → not forwarded
                "use_default_prompt": False,  # == default → not forwarded
                "use_llm": False,           # == default → not forwarded
            }
        }
        docs_ui = list(process_content_by_type(content, "doc.pdf", chunking_config=ui_config))
        docs_bare = list(process_content_by_type(content, "doc.pdf"))
        assert _page_contents(docs_ui) == _page_contents(docs_bare)


# ===========================================================================
# LLM / prompt parameters
# ===========================================================================

class TestLlmPdf:
    """
    .pdf allowed_to_override includes use_llm, use_default_prompt, prompt.
    When use_llm=False (default), the llm argument is stripped before
    AlitaPDFLoader is instantiated.  load() uses PyPDFium2Loader — it never
    calls the LLM.  prompt and use_default_prompt have no effect in load().
    """

    def test_use_llm_false_llm_not_injected(self):
        """use_llm=False → llm kwarg must NOT reach AlitaPDFLoader."""
        content = _read_bytes(_PDF_TEXT_ONLY)
        mock_llm = MagicMock(name="mock_llm")
        docs_no_llm = list(process_content_by_type(content, "doc.pdf"))
        docs_with_llm_disabled = list(process_content_by_type(
            content, "doc.pdf",
            llm=mock_llm,
            chunking_config={".pdf": {"use_llm": False}},
        ))
        assert _page_contents(docs_with_llm_disabled) == _page_contents(docs_no_llm)
        mock_llm.assert_not_called()

    def test_mock_llm_without_config_never_called(self):
        """LLM passed as argument without use_llm=True in config → never called."""
        mock_llm = MagicMock(name="mock_llm")
        list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf", llm=mock_llm))
        mock_llm.assert_not_called()

    def test_empty_prompt_does_not_crash(self):
        """UI sends prompt='' → must not crash; output same as no-config."""
        content = _read_bytes(_PDF_TEXT_ONLY)
        docs_prompt_empty = list(process_content_by_type(
            content, "doc.pdf",
            chunking_config={".pdf": {"prompt": ""}},
        ))
        docs_no_config = list(process_content_by_type(content, "doc.pdf"))
        # prompt is the default value "" → not forwarded (== guard) → identical output
        assert _page_contents(docs_prompt_empty) == _page_contents(docs_no_config)

    def test_use_default_prompt_false_no_effect_on_load(self):
        """use_default_prompt=False is the default → not forwarded → no-op."""
        content = _read_bytes(_PDF_TEXT_ONLY)
        docs = list(process_content_by_type(
            content, "doc.pdf",
            chunking_config={".pdf": {"use_default_prompt": False}},
        ))
        assert len(docs) >= 1


# ===========================================================================
# Metadata assertions
# ===========================================================================

class TestMetadataPdf:
    """
    AlitaPDFLoader.load() sets chunk_id = doc.metadata['page'] (0-indexed).
    process_document_by_type overrides chunk_id with a sequential 1-based counter.
    """

    def test_load_sets_chunk_id_to_page_index(self):
        """
        process_content_by_type calls load() directly.
        PyPDFium2Loader sets metadata['page'] = 0-indexed page number.
        AlitaPDFLoader.load() copies it to metadata['chunk_id'].
        """
        docs = list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf"))
        assert len(docs) == 3
        # chunk_id should equal the 0-indexed page number
        for expected_page, doc in enumerate(docs):
            assert "chunk_id" in doc.metadata, "chunk_id must be set by AlitaPDFLoader.load()"
            assert doc.metadata["chunk_id"] == expected_page, (
                f"chunk_id should equal page index {expected_page}, "
                f"got {doc.metadata['chunk_id']}"
            )

    def test_process_document_by_type_overrides_chunk_id_sequentially(self):
        """
        process_document_by_type wraps process_content_by_type and reassigns
        chunk_id as a sequential 1-based counter — overriding the page-index
        value set by AlitaPDFLoader.load().
        """
        base_doc = Document(
            page_content="",
            metadata={
                "id": "test-pdf-001",
                "source": "https://storage.example.com/test.pdf",
            },
        )
        result_docs = list(process_document_by_type(
            content=_read_bytes(_PDF_TEXT_ONLY),
            extension_source="doc.pdf",
            document=base_doc,
        ))
        assert len(result_docs) == 3
        for i, doc in enumerate(result_docs, start=1):
            assert doc.metadata["chunk_id"] == i, (
                f"process_document_by_type must set chunk_id={i} (1-based), "
                f"got {doc.metadata['chunk_id']}"
            )

    def test_process_document_by_type_merges_base_metadata(self):
        """
        Base document metadata (id, source, custom fields) must be present
        in all output chunks — merged by process_document_by_type.
        """
        base_doc = Document(
            page_content="",
            metadata={
                "id": "base-id-42",
                "source": "https://storage.example.com/report.pdf",
                "project": "alita-sdk",
                "indexed_by": "indexer_v2",
            },
        )
        result_docs = list(process_document_by_type(
            content=_read_bytes(_PDF_TEXT_ONLY),
            extension_source="doc.pdf",
            document=base_doc,
        ))
        for doc in result_docs:
            assert doc.metadata.get("id") == "base-id-42"
            assert doc.metadata.get("project") == "alita-sdk"
            assert doc.metadata.get("indexed_by") == "indexer_v2"

    def test_metadata_has_source_field(self):
        """PyPDFium2Loader sets metadata['source'] = file path."""
        docs = list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf"))
        for doc in docs:
            assert "source" in doc.metadata, "source must be in metadata"


# ===========================================================================
# Hyperlink extraction (get_content path vs load path)
# ===========================================================================

class TestHyperlinkPdf:
    """
    AlitaPDFLoader has two code paths:
      - get_content(): extracts and formats hyperlinks as Markdown [text](url)
      - load(): delegates to PyPDFium2Loader — hyperlinks are NOT extracted

    These tests document which path is used in production (load) and ensure
    the plain text is still extracted correctly from pages that contain links.
    """

    def test_page_with_hyperlink_returns_text_content(self):
        """
        Page 1 of pdf_text_only.pdf contains a hyperlink.
        load() (PyPDFium2Loader path) must return text content from that page.
        """
        docs = list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf"))
        first_page = docs[0]
        # The page contains "Visit our website" and other text
        assert len(first_page.page_content.strip()) > 0, (
            "Page with hyperlink must still return text content via load() path"
        )

    def test_hyperlink_not_formatted_as_markdown_in_load_path(self):
        """
        load() uses PyPDFium2Loader which does NOT format hyperlinks.
        The markdown [text](url) format is only produced by get_content().
        This test documents the current behaviour: no markdown links in output.
        """
        docs = list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "doc.pdf"))
        first_page_content = docs[0].page_content
        # Markdown link format should NOT appear in load() output
        assert "](" not in first_page_content, (
            "load() path (PyPDFium2Loader) must not produce markdown hyperlinks. "
            "Hyperlink formatting only happens in get_content() which is not called "
            "from the base_indexer_toolkit production path."
        )


# ===========================================================================
# Image PDF — no LLM
# ===========================================================================

class TestImagePdf:
    """
    A PDF containing an embedded image but no meaningful text.
    Without LLM (use_llm=False), the image content must be ignored.
    """

    def test_image_pdf_no_llm_returns_doc_without_crashing(self):
        content = _read_bytes(_PDF_WITH_IMAGE)
        docs = list(process_content_by_type(content, "img.pdf"))
        assert len(docs) >= 1

    def test_image_pdf_no_llm_does_not_include_image_bytes(self):
        """
        With extract_images=False (default when use_llm=False),
        image bytes must not appear in page_content.
        """
        content = _read_bytes(_PDF_WITH_IMAGE)
        docs = list(process_content_by_type(content, "img.pdf"))
        for doc in docs:
            assert isinstance(doc.page_content, str), "page_content must be a string"
            # No raw binary-looking content
            assert "\x00" not in doc.page_content, (
                "page_content must not contain NUL bytes"
            )

    def test_image_pdf_with_ui_config_no_crash(self):
        """Full UI config payload against image PDF must not crash."""
        ui_config = {
            ".pdf": {
                "max_tokens": 512,
                "prompt": "",
                "use_default_prompt": False,
                "use_llm": False,
            }
        }
        docs = list(process_content_by_type(
            _read_bytes(_PDF_WITH_IMAGE), "img.pdf",
            chunking_config=ui_config,
        ))
        assert len(docs) >= 1


# ===========================================================================
# loaders_map mutation guard
# ===========================================================================

class TestLoadersMapNotMutatedPdf:
    """
    Regression: shared loaders_map[".pdf"]["kwargs"] must never be mutated
    across calls (fixed by the dict-copy in process_content_by_type).
    """

    def test_kwargs_unchanged_after_plain_call(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".pdf"]["kwargs"])
        list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "a.pdf"))
        list(process_content_by_type(_read_bytes(_PDF_TEXT_ONLY), "b.pdf"))
        assert loaders_map[".pdf"]["kwargs"] == original

    def test_kwargs_unchanged_with_chunking_config(self):
        from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
        original = dict(loaders_map[".pdf"]["kwargs"])
        list(process_content_by_type(
            _read_bytes(_PDF_TEXT_ONLY), "c.pdf",
            chunking_config={".pdf": {"max_tokens": 128, "use_llm": False}},
        ))
        assert loaders_map[".pdf"]["kwargs"] == original
