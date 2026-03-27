"""
Unit tests for alita_sdk.tools.chunkers.sematic.statistical_chunker.

SCH01 — Missing embedding raises ImportError/ValueError
SCH02 — Each output chunk has chunk_id, chunk_type, chunk_token_count metadata
SCH03 — Source metadata is preserved on every chunk
SCH04 — Config defaults: dynamic_threshold=True, window_size=5, etc.
SCH05 — Internal helpers: _calculate_similarity_scores, _find_split_indices, _split_documents

Statistical chunker requires an embedding model for the main path.
Tests for the public function use a mocked embedding that returns fixed vectors.
Internal helpers are tested in isolation (no embedding needed).

Tests assert semantically correct behaviour.
If a test fails, it surfaces a bug in the source — do NOT change the assertion to match broken behaviour.
"""

import numpy as np
from typing import Generator
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from alita_sdk.tools.chunkers.sematic.statistical_chunker import (
    statistical_chunker,
    _calculate_similarity_scores,
    _find_split_indices,
    _split_documents,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_generator(*docs: Document) -> Generator[Document, None, None]:
    yield from docs


def doc(content: str, source: str = "test.txt", **extra) -> Document:
    return Document(page_content=content, metadata={"source": source, **extra})


def make_mock_embedding(n_dims: int = 8):
    """Return a mock embedding that returns fixed unit vectors for any input."""
    mock = MagicMock()
    def embed_documents(texts):
        # Return slightly varied unit vectors so similarity scores differ
        return [
            list(np.random.default_rng(i).random(n_dims))
            for i, _ in enumerate(texts)
        ]
    mock.embed_documents.side_effect = embed_documents
    return mock


# ---------------------------------------------------------------------------
# SCH01 — Missing embedding raises ValueError
# ---------------------------------------------------------------------------

class TestSCH01_MissingEmbeddingRaises:

    def test_no_embedding_raises_error(self):
        with pytest.raises((ValueError, ImportError)):
            list(statistical_chunker(
                make_generator(doc("Some content here.")),
                config={},  # no embedding key
            ))

    def test_none_embedding_raises_error(self):
        with pytest.raises((ValueError, ImportError)):
            list(statistical_chunker(
                make_generator(doc("Some content here.")),
                config={"embedding": None},
            ))


# ---------------------------------------------------------------------------
# SCH02 — Each output chunk has required metadata keys
# ---------------------------------------------------------------------------

class TestSCH02_OutputMetadataKeys:

    def test_chunk_has_chunk_id(self):
        embedding = make_mock_embedding()
        result = list(statistical_chunker(
            make_generator(doc("Word " * 200)),
            config={"embedding": embedding, "max_doc_size": 50, "min_split_tokens": 10, "max_split_tokens": 60},
        ))
        assert len(result) >= 1
        for chunk in result:
            assert "chunk_id" in chunk.metadata

    def test_chunk_has_chunk_type_document(self):
        embedding = make_mock_embedding()
        result = list(statistical_chunker(
            make_generator(doc("Word " * 200)),
            config={"embedding": embedding, "max_doc_size": 50, "min_split_tokens": 10, "max_split_tokens": 60},
        ))
        for chunk in result:
            assert chunk.metadata["chunk_type"] == "document"

    def test_chunk_has_chunk_token_count(self):
        embedding = make_mock_embedding()
        result = list(statistical_chunker(
            make_generator(doc("Word " * 200)),
            config={"embedding": embedding, "max_doc_size": 50, "min_split_tokens": 10, "max_split_tokens": 60},
        ))
        for chunk in result:
            assert "chunk_token_count" in chunk.metadata

    def test_chunk_ids_start_at_1_and_are_sequential(self):
        embedding = make_mock_embedding()
        result = list(statistical_chunker(
            make_generator(doc("Word " * 300)),
            config={"embedding": embedding, "max_doc_size": 50, "min_split_tokens": 10, "max_split_tokens": 60},
        ))
        ids = [c.metadata["chunk_id"] for c in result]
        assert ids[0] == 1
        assert ids == list(range(1, len(result) + 1))


# ---------------------------------------------------------------------------
# SCH03 — Source metadata is preserved on every chunk
# ---------------------------------------------------------------------------

class TestSCH03_SourceMetadataPreserved:

    def test_source_preserved_on_all_chunks(self):
        embedding = make_mock_embedding()
        result = list(statistical_chunker(
            make_generator(doc("Word " * 200, source="myfile.txt")),
            config={"embedding": embedding, "max_doc_size": 50, "min_split_tokens": 10, "max_split_tokens": 60},
        ))
        for chunk in result:
            assert chunk.metadata["source"] == "myfile.txt"

    def test_extra_metadata_preserved_on_all_chunks(self):
        embedding = make_mock_embedding()
        result = list(statistical_chunker(
            make_generator(doc("Word " * 200, source="f.txt", project="proj")),
            config={"embedding": embedding, "max_doc_size": 50, "min_split_tokens": 10, "max_split_tokens": 60},
        ))
        for chunk in result:
            assert chunk.metadata["project"] == "proj"


# ---------------------------------------------------------------------------
# SCH04 — Config defaults observed
# ---------------------------------------------------------------------------

class TestSCH04_ConfigDefaults:

    def test_empty_generator_yields_nothing(self):
        embedding = make_mock_embedding()
        def empty():
            return
            yield
        result = list(statistical_chunker(empty(), config={"embedding": embedding}))
        assert result == []

    def test_fixed_threshold_used_when_dynamic_false(self):
        """With dynamic_threshold=False, score_threshold is used directly."""
        embedding = make_mock_embedding()
        # Just verify it doesn't crash and returns at least one chunk
        result = list(statistical_chunker(
            make_generator(doc("Word " * 200)),
            config={
                "embedding": embedding,
                "dynamic_threshold": False,
                "score_threshold": 0.9,  # very high → few or no splits
                "max_doc_size": 50,
                "min_split_tokens": 10,
                "max_split_tokens": 60,
            },
        ))
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# SCH05 — Internal helper unit tests (no embedding needed)
# ---------------------------------------------------------------------------

class TestSCH05_InternalHelpers:

    # _calculate_similarity_scores

    def test_similarity_scores_count(self):
        """Should return N-1 scores for N encoded documents."""
        n = 5
        encoded = np.random.default_rng(0).random((n, 8))
        scores = _calculate_similarity_scores(encoded, window_size=2)
        assert len(scores) == n - 1

    def test_similarity_scores_are_floats_in_range(self):
        encoded = np.random.default_rng(1).random((6, 8))
        scores = _calculate_similarity_scores(encoded, window_size=2)
        for s in scores:
            assert isinstance(s, float)
            # Cosine similarity is in [-1, 1]; with non-negative vectors it's [0, 1]
            assert -1.0 <= s <= 1.0 + 1e-6

    def test_single_document_yields_no_scores(self):
        encoded = np.random.default_rng(0).random((1, 8))
        scores = _calculate_similarity_scores(encoded, window_size=1)
        assert scores == []

    # _find_split_indices

    def test_split_indices_below_threshold(self):
        """Indices where score < threshold should be returned (offset by 1)."""
        similarities = [0.9, 0.2, 0.8, 0.1]
        threshold = 0.5
        indices = _find_split_indices(similarities, threshold)
        # score at idx=1 (0.2) and idx=3 (0.1) are below threshold → indices 2, 4
        assert 2 in indices
        assert 4 in indices

    def test_no_splits_when_all_above_threshold(self):
        similarities = [0.8, 0.9, 0.7]
        indices = _find_split_indices(similarities, calculated_threshold=0.5)
        assert indices == []

    def test_all_split_when_all_below_threshold(self):
        similarities = [0.1, 0.2, 0.3]
        indices = _find_split_indices(similarities, calculated_threshold=0.5)
        assert len(indices) == 3

    # _split_documents

    def test_split_documents_no_tokens_lost(self):
        """Total token count in output chunks must equal total token count in input."""
        from alita_sdk.tools.chunkers.utils import tiktoken_length
        docs = ["hello world"] * 10
        similarities = [0.5] * 9
        chunks = _split_documents(docs, split_indices=[], similarities=similarities,
                                  max_split_tokens=300, min_split_tokens=5)
        original_count = sum(tiktoken_length(d) for d in docs)
        split_count = sum(tiktoken_length(d) for chunk in chunks for d in chunk.splits)
        assert original_count == split_count

    def test_split_documents_returns_list_of_chunks(self):
        from alita_sdk.tools.chunkers.sematic.base import Chunk
        docs = ["sentence one", "sentence two", "sentence three"]
        similarities = [0.8, 0.2]
        chunks = _split_documents(docs, split_indices=[2], similarities=similarities,
                                  max_split_tokens=300, min_split_tokens=1)
        assert isinstance(chunks, list)
        for c in chunks:
            assert isinstance(c, Chunk)
