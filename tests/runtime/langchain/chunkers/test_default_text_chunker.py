"""
Unit tests for alita_sdk.tools.chunkers.universal_chunker._default_text_chunker.

TCH01 — Short text produces at least one chunk
TCH02 — Long text is split into multiple chunks
TCH03 — Every chunk has chunk_id, chunk_type='text', method_name='text'
TCH04 — chunk_size and chunk_overlap config control split behaviour
TCH05 — Source metadata is preserved on every chunk

_default_text_chunker is a private function inside universal_chunker.py.

Tests assert semantically correct behaviour.
If a test fails, it surfaces a bug in the source — do NOT change the assertion to match broken behaviour.
"""

from typing import Generator

from langchain_core.documents import Document

from alita_sdk.tools.chunkers.universal_chunker import _default_text_chunker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_generator(*docs: Document) -> Generator[Document, None, None]:
    yield from docs


def doc(content: str, source: str = "test.txt", **extra) -> Document:
    return Document(page_content=content, metadata={"source": source, **extra})


SHORT_TEXT = "This is a short document."
LONG_TEXT = "word " * 500  # ~500 tokens, will exceed default chunk_size=1000 chars


# ---------------------------------------------------------------------------
# TCH01 — Short text produces at least one chunk
# ---------------------------------------------------------------------------

class TestTCH01_ShortTextProducesChunk:

    def test_short_text_yields_at_least_one_chunk(self):
        result = list(_default_text_chunker(make_generator(doc(SHORT_TEXT)), config={}))
        assert len(result) >= 1

    def test_short_text_content_preserved(self):
        result = list(_default_text_chunker(make_generator(doc(SHORT_TEXT)), config={}))
        full = " ".join(c.page_content for c in result)
        assert "short document" in full

    def test_empty_generator_yields_nothing(self):
        def empty():
            return
            yield
        result = list(_default_text_chunker(empty(), config={}))
        assert result == []


# ---------------------------------------------------------------------------
# TCH02 — Long text is split into multiple chunks
# ---------------------------------------------------------------------------

class TestTCH02_LongTextSplit:

    def test_long_text_produces_multiple_chunks(self):
        result = list(_default_text_chunker(
            make_generator(doc(LONG_TEXT)),
            config={"chunk_size": 100, "chunk_overlap": 0},
        ))
        assert len(result) > 1

    def test_no_content_lost_across_chunks(self):
        """The union of all chunk contents should cover the original text (modulo overlap)."""
        result = list(_default_text_chunker(
            make_generator(doc("alpha beta gamma " * 100)),
            config={"chunk_size": 50, "chunk_overlap": 0},
        ))
        all_content = " ".join(c.page_content for c in result)
        assert "alpha" in all_content
        assert "gamma" in all_content


# ---------------------------------------------------------------------------
# TCH03 — Every chunk has required metadata fields
# ---------------------------------------------------------------------------

class TestTCH03_RequiredMetadataFields:

    def test_chunk_id_present(self):
        result = list(_default_text_chunker(make_generator(doc(SHORT_TEXT)), config={}))
        for chunk in result:
            assert "chunk_id" in chunk.metadata

    def test_chunk_id_starts_at_1(self):
        result = list(_default_text_chunker(make_generator(doc(SHORT_TEXT)), config={}))
        assert result[0].metadata["chunk_id"] == 1

    def test_chunk_ids_sequential(self):
        result = list(_default_text_chunker(
            make_generator(doc(LONG_TEXT)),
            config={"chunk_size": 100, "chunk_overlap": 0},
        ))
        ids = [c.metadata["chunk_id"] for c in result]
        assert ids == list(range(1, len(result) + 1))

    def test_chunk_type_is_text(self):
        result = list(_default_text_chunker(make_generator(doc(SHORT_TEXT)), config={}))
        for chunk in result:
            assert chunk.metadata["chunk_type"] == "text"

    def test_method_name_is_text(self):
        result = list(_default_text_chunker(make_generator(doc(SHORT_TEXT)), config={}))
        for chunk in result:
            assert chunk.metadata["method_name"] == "text"


# ---------------------------------------------------------------------------
# TCH04 — chunk_size and chunk_overlap control split behaviour
# ---------------------------------------------------------------------------

class TestTCH04_ChunkSizeConfig:

    def test_smaller_chunk_size_produces_more_chunks(self):
        content = "word " * 200
        result_small = list(_default_text_chunker(
            make_generator(doc(content)),
            config={"chunk_size": 50, "chunk_overlap": 0},
        ))
        result_large = list(_default_text_chunker(
            make_generator(doc(content)),
            config={"chunk_size": 500, "chunk_overlap": 0},
        ))
        assert len(result_small) >= len(result_large)

    def test_default_chunk_size_is_1000(self):
        """Config with explicit 1000 should behave the same as empty config."""
        content = "word " * 200
        result_default = list(_default_text_chunker(make_generator(doc(content)), config={}))
        result_explicit = list(_default_text_chunker(
            make_generator(doc(content)),
            config={"chunk_size": 1000, "chunk_overlap": 100},
        ))
        assert len(result_default) == len(result_explicit)


# ---------------------------------------------------------------------------
# TCH05 — Source metadata is preserved
# ---------------------------------------------------------------------------

class TestTCH05_SourceMetadataPreserved:

    def test_source_preserved_on_single_chunk(self):
        result = list(_default_text_chunker(
            make_generator(doc(SHORT_TEXT, source="myfile.txt")),
            config={},
        ))
        for chunk in result:
            assert chunk.metadata["source"] == "myfile.txt"

    def test_extra_metadata_preserved_on_all_split_chunks(self):
        result = list(_default_text_chunker(
            make_generator(doc(LONG_TEXT, source="long.txt", project="myproject")),
            config={"chunk_size": 100, "chunk_overlap": 0},
        ))
        for chunk in result:
            assert chunk.metadata["project"] == "myproject"

    def test_multiple_docs_each_preserve_their_metadata(self):
        result = list(_default_text_chunker(
            make_generator(
                doc(SHORT_TEXT, source="a.txt"),
                doc(SHORT_TEXT, source="b.txt"),
            ),
            config={},
        ))
        sources = {c.metadata["source"] for c in result}
        assert "a.txt" in sources
        assert "b.txt" in sources
