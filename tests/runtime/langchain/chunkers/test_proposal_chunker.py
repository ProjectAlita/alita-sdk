"""
Unit tests for alita_sdk.tools.chunkers.sematic.proposal_chunker.

PCH01 — Missing LLM raises ValueError
PCH02 — Each chunk group produces title, summary, propositions, document chunks
PCH03 — chunk_id metadata increments per proposition group
PCH04 — Source metadata preserved; doc too long triggers pre-split

proposal_chunker requires a real LLM for the main path.
Tests mock the LLM with a fake structured-output responder.

Tests assert semantically correct behaviour.
If a test fails, it surfaces a bug in the source — do NOT change the assertion to match broken behaviour.
"""

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from alita_sdk.tools.chunkers.sematic.proposal_chunker import (
    proposal_chunker,
    AgenticChunker,
    ChunkAnalysis,
    ChunkDetails,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_generator(*docs: Document) -> Generator[Document, None, None]:
    yield from docs


def doc(content: str, source: str = "test.txt", **extra) -> Document:
    return Document(page_content=content, metadata={"source": source, **extra})


def make_mock_llm(chunks: list[dict]):
    """Build a mock LLM whose with_structured_output returns fixed ChunkAnalysis."""
    analysis = ChunkAnalysis(chunks=[
        ChunkDetails(
            chunk_title=c["title"],
            chunk_summary=c["summary"],
            propositions=c["propositions"],
        )
        for c in chunks
    ])
    structured_mock = MagicMock()
    structured_mock.invoke.return_value = analysis

    llm_mock = MagicMock()
    llm_mock.with_structured_output.return_value = structured_mock
    return llm_mock


SAMPLE_CHUNKS = [
    {
        "title": "About Apples",
        "summary": "This chunk discusses apples as a type of fruit.",
        "propositions": ["Apples are fruit.", "Apples are red or green."],
    }
]


# ---------------------------------------------------------------------------
# PCH01 — Missing LLM raises ValueError
# ---------------------------------------------------------------------------

class TestPCH01_MissingLLMRaises:

    def test_no_llm_raises_value_error(self):
        with pytest.raises(ValueError, match="Missing LLM model"):
            list(proposal_chunker(
                make_generator(doc("Some text content here.")),
                config={},
            ))

    def test_none_llm_raises_value_error(self):
        with pytest.raises(ValueError, match="Missing LLM model"):
            list(proposal_chunker(
                make_generator(doc("Some text content here.")),
                config={"llm": None},
            ))


# ---------------------------------------------------------------------------
# PCH02 — Each proposition group produces 4 document types
# ---------------------------------------------------------------------------

class TestPCH02_FourDocumentsPerPropositionGroup:
    """Each chunk from AgenticChunker yields: title, summary, propositions, document."""

    def test_single_proposition_group_yields_four_chunks(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        result = list(proposal_chunker(
            make_generator(doc("Apples are a type of fruit.")),
            config={"llm": llm},
        ))
        assert len(result) == 4

    def test_chunk_types_are_title_summary_propositions_document(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        result = list(proposal_chunker(
            make_generator(doc("Apples are a type of fruit.")),
            config={"llm": llm},
        ))
        types = [c.metadata["chunk_type"] for c in result]
        assert types == ["title", "summary", "propositions", "document"]

    def test_title_chunk_content_matches_llm_output(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        result = list(proposal_chunker(
            make_generator(doc("Apples are a type of fruit.")),
            config={"llm": llm},
        ))
        title_chunks = [c for c in result if c.metadata["chunk_type"] == "title"]
        assert title_chunks[0].page_content == "About Apples"

    def test_summary_chunk_content_matches_llm_output(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        result = list(proposal_chunker(
            make_generator(doc("Apples are a type of fruit.")),
            config={"llm": llm},
        ))
        summary_chunks = [c for c in result if c.metadata["chunk_type"] == "summary"]
        assert "apples" in summary_chunks[0].page_content.lower()

    def test_propositions_chunk_content_contains_each_proposition(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        result = list(proposal_chunker(
            make_generator(doc("Apples are a type of fruit.")),
            config={"llm": llm},
        ))
        prop_chunks = [c for c in result if c.metadata["chunk_type"] == "propositions"]
        content = prop_chunks[0].page_content
        assert "Apples are fruit." in content
        assert "Apples are red or green." in content

    def test_document_chunk_content_is_original_split_text(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        original_text = "Apples are a type of fruit."
        result = list(proposal_chunker(
            make_generator(doc(original_text)),
            config={"llm": llm},
        ))
        doc_chunks = [c for c in result if c.metadata["chunk_type"] == "document"]
        assert doc_chunks[0].page_content == original_text


# ---------------------------------------------------------------------------
# PCH03 — chunk_id metadata increments per proposition group
# ---------------------------------------------------------------------------

class TestPCH03_ChunkIdMetadata:

    def test_all_four_chunks_share_same_chunk_id(self):
        """All 4 chunks from a single proposition group share the same chunk_id."""
        llm = make_mock_llm(SAMPLE_CHUNKS)
        result = list(proposal_chunker(
            make_generator(doc("Some content.")),
            config={"llm": llm},
        ))
        ids = {c.metadata["chunk_id"] for c in result}
        assert len(ids) == 1
        assert 1 in ids

    def test_two_proposition_groups_have_different_chunk_ids(self):
        two_chunks = [
            {"title": "T1", "summary": "S1", "propositions": ["P1"]},
            {"title": "T2", "summary": "S2", "propositions": ["P2"]},
        ]
        llm = make_mock_llm(two_chunks)
        result = list(proposal_chunker(
            make_generator(doc("Content A. Content B.")),
            config={"llm": llm},
        ))
        ids = [c.metadata["chunk_id"] for c in result]
        assert 1 in ids
        assert 2 in ids

    def test_chunk_title_in_document_chunk_metadata(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        result = list(proposal_chunker(
            make_generator(doc("Apples are fruit.")),
            config={"llm": llm},
        ))
        doc_chunks = [c for c in result if c.metadata["chunk_type"] == "document"]
        assert doc_chunks[0].metadata.get("chunk_title") == "About Apples"


# ---------------------------------------------------------------------------
# PCH04 — Source metadata preserved; long doc triggers pre-split
# ---------------------------------------------------------------------------

class TestPCH04_MetadataAndLongDocSplit:

    def test_source_metadata_preserved_on_all_chunks(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        result = list(proposal_chunker(
            make_generator(doc("Apples are fruit.", source="produce.txt")),
            config={"llm": llm},
        ))
        for chunk in result:
            assert chunk.metadata["source"] == "produce.txt"

    def test_empty_generator_yields_nothing(self):
        llm = make_mock_llm(SAMPLE_CHUNKS)
        def empty():
            return
            yield
        result = list(proposal_chunker(empty(), config={"llm": llm}))
        assert result == []

    def test_long_doc_still_produces_chunks(self):
        """A document exceeding max_doc_tokens is pre-split before LLM chunking."""
        llm = make_mock_llm(SAMPLE_CHUNKS)
        long_text = "word " * 2000  # ~2000 tokens, well above default 1024
        result = list(proposal_chunker(
            make_generator(doc(long_text)),
            config={"llm": llm, "max_doc_tokens": 100},
        ))
        # LLM was called multiple times (once per pre-split)
        assert llm.with_structured_output.return_value.invoke.call_count >= 2

    def test_llm_error_in_create_chunkes_returns_empty(self):
        """If LLM raises, AgenticChunker.create_chunkes returns [] and no chunks yielded."""
        broken_llm = MagicMock()
        structured = MagicMock()
        structured.invoke.side_effect = RuntimeError("LLM failure")
        broken_llm.with_structured_output.return_value = structured

        result = list(proposal_chunker(
            make_generator(doc("Some text.")),
            config={"llm": broken_llm},
        ))
        # With empty propositions, no chunks should be yielded
        assert result == []
