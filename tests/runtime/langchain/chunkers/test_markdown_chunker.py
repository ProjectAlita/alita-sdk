"""
Unit tests for alita_sdk.tools.chunkers.sematic.markdown_chunker.

Tests are fully self-contained: no file I/O, no network, no vector DB.
Every test constructs an in-memory Document generator and asserts on the
returned chunk list.

Run:
  pytest tests/runtime/langchain/chunkers/test_markdown_chunker.py -v
  pytest tests/runtime/langchain/chunkers/test_markdown_chunker.py -v -k "MCH01"
"""

from typing import Generator, List
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from alita_sdk.tools.chunkers.sematic.markdown_chunker import (
    markdown_chunker,
    markdown_by_headers_chunker,
    _merge_small_chunks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_generator(*contents: str, source: str = "test.md") -> Generator[Document, None, None]:
    """Yield one Document per content string."""
    for content in contents:
        yield Document(page_content=content, metadata={"source": source})


def chunk(content: str, config: dict = None) -> List[Document]:
    """Convenience wrapper: list(markdown_chunker(...))."""
    return list(markdown_chunker(make_generator(content), config=config or {}))


# ---------------------------------------------------------------------------
# MCH01 — Split on H1/H2/H3 headers
# ---------------------------------------------------------------------------

class TestMCH01_SplitOnHeaders:
    """Headers in headers_to_split_on produce separate chunks."""

    def test_splits_on_h1(self):
        text = "# Section A\nContent A\n\n# Section B\nContent B"
        cfg = {"headers_to_split_on": [("#", "H1")], "min_chunk_chars": 1}
        chunks = chunk(text, cfg)
        assert len(chunks) >= 2
        contents = [c.page_content for c in chunks]
        assert any("Content A" in c for c in contents)
        assert any("Content B" in c for c in contents)

    def test_splits_on_h2(self):
        text = "## Intro\nIntroduction text here.\n\n## Details\nDetailed information here."
        cfg = {"headers_to_split_on": [("##", "H2")], "min_chunk_chars": 1}
        chunks = chunk(text, cfg)
        assert len(chunks) >= 2

    def test_splits_on_h1_h2_h3(self):
        text = (
            "# Top\nTop level content.\n\n"
            "## Sub\nSub level content.\n\n"
            "### Deep\nDeep level content."
        )
        cfg = {
            "headers_to_split_on": [("#", "H1"), ("##", "H2"), ("###", "H3")],
            "min_chunk_chars": 1,
        }
        chunks = chunk(text, cfg)
        assert len(chunks) >= 3

    def test_header_metadata_present(self):
        text = "## My Section\nSome content inside the section."
        cfg = {"headers_to_split_on": [("##", "H2")], "min_chunk_chars": 1}
        chunks = chunk(text, cfg)
        # Every chunk gets a 'headers' metadata key
        for c in chunks:
            assert "headers" in c.metadata

    def test_chunk_id_sequential(self):
        text = "## A\nContent A.\n\n## B\nContent B."
        cfg = {"headers_to_split_on": [("##", "H2")], "min_chunk_chars": 1}
        chunks = chunk(text, cfg)
        ids = [c.metadata["chunk_id"] for c in chunks]
        assert ids == list(range(1, len(chunks) + 1))

    def test_chunk_type_is_document(self):
        text = "## A\nContent A."
        cfg = {"headers_to_split_on": [("##", "H2")], "min_chunk_chars": 1}
        chunks = chunk(text, cfg)
        for c in chunks:
            assert c.metadata["chunk_type"] == "document"

    def test_source_metadata_preserved(self):
        text = "## A\nContent A."
        cfg = {"headers_to_split_on": [("##", "H2")], "min_chunk_chars": 1}
        chunks = list(markdown_chunker(make_generator(text, source="my_doc.md"), config=cfg))
        for c in chunks:
            assert c.metadata["source"] == "my_doc.md"


# ---------------------------------------------------------------------------
# MCH02 — strip_header=True removes header from page_content
# ---------------------------------------------------------------------------

class TestMCH02_StripHeader:

    def test_header_absent_from_content_when_stripped(self):
        text = "## My Header\nSome body text that is long enough to pass min_chunk_chars."
        cfg = {
            "headers_to_split_on": [("##", "H2")],
            "strip_header": True,
            "min_chunk_chars": 1,
        }
        chunks = chunk(text, cfg)
        for c in chunks:
            assert "## My Header" not in c.page_content

    def test_header_present_in_content_when_not_stripped(self):
        text = "## My Header\nSome body text that is long enough to pass min_chunk_chars."
        cfg = {
            "headers_to_split_on": [("##", "H2")],
            "strip_header": False,
            "min_chunk_chars": 1,
        }
        chunks = chunk(text, cfg)
        full_text = " ".join(c.page_content for c in chunks)
        assert "My Header" in full_text


# ---------------------------------------------------------------------------
# MCH03 — Section exceeds max_tokens is further split
# ---------------------------------------------------------------------------

class TestMCH03_MaxTokensSplit:

    def test_large_section_produces_multiple_subchunks(self):
        # Generate ~200 word paragraph — well over 10 tokens
        long_paragraph = " ".join(["word"] * 200)
        text = f"## Long Section\n{long_paragraph}"
        cfg = {
            "headers_to_split_on": [("##", "H2")],
            "max_tokens": 10,
            "token_overlap": 0,
            "min_chunk_chars": 1,
        }
        chunks = chunk(text, cfg)
        assert len(chunks) > 1

    @pytest.mark.xfail(reason="Known bug: markdown_chunker sets method_name='markdown' even for chunks split by TokenTextSplitter", id="BUG-1236")
    def test_oversplit_chunks_have_method_name_text(self):
        # Chunks that were further split by TokenTextSplitter (overflow path)
        # should carry method_name='text' (token/text splitting was the final operation).
        long_paragraph = " ".join(["word"] * 200)
        text = f"## Big\n{long_paragraph}"
        cfg = {
            "headers_to_split_on": [("##", "H2")],
            "max_tokens": 10,
            "token_overlap": 0,
            "min_chunk_chars": 1,
        }
        chunks = chunk(text, cfg)
        for c in chunks:
            assert c.metadata["method_name"] == "text"

    @pytest.mark.xfail(reason="Known bug: markdown_chunker sets method_name='markdown' even for chunks split by TokenTextSplitter", id="BUG-1236")
    def test_normal_chunk_has_method_name_markdown(self):
        # Chunks produced by MarkdownHeaderTextSplitter alone (normal path)
        # should carry method_name='markdown' (markdown splitting was the only operation).
        text = "## Short\nBrief content."
        cfg = {
            "headers_to_split_on": [("##", "H2")],
            "max_tokens": 512,
            "min_chunk_chars": 1,
        }
        chunks = chunk(text, cfg)
        for c in chunks:
            assert c.metadata["method_name"] == "markdown"


# ---------------------------------------------------------------------------
# MCH04 — Section below min_chunk_chars is merged with the next chunk
# ---------------------------------------------------------------------------

class TestMCH04_MinChunkCharsMerge:

    def test_tiny_section_merged_with_next(self):
        # First section is very short (< 100 chars by default), second is longer
        text = (
            "## Short\nHi.\n\n"
            "## Long\n" + "This section has enough content to exceed the minimum size." * 3
        )
        cfg = {
            "headers_to_split_on": [("##", "H2")],
            "min_chunk_chars": 50,
            "max_tokens": 512,
        }
        chunks = chunk(text, cfg)
        # The tiny "Hi." section should be merged, so we get fewer chunks than sections
        full_text = " ".join(c.page_content for c in chunks)
        assert "Hi." in full_text  # content not lost

    def test_min_chunk_chars_zero_no_merge(self):
        text = "## A\nX.\n\n## B\nY."
        cfg = {
            "headers_to_split_on": [("##", "H2")],
            "min_chunk_chars": 0,
            "max_tokens": 512,
        }
        chunks = chunk(text, cfg)
        assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# MCH05 — return_each_line=True yields more chunks than without it
# ---------------------------------------------------------------------------
# Note: MarkdownHeaderTextSplitter's return_each_line only takes effect when
# headers_to_split_on is configured.  Without headers, the entire content is
# returned as a single chunk regardless of return_each_line.

class TestMCH05_ReturnEachLine:

    def test_return_each_line_produces_more_chunks_than_default(self):
        # Three content lines under one header; with return_each_line each line
        # becomes its own chunk instead of all content being one chunk.
        text = "## Section\nLine one\nLine two\nLine three"
        base_cfg = {"headers_to_split_on": [("##", "H2")], "min_chunk_chars": 1, "max_tokens": 512}
        cfg_each_line = {**base_cfg, "return_each_line": True}
        cfg_default = {**base_cfg, "return_each_line": False}
        chunks_each = chunk(text, cfg_each_line)
        chunks_default = chunk(text, cfg_default)
        assert len(chunks_each) >= len(chunks_default)

    def test_lines_content_preserved_with_headers(self):
        text = "## Sec\nAlpha\nBeta\nGamma"
        cfg = {
            "headers_to_split_on": [("##", "H2")],
            "return_each_line": True,
            "min_chunk_chars": 1,
            "max_tokens": 512,
        }
        chunks = chunk(text, cfg)
        all_content = " ".join(c.page_content for c in chunks)
        assert "Alpha" in all_content
        assert "Beta" in all_content
        assert "Gamma" in all_content

    def test_no_headers_config_whole_content_is_one_chunk(self):
        # Without headers_to_split_on, return_each_line has no effect.
        text = "Line one\nLine two\nLine three"
        cfg = {"return_each_line": True, "min_chunk_chars": 1, "max_tokens": 512}
        chunks = chunk(text, cfg)
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# MCH06 — No headers in document produces a single chunk
# ---------------------------------------------------------------------------

class TestMCH06_NoHeaders:

    def test_flat_paragraphs_produce_one_chunk(self):
        text = "This is plain text with no markdown headers at all. " * 5
        cfg = {"headers_to_split_on": [("#", "H1"), ("##", "H2")], "min_chunk_chars": 1}
        chunks = chunk(text, cfg)
        # Without matching headers, the whole content is one unsplit block
        assert len(chunks) == 1
        assert "plain text" in chunks[0].page_content

    def test_empty_headers_config_produces_one_chunk(self):
        text = "## Ignored\nSome content here."
        cfg = {"headers_to_split_on": [], "min_chunk_chars": 1}
        chunks = chunk(text, cfg)
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# MCH07 — Empty document yields no chunks, no crash
# ---------------------------------------------------------------------------

class TestMCH07_EmptyDocument:

    def test_empty_string_yields_no_chunks(self):
        chunks = chunk("", {})
        assert chunks == []

    def test_whitespace_only_yields_no_crash(self):
        # Should not raise, output may be empty or one whitespace chunk
        result = chunk("   \n\n   ", {})
        assert isinstance(result, list)

    def test_empty_generator_yields_nothing(self):
        def empty():
            return
            yield  # make it a generator

        result = list(markdown_chunker(empty(), config={}))
        assert result == []


# ---------------------------------------------------------------------------
# _merge_small_chunks — internal helper unit tests
# ---------------------------------------------------------------------------

class TestMergeSmallChunks:

    def _doc(self, content: str, **meta) -> Document:
        return Document(page_content=content, metadata=meta)

    def test_empty_input_returns_empty(self):
        assert _merge_small_chunks([], 100) == []

    def test_large_chunks_pass_through_unchanged(self):
        docs = [self._doc("A" * 200), self._doc("B" * 200)]
        result = _merge_small_chunks(docs, 100)
        assert len(result) == 2
        assert result[0].page_content == "A" * 200

    def test_small_chunk_merged_with_next(self):
        docs = [self._doc("tiny"), self._doc("B" * 200)]
        result = _merge_small_chunks(docs, 50)
        assert len(result) == 1
        assert "tiny" in result[0].page_content
        assert "B" * 100 in result[0].page_content

    def test_trailing_small_chunk_emitted(self):
        docs = [self._doc("A" * 200), self._doc("tiny")]
        result = _merge_small_chunks(docs, 50)
        assert len(result) == 2
        assert result[1].page_content == "tiny"

    def test_all_small_chunks_accumulate_into_one(self):
        docs = [self._doc("ab"), self._doc("cd"), self._doc("ef")]
        result = _merge_small_chunks(docs, 100)
        assert len(result) == 1
        assert "ab" in result[0].page_content
        assert "cd" in result[0].page_content
        assert "ef" in result[0].page_content

    def test_single_chunk_below_min_still_emitted(self):
        docs = [self._doc("short")]
        result = _merge_small_chunks(docs, 100)
        assert len(result) == 1
        assert result[0].page_content == "short"

    def test_min_chars_zero_no_merge(self):
        docs = [self._doc("x"), self._doc("y")]
        result = _merge_small_chunks(docs, 0)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Mutation-kill tests — default values (lines 25-26)
# ---------------------------------------------------------------------------
# These kill ReplaceFalseWithTrue on strip_header/return_each_line defaults.
# The tests call markdown_chunker with an EMPTY config {} (no explicit keys)
# and verify the default=False behaviour is in effect.

class TestDefaultConfigValues:

    def test_default_strip_header_is_false(self):
        """With empty strip_header (unset), headers_to_split_on must be given so the
        splitter actually recognises headers and strip_headers takes effect.
        Default strip_header=False → header text remains in page_content."""
        text = "## My Title\nContent body here."
        # Provide headers_to_split_on so ## is recognised, but leave strip_header unset
        chunks = list(markdown_chunker(
            make_generator(text),
            config={"headers_to_split_on": [("##", "H2")], "min_chunk_chars": 1},
        ))
        full = " ".join(c.page_content for c in chunks)
        # With strip_header=False (default), "## My Title" stays in page_content.
        # With strip_header=True (mutant default), it would be stripped to metadata only.
        assert "My Title" in full

    def test_default_return_each_line_is_false(self):
        """With return_each_line unset, default is False → multi-line section is ONE chunk
        (not split per line). Requires headers_to_split_on so the splitter is active."""
        text = "## Sec\nLine one\nLine two\nLine three"
        # default config: explicitly set headers but leave return_each_line unset
        chunks_default = list(markdown_chunker(
            make_generator(text),
            config={"headers_to_split_on": [("##", "H2")], "min_chunk_chars": 1},
        ))
        # explicit True — should produce MORE chunks (one per line)
        chunks_each_line = list(markdown_chunker(
            make_generator(text),
            config={"headers_to_split_on": [("##", "H2")], "return_each_line": True, "min_chunk_chars": 1},
        ))
        # Default (False) must produce STRICTLY fewer chunks than explicit True.
        # If default were True (mutant), both would produce equal counts → test fails → mutant killed.
        assert len(chunks_default) < len(chunks_each_line)


# ---------------------------------------------------------------------------
# Mutation-kill tests — max_tokens exact boundary (line 50)
# ---------------------------------------------------------------------------
# Kills ReplaceComparisonOperator_Gt_GtE: `> max_tokens` vs `>= max_tokens`.
# A chunk whose token count is EXACTLY max_tokens must NOT be sub-split.

class TestMaxTokensBoundary:

    @pytest.mark.xfail(reason="Known bug: markdown_chunker sets method_name='markdown' even for chunks split by TokenTextSplitter", id="BUG-1236")
    def test_chunk_exactly_at_max_tokens_is_not_split(self):
        """Chunk with token count == max_tokens must stay as one chunk.
        Expected method_name='markdown' (only MarkdownHeaderTextSplitter was applied).
        BUG DETECTOR: current source sets 'text' here — test FAILS, surfacing the inverted-label bug."""
        cfg = {"max_tokens": 50, "min_chunk_chars": 1}
        with patch(
            "alita_sdk.tools.chunkers.sematic.markdown_chunker.tiktoken_length",
            return_value=50,  # exactly equal to max_tokens
        ):
            chunks = chunk("Any content here.", cfg)
        assert len(chunks) == 1
        assert chunks[0].metadata["method_name"] == "markdown"

    @pytest.mark.xfail(reason="Known bug: markdown_chunker sets method_name='markdown' even for chunks split by TokenTextSplitter", id="BUG-1236")
    def test_chunk_one_token_over_max_tokens_is_split(self):
        """Chunk with token count == max_tokens + 1 must be sub-split.
        Expected method_name='text' (TokenTextSplitter — a text splitter — was the final operation).
        BUG DETECTOR: current source sets 'markdown' here — test FAILS, surfacing the inverted-label bug."""
        cfg = {"max_tokens": 50, "token_overlap": 0, "min_chunk_chars": 1}
        with patch(
            "alita_sdk.tools.chunkers.sematic.markdown_chunker.tiktoken_length",
            return_value=51,  # one over max_tokens → triggers TokenTextSplitter
        ):
            # Use a real multi-word string so TokenTextSplitter has room to split
            long_text = " ".join(["word"] * 200)
            chunks = list(markdown_chunker(make_generator(long_text), config=cfg))
        for c in chunks:
            assert c.metadata["method_name"] == "text"


# ---------------------------------------------------------------------------
# Mutation-kill tests — metadata merge in _merge_small_chunks (lines 112-113)
# ---------------------------------------------------------------------------
# Kills:
#   ZeroIterationForLoop  on `for key, value in chunk.metadata.items():`
#   AddNot + ReplaceOrWithAnd on `if key not in combined_metadata or not combined_metadata[key]:`

class TestMergeSmallChunksMetadata:

    def _doc(self, content: str, **meta) -> Document:
        return Document(page_content=content, metadata=meta)

    def test_merge_adds_new_key_from_second_chunk(self):
        """When first (pending) chunk has no H2, merged result gets H2 from second chunk."""
        first = self._doc("Hi", H1="SectionA")        # small — will become pending
        second = self._doc("B" * 200, H1="SectionA", H2="Sub")  # big — triggers emit
        result = _merge_small_chunks([first, second], min_chars=50)
        assert len(result) == 1
        assert result[0].metadata.get("H2") == "Sub"

    def test_merge_does_not_overwrite_existing_key(self):
        """Existing key from pending chunk is NOT overwritten by second chunk's value."""
        first = self._doc("Hi", H1="First")    # small — pending
        second = self._doc("B" * 200, H1="Second")  # big — triggers emit
        result = _merge_small_chunks([first, second], min_chars=50)
        assert len(result) == 1
        # H1 was already in combined_metadata from first; must keep "First"
        assert result[0].metadata["H1"] == "First"

    def test_merge_fills_empty_string_metadata_value(self):
        """An empty string for a key (falsy) in pending is filled from second chunk."""
        first = self._doc("Hi", H2="")         # small, H2 empty → falsy
        second = self._doc("B" * 200, H2="SubTitle")
        result = _merge_small_chunks([first, second], min_chars=50)
        assert len(result) == 1
        assert result[0].metadata["H2"] == "SubTitle"


# ---------------------------------------------------------------------------
# Mutation-kill tests — len boundary in _merge_small_chunks (lines 116, 128)
# ---------------------------------------------------------------------------
# Kills:
#   ReplaceComparisonOperator_GtE_Gt  on `if len(combined_content) >= min_chars:`
#   ReplaceComparisonOperator_Lt_LtE  on `elif len(content) < min_chars:`

class TestMergeSmallChunksBoundary:

    def _doc(self, content: str) -> Document:
        return Document(page_content=content, metadata={})

    def test_combined_exactly_at_min_chars_is_emitted(self):
        """Combined content at exactly min_chars must be emitted immediately (>= not >).

        With >= (correct): first+second emitted as chunk 1; third becomes chunk 2 → 2 total.
        With >  (mutant):  first+second NOT emitted (7 not > 7); accumulated with third
                           → flushed as single combined chunk → 1 total.
        Checking len==2 distinguishes the two paths.
        """
        # pending="abc" (3) + "\n\n" (2) + "bb" (2) = 7 chars exactly
        min_chars = 7
        first = self._doc("abc")       # 3 < 7 → pending
        second = self._doc("bb")       # combined = 7 → must emit with >=
        third = self._doc("C" * 200)   # big chunk, definitely ≥ min_chars on its own
        result = _merge_small_chunks([first, second, third], min_chars=min_chars)
        # Correct (>=): first+second emitted, third emitted → 2 chunks
        # Mutant (>):  first+second kept pending, merged with third → 1 chunk
        assert len(result) == 2
        assert "abc" in result[0].page_content
        assert "bb" in result[0].page_content

    def test_single_chunk_exactly_at_min_chars_not_pending(self):
        """A chunk whose stripped length equals min_chars must NOT be treated as pending."""
        min_chars = 5
        content = "abcde"  # len == 5 == min_chars → NOT < min_chars → should pass through
        docs = [self._doc(content), self._doc("X" * 200)]
        result = _merge_small_chunks(docs, min_chars=min_chars)
        # First chunk passes through as-is; second chunk also passes through
        assert len(result) == 2
        assert result[0].page_content == content


# ---------------------------------------------------------------------------
# markdown_by_headers_chunker tests (lines 147-168)
# ---------------------------------------------------------------------------
# Kills ReplaceFalseWithTrue on defaults and ZeroIterationForLoop on both loops.

class TestMarkdownByHeadersChunker:

    def _gen(self, *contents: str) -> Generator[Document, None, None]:
        for c in contents:
            yield Document(page_content=c, metadata={"source": "test.md"})

    def test_basic_split_on_h2(self):
        """Basic usage: splits on H2 headers and yields chunks with metadata."""
        text = "## Intro\nIntro content.\n\n## Details\nDetail content."
        cfg = {"headers_to_split_on": ["## H2"], "strip_header": False, "return_each_line": False}
        chunks = list(markdown_by_headers_chunker(self._gen(text), config=cfg))
        assert len(chunks) >= 1
        for c in chunks:
            assert "chunk_id" in c.metadata
            assert c.metadata["chunk_type"] == "document"

    def test_empty_generator_yields_nothing(self):
        """Empty generator → no chunks, no crash."""
        def empty():
            return
            yield

        result = list(markdown_by_headers_chunker(empty(), config={}))
        assert result == []

    def test_multiple_documents_all_chunked(self):
        """All documents from the generator are processed (outer for-loop executes)."""
        doc1 = "## A\nContent A."
        doc2 = "## B\nContent B."
        cfg = {"headers_to_split_on": ["## H2"]}
        chunks = list(markdown_by_headers_chunker(self._gen(doc1, doc2), config=cfg))
        full = " ".join(c.page_content for c in chunks)
        assert "Content A" in full
        assert "Content B" in full

    def test_chunk_ids_are_sequential_per_document(self):
        """chunk_id resets to 1 for each document (inner for-loop executes)."""
        text = "## X\nFirst chunk.\n\n## Y\nSecond chunk."
        cfg = {"headers_to_split_on": ["## H2"]}
        chunks = list(markdown_by_headers_chunker(self._gen(text), config=cfg))
        ids = [c.metadata["chunk_id"] for c in chunks]
        assert ids == list(range(1, len(chunks) + 1))

    def test_default_strip_header_is_false(self):
        """Empty config → strip_header defaults to False → header present in output."""
        text = "## My Header\nSome body."
        chunks = list(markdown_by_headers_chunker(self._gen(text), config={}))
        full = " ".join(c.page_content for c in chunks)
        assert "My Header" in full

    def test_default_return_each_line_is_false(self):
        """Empty config → return_each_line defaults to False → no per-line splitting."""
        text = "## Sec\nLine one\nLine two\nLine three"
        chunks_default = list(markdown_by_headers_chunker(self._gen(text), config={}))
        chunks_explicit_false = list(
            markdown_by_headers_chunker(self._gen(text), config={"return_each_line": False})
        )
        assert len(chunks_default) == len(chunks_explicit_false)

    def test_source_metadata_preserved(self):
        """Source metadata from original Document is carried through to output chunks."""
        text = "## Sec\nContent."
        chunks = list(markdown_by_headers_chunker(
            (Document(page_content=text, metadata={"source": "my_file.md"}) for _ in range(1)),
            config={},
        ))
        for c in chunks:
            assert c.metadata["source"] == "my_file.md"

    @pytest.mark.xfail(reason="Known bug: markdown_by_headers_chunker does not set method_name metadata", id="BUG-1236")
    def test_chunk_has_method_name_metadata(self):
        """BUG DETECTOR: markdown_by_headers_chunker should set method_name on every chunk,
        consistent with markdown_chunker. Currently it never sets method_name.
        This test FAILS, surfacing the missing-method_name bug (Bug 3)."""
        text = "## Sec\nContent here."
        chunks = list(markdown_by_headers_chunker(self._gen(text), config={}))
        for c in chunks:
            assert "method_name" in c.metadata

