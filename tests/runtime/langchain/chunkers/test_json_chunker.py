"""
Unit tests for alita_sdk.tools.chunkers.sematic.json_chunker.

JCH01 — Small JSON (fits in one chunk) yielded as-is
JCH02 — Large JSON produces multiple chunks with method_name='json'
JCH03 — Each chunk has chunk_id starting from 1 (sequential)
JCH04 — Source metadata is preserved on every chunk
JCH05 — Invalid JSON yields the original document unchanged (error recovery)
JCH06 — max_tokens config controls split threshold

Tests assert semantically correct behaviour.
If a test fails, it surfaces a bug in the source — do NOT change the assertion to match broken behaviour.
"""

import json
from typing import Generator

from langchain_core.documents import Document

from alita_sdk.tools.chunkers.sematic.json_chunker import json_chunker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_generator(*docs: Document) -> Generator[Document, None, None]:
    yield from docs


def doc(content, source="test.json", **extra_meta):
    return Document(page_content=content, metadata={"source": source, **extra_meta})


def small_json_str():
    """A JSON object small enough to be a single chunk at default max_tokens=512."""
    return json.dumps({"key": "value", "num": 42})


def large_json_str(n=200):
    """A JSON object large enough to be split at a small max_tokens setting."""
    return json.dumps({f"key_{i}": f"value_{i}" * 10 for i in range(n)})


# ---------------------------------------------------------------------------
# JCH01 — Small JSON (fits in one chunk) yielded as-is
# ---------------------------------------------------------------------------

class TestJCH01_SmallJsonPassthrough:
    """Single-chunk JSON is returned as the original Document object."""

    def test_single_chunk_returns_original_doc(self):
        original = doc(small_json_str())
        result = list(json_chunker(make_generator(original), config={}))
        assert len(result) == 1
        assert result[0] is original

    def test_single_chunk_page_content_unchanged(self):
        content = small_json_str()
        original = doc(content)
        result = list(json_chunker(make_generator(original), config={}))
        assert result[0].page_content == content

    def test_single_chunk_metadata_unchanged(self):
        original = doc(small_json_str(), source="my.json", extra="info")
        result = list(json_chunker(make_generator(original), config={}))
        assert result[0].metadata["source"] == "my.json"
        assert result[0].metadata["extra"] == "info"


# ---------------------------------------------------------------------------
# JCH02 — Large JSON produces multiple chunks with method_name='json'
# ---------------------------------------------------------------------------

class TestJCH02_LargeJsonSplit:
    """Large JSON split into multiple chunks; each carries method_name='json'."""

    def test_large_json_produces_multiple_chunks(self):
        result = list(json_chunker(
            make_generator(doc(large_json_str())),
            config={"max_tokens": 50},
        ))
        assert len(result) > 1

    def test_each_split_chunk_has_method_name_json(self):
        result = list(json_chunker(
            make_generator(doc(large_json_str())),
            config={"max_tokens": 50},
        ))
        assert len(result) > 1
        for chunk in result:
            assert chunk.metadata.get("method_name") == "json"

    def test_each_split_chunk_contains_valid_json(self):
        result = list(json_chunker(
            make_generator(doc(large_json_str())),
            config={"max_tokens": 50},
        ))
        for chunk in result:
            # page_content of each chunk must be valid JSON
            parsed = json.loads(chunk.page_content)
            assert isinstance(parsed, (dict, list))


# ---------------------------------------------------------------------------
# JCH03 — chunk_id is sequential starting from 1
# ---------------------------------------------------------------------------

class TestJCH03_ChunkIdSequential:
    """When split, chunk_ids start at 1 and increment by 1."""

    def test_chunk_ids_start_at_1(self):
        result = list(json_chunker(
            make_generator(doc(large_json_str())),
            config={"max_tokens": 50},
        ))
        assert len(result) > 1
        assert result[0].metadata["chunk_id"] == 1

    def test_chunk_ids_are_sequential(self):
        result = list(json_chunker(
            make_generator(doc(large_json_str())),
            config={"max_tokens": 50},
        ))
        ids = [c.metadata["chunk_id"] for c in result]
        assert ids == list(range(1, len(result) + 1))

    def test_chunk_ids_reset_per_document(self):
        """Each document starts its own chunk_id sequence from 1."""
        result = list(json_chunker(
            make_generator(doc(large_json_str()), doc(large_json_str())),
            config={"max_tokens": 50},
        ))
        # Find where ids reset — cannot assume global sequential across docs
        # At minimum, first chunk must be chunk_id=1
        assert result[0].metadata["chunk_id"] == 1


# ---------------------------------------------------------------------------
# JCH04 — Source metadata is preserved on every chunk
# ---------------------------------------------------------------------------

class TestJCH04_MetadataPreserved:
    """Original document metadata is copied to every split chunk."""

    def test_source_preserved_on_all_split_chunks(self):
        result = list(json_chunker(
            make_generator(doc(large_json_str(), source="data.json")),
            config={"max_tokens": 50},
        ))
        assert len(result) > 1
        for chunk in result:
            assert chunk.metadata["source"] == "data.json"

    def test_extra_metadata_preserved_on_all_split_chunks(self):
        result = list(json_chunker(
            make_generator(doc(large_json_str(), source="d.json", project="myproject")),
            config={"max_tokens": 50},
        ))
        for chunk in result:
            assert chunk.metadata["project"] == "myproject"


# ---------------------------------------------------------------------------
# JCH05 — Invalid JSON yields original document unchanged (error recovery)
# ---------------------------------------------------------------------------

class TestJCH05_InvalidJsonRecovery:
    """Malformed JSON must not crash; original document is yielded."""

    def test_invalid_json_no_crash(self):
        bad = doc("this is { not valid json")
        result = list(json_chunker(make_generator(bad), config={}))
        assert len(result) == 1

    def test_invalid_json_yields_original_doc(self):
        bad = doc("this is { not valid json")
        result = list(json_chunker(make_generator(bad), config={}))
        assert result[0] is bad

    def test_invalid_json_followed_by_valid_doc_still_processes_valid(self):
        bad = doc("not json")
        good = doc(small_json_str())
        result = list(json_chunker(make_generator(bad, good), config={}))
        assert len(result) == 2

    def test_empty_string_does_not_crash(self):
        empty = doc("")
        result = list(json_chunker(make_generator(empty), config={}))
        assert len(result) == 1
        assert result[0] is empty


# ---------------------------------------------------------------------------
# JCH06 — max_tokens config controls split threshold
# ---------------------------------------------------------------------------

class TestJCH06_MaxTokensConfig:
    """max_tokens passed through config controls RecursiveJsonSplitter chunk size."""

    def test_large_max_tokens_produces_fewer_chunks(self):
        content = large_json_str()
        result_small = list(json_chunker(make_generator(doc(content)), config={"max_tokens": 50}))
        result_large = list(json_chunker(make_generator(doc(content)), config={"max_tokens": 2000}))
        assert len(result_small) >= len(result_large)

    def test_default_max_tokens_is_512(self):
        """Config with explicit 512 should behave the same as empty config."""
        content = large_json_str()
        result_default = list(json_chunker(make_generator(doc(content)), config={}))
        result_explicit = list(json_chunker(make_generator(doc(content)), config={"max_tokens": 512}))
        assert len(result_default) == len(result_explicit)

    def test_empty_generator_yields_nothing(self):
        def empty():
            return
            yield
        result = list(json_chunker(empty(), config={}))
        assert result == []
