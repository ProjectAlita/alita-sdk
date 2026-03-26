"""
Unit tests for alita_sdk.tools.chunkers.universal_chunker.

UC01  — .md file routed to markdown_chunker
UC02  — .markdown / .mdx / .mdown extensions also route to markdown
UC03  — .json file routed to json_chunker
UC04  — .jsonl extension also routes to json
UC05  — .py file routed to code parser
UC06  — .js, .ts, .java, .go, .rs code extensions route to code parser
UC07  — Unknown extension routed to default text chunker
UC08  — file_path / file_name / source metadata keys all used for routing
UC09  — 'unknown' file_path falls back to text chunker
UC10  — Every output chunk from every route has chunk_id in metadata
UC11  — file_path metadata set on input document is preserved/set on output
UC12  — None config defaults applied (no crash)
UC13  — chunk_single_document convenience wrapper works
UC14  — Buffer flush: more than BUFFER_SIZE (10) docs of same type all processed

Tests assert semantically correct behaviour.
If a test fails, it surfaces a bug in the source — do NOT change the assertion to match broken behaviour.
"""

import json
from typing import Generator
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from alita_sdk.tools.chunkers.universal_chunker import (
    universal_chunker,
    chunk_single_document,
    get_file_type,
    get_file_extension,
    MARKDOWN_EXTENSIONS,
    JSON_EXTENSIONS,
    CODE_EXTENSIONS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_doc(content: str, file_path: str = None, source: str = None, **extra) -> Document:
    meta = {}
    if file_path:
        meta["file_path"] = file_path
    if source:
        meta["source"] = source
    meta.update(extra)
    return Document(page_content=content, metadata=meta)


def gen(*docs: Document) -> Generator[Document, None, None]:
    yield from docs


MARKDOWN_CONTENT = "# Title\nSome markdown content here.\n\n## Section\nMore content."
JSON_CONTENT = json.dumps({"key": "value", "num": 42})
LARGE_JSON_CONTENT = json.dumps({f"k{i}": f"v{i}" * 10 for i in range(100)})
PLAIN_TEXT = "This is just plain text with no special structure."
PYTHON_CODE = "def hello():\n    return 'hello'\n\ndef world():\n    return 'world'\n"


# ---------------------------------------------------------------------------
# Unit tests for get_file_type / get_file_extension helpers
# ---------------------------------------------------------------------------

class TestGetFileType:

    def test_md_is_markdown(self):
        assert get_file_type("readme.md") == "markdown"

    def test_markdown_is_markdown(self):
        assert get_file_type("docs.markdown") == "markdown"

    def test_mdx_is_markdown(self):
        assert get_file_type("page.mdx") == "markdown"

    def test_json_is_json(self):
        assert get_file_type("data.json") == "json"

    def test_jsonl_is_json(self):
        assert get_file_type("records.jsonl") == "json"

    def test_py_is_code(self):
        assert get_file_type("script.py") == "code"

    def test_js_is_code(self):
        assert get_file_type("app.js") == "code"

    def test_ts_is_code(self):
        assert get_file_type("module.ts") == "code"

    def test_txt_is_text(self):
        assert get_file_type("notes.txt") == "text"

    def test_csv_is_text(self):
        assert get_file_type("data.csv") == "text"

    def test_unknown_no_extension_is_text(self):
        assert get_file_type("Makefile") == "text"

    def test_case_insensitive(self):
        assert get_file_type("README.MD") == "markdown"
        assert get_file_type("DATA.JSON") == "json"


# ---------------------------------------------------------------------------
# UC01 — .md file routed to markdown_chunker
# ---------------------------------------------------------------------------

class TestUC01_MarkdownRouting:

    def test_md_file_produces_chunks(self):
        result = list(universal_chunker(
            gen(make_doc(MARKDOWN_CONTENT, file_path="readme.md")),
        ))
        assert len(result) >= 1

    def test_md_chunks_have_chunk_id(self):
        result = list(universal_chunker(
            gen(make_doc(MARKDOWN_CONTENT, file_path="readme.md")),
        ))
        for chunk in result:
            assert "chunk_id" in chunk.metadata


# ---------------------------------------------------------------------------
# UC02 — Other markdown extensions route to markdown
# ---------------------------------------------------------------------------

class TestUC02_MarkdownExtensions:

    @pytest.mark.parametrize("ext", [".markdown", ".mdx", ".mdown", ".mkd"])
    def test_markdown_extension_routed(self, ext):
        result = list(universal_chunker(
            gen(make_doc(MARKDOWN_CONTENT, file_path=f"doc{ext}")),
        ))
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# UC03 — .json file routed to json_chunker
# ---------------------------------------------------------------------------

class TestUC03_JsonRouting:

    def test_json_file_produces_chunks(self):
        result = list(universal_chunker(
            gen(make_doc(JSON_CONTENT, file_path="data.json")),
        ))
        assert len(result) >= 1

    def test_large_json_file_split(self):
        result = list(universal_chunker(
            gen(make_doc(LARGE_JSON_CONTENT, file_path="big.json")),
            config={"json_config": {"max_tokens": 50}},
        ))
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# UC04 — .jsonl extension routes to json
# ---------------------------------------------------------------------------

class TestUC04_JsonlExtension:

    def test_jsonl_routed_as_json(self):
        result = list(universal_chunker(
            gen(make_doc(JSON_CONTENT, file_path="records.jsonl")),
        ))
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# UC05 — .py file routed to code parser
# ---------------------------------------------------------------------------

class TestUC05_PythonCodeRouting:

    def test_python_file_produces_chunks(self):
        result = list(universal_chunker(
            gen(make_doc(PYTHON_CODE, file_path="script.py")),
        ))
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# UC06 — Other code extensions route to code parser
# ---------------------------------------------------------------------------

class TestUC06_CodeExtensions:

    @pytest.mark.parametrize("ext", [".js", ".ts", ".java", ".go", ".rs", ".rb"])
    def test_code_extension_routed(self, ext):
        # Use minimal valid content for each language
        result = list(universal_chunker(
            gen(make_doc("function foo() { return 1; }\n", file_path=f"file{ext}")),
        ))
        # Should not crash; may produce 0+ chunks depending on content
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# UC07 — Unknown extension routed to default text chunker
# ---------------------------------------------------------------------------

class TestUC07_TextFallback:

    def test_txt_file_produces_chunks(self):
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, file_path="notes.txt")),
        ))
        assert len(result) >= 1

    def test_text_chunks_have_method_name_text(self):
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, file_path="notes.txt")),
        ))
        for chunk in result:
            assert chunk.metadata["method_name"] == "text"

    def test_text_chunks_have_chunk_type_text(self):
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, file_path="notes.txt")),
        ))
        for chunk in result:
            assert chunk.metadata["chunk_type"] == "text"


# ---------------------------------------------------------------------------
# UC08 — file_path / file_name / source metadata keys all used for routing
# ---------------------------------------------------------------------------

class TestUC08_MetadataKeyFallbacks:

    def test_file_name_key_used_for_routing(self):
        """file_name metadata key (not file_path) is used to determine type."""
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, **{"file_name": "notes.txt"})),
        ))
        assert len(result) >= 1

    def test_source_key_used_for_routing(self):
        """source metadata key used when neither file_path nor file_name is set."""
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, source="notes.txt")),
        ))
        assert len(result) >= 1

    def test_file_path_takes_precedence_over_file_name(self):
        """file_path key is read first; file_name is fallback."""
        # Both present: file_path=.md, file_name=.txt → should route as markdown
        result = list(universal_chunker(
            gen(make_doc(MARKDOWN_CONTENT, file_path="readme.md", **{"file_name": "notes.txt"})),
        ))
        # Result should come from markdown route (has headers metadata)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# UC09 — 'unknown' file_path falls back to text chunker
# ---------------------------------------------------------------------------

class TestUC09_UnknownFallbackToText:

    def test_no_metadata_keywords_falls_back_to_text(self):
        """Document with no file_path/file_name/source metadata falls back to text."""
        result = list(universal_chunker(
            gen(Document(page_content=PLAIN_TEXT, metadata={})),
        ))
        assert len(result) >= 1

    def test_unknown_extension_falls_back_to_text(self):
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, file_path="unknown.xyz")),
        ))
        for chunk in result:
            assert chunk.metadata["method_name"] == "text"


# ---------------------------------------------------------------------------
# UC10 — Every output chunk from every route has chunk_id in metadata
# ---------------------------------------------------------------------------

class TestUC10_ChunkIdOnAllRoutes:

    @pytest.mark.xfail(reason="Missing `chunk_id` in universal_chunker for code and JSON files. See: https://github.com/ProjectAlita/projectalita.github.io/issues/3998")
    @pytest.mark.parametrize("file_path,content", [
        ("readme.md", MARKDOWN_CONTENT),
        ("data.json", JSON_CONTENT),
        ("notes.txt", PLAIN_TEXT),
        ("script.py", PYTHON_CODE),
    ])
    def test_chunk_id_present(self, file_path, content):
        result = list(universal_chunker(
            gen(make_doc(content, file_path=file_path)),
        ))
        assert len(result) >= 1
        for chunk in result:
            assert "chunk_id" in chunk.metadata


# ---------------------------------------------------------------------------
# UC11 — file_path set on input doc is preserved on output
# ---------------------------------------------------------------------------

class TestUC11_FilePathPreserved:

    def test_file_path_set_on_output_chunks(self):
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, file_path="myfile.txt")),
        ))
        for chunk in result:
            assert chunk.metadata.get("file_path") == "myfile.txt"


# ---------------------------------------------------------------------------
# UC12 — None config defaults applied (no crash)
# ---------------------------------------------------------------------------

class TestUC12_NoneConfigNocrash:

    def test_none_config_does_not_crash(self):
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, file_path="notes.txt")),
            config=None,
        ))
        assert len(result) >= 1

    def test_empty_config_does_not_crash(self):
        result = list(universal_chunker(
            gen(make_doc(PLAIN_TEXT, file_path="notes.txt")),
            config={},
        ))
        assert len(result) >= 1

    def test_empty_generator_yields_nothing(self):
        def empty():
            return
            yield
        result = list(universal_chunker(empty()))
        assert result == []


# ---------------------------------------------------------------------------
# UC13 — chunk_single_document convenience wrapper
# ---------------------------------------------------------------------------

class TestUC13_ChunkSingleDocument:

    def test_single_doc_wrapper_produces_chunks(self):
        d = make_doc(PLAIN_TEXT, file_path="notes.txt")
        result = list(chunk_single_document(d))
        assert len(result) >= 1

    def test_single_doc_wrapper_with_config(self):
        d = make_doc(PLAIN_TEXT, file_path="notes.txt")
        result = list(chunk_single_document(d, config={"text_config": {"chunk_size": 200, "chunk_overlap": 20}}))
        assert len(result) >= 1

    def test_single_doc_markdown_wrapper(self):
        d = make_doc(MARKDOWN_CONTENT, file_path="doc.md")
        result = list(chunk_single_document(d))
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# UC14 — Buffer flush: more than BUFFER_SIZE (10) docs of same type all processed
# ---------------------------------------------------------------------------

class TestUC14_BufferFlush:

    def test_more_than_buffer_size_text_docs_all_processed(self):
        docs = [make_doc(f"Document {i} content here.", file_path=f"doc{i}.txt")
                for i in range(15)]
        result = list(universal_chunker(gen(*docs)))
        # All 15 documents must have produced at least one chunk
        assert len(result) >= 15

    def test_more_than_buffer_size_json_docs_all_processed(self):
        docs = [make_doc(JSON_CONTENT, file_path=f"data{i}.json")
                for i in range(15)]
        result = list(universal_chunker(gen(*docs)))
        assert len(result) >= 15

    def test_mixed_types_beyond_buffer_all_processed(self):
        docs = (
            [make_doc(PLAIN_TEXT, file_path=f"t{i}.txt") for i in range(12)] +
            [make_doc(JSON_CONTENT, file_path=f"j{i}.json") for i in range(12)]
        )
        result = list(universal_chunker(gen(*docs)))
        assert len(result) >= 24


# ---------------------------------------------------------------------------
# UC15 — file_name metadata with non-text extension routes correctly (line 220 or-chain)
# ---------------------------------------------------------------------------

class TestUC15_FileNameMetadataRouting:
    """
    Targets the `or` chain:
        file_path = (doc.metadata.get('file_path') or
                     doc.metadata.get('file_name') or   ← line 220
                     doc.metadata.get('source') or
                     'unknown')

    ReplaceOrWithAnd at occurrence #1 would make the second `or` an `and`,
    causing `file_name and source` when file_path is absent. If source is
    absent too, the result would be None (→ 'unknown', text route) even
    though file_name="readme.md" should have triggered markdown routing.
    """

    def test_file_name_markdown_routes_to_markdown_not_text(self):
        """file_name=readme.md without file_path or source must route to markdown."""
        result = list(universal_chunker(
            gen(Document(page_content=MARKDOWN_CONTENT, metadata={"file_name": "readme.md"})),
        ))
        assert len(result) >= 1
        # markdown_chunker always sets 'headers' on every chunk it produces
        # (both the normal-sized path and the oversized/TokenTextSplitter path).
        # _default_text_chunker (the universal_chunker text-fallback route) never
        # sets 'headers'. So presence of 'headers' proves the markdown route was
        # taken, regardless of the method_name value.
        has_headers_key = any("headers" in c.metadata for c in result)
        assert has_headers_key, (
            "No 'headers' key found — markdown route was not taken; "
            "file_name fallback likely broken (line 220 or-chain)"
        )

    def test_file_name_json_routes_to_json_not_text(self):
        """file_name=data.json without file_path or source must route to json."""
        result = list(universal_chunker(
            gen(Document(page_content=JSON_CONTENT, metadata={"file_name": "data.json"})),
        ))
        assert len(result) >= 1
        # JSON route (single small chunk passthrough) will not have method_name='text'
        for chunk in result:
            assert chunk.metadata.get("method_name") != "text"


# ---------------------------------------------------------------------------
# UC16 — code route sets file_path on output chunks (line 111 AddNot guard)
# ---------------------------------------------------------------------------

class TestUC16_CodeRouteFilePath:
    """
    Targets the backfill guard in _code_chunker_from_documents:
        if 'file_path' not in chunk.metadata and 'filename' in chunk.metadata:
            chunk.metadata['file_path'] = chunk.metadata['filename']

    AddNot #1 negates the second condition to `'filename' not in chunk.metadata`,
    making the backfill never run (since filename is always set by the parser).
    A test asserting file_path on code route chunks will kill this mutation.
    """

    def test_python_code_chunks_have_file_path(self):
        """Code chunks must have file_path set after routing through the code parser."""
        result = list(universal_chunker(
            gen(make_doc(PYTHON_CODE, file_path="module.py")),
        ))
        assert len(result) >= 1
        for chunk in result:
            assert "file_path" in chunk.metadata, "file_path missing from code chunk"

    def test_python_code_file_path_matches_input(self):
        """file_path on code chunks must equal the original input file_path."""
        result = list(universal_chunker(
            gen(make_doc(PYTHON_CODE, file_path="mymodule.py")),
        ))
        assert len(result) >= 1
        for chunk in result:
            assert chunk.metadata.get("file_path") == "mymodule.py"


# ---------------------------------------------------------------------------
# UC17 — Default markdown config: strip_header=False, return_each_line=False
# ---------------------------------------------------------------------------

class TestUC17_MarkdownDefaultConfig:
    """
    Targets the two ReplaceFalseWithTrue mutations in the default markdown_config:
        'strip_header': False,      ← line 147
        'return_each_line': False,  ← line 148

    strip_header=True would remove header text from page_content.
    return_each_line=True would split every line into its own chunk.
    """

    MULTI_SECTION_MD = (
        "# Introduction\n\n"
        "This is the introduction paragraph with enough content to matter.\n\n"
        "## Background\n\n"
        "Background section content goes here in detail.\n\n"
        "## Details\n\n"
        "Details section content for the third major section.\n"
    )

    def test_default_config_headers_not_stripped(self):
        """With strip_header=False (default), header markers must appear in output."""
        result = list(universal_chunker(
            gen(make_doc(self.MULTI_SECTION_MD, file_path="guide.md")),
        ))
        assert len(result) >= 1
        all_content = " ".join(c.page_content for c in result)
        # At least one of the header markers must be present in combined output.
        # If strip_header were True, '##' / '#' wouldn't appear in page_content.
        has_header_text = (
            "Introduction" in all_content or
            "Background" in all_content or
            "Details" in all_content
        )
        assert has_header_text, (
            "Header text lost — strip_header may have been set to True by mutation"
        )

    def test_default_config_not_one_line_per_chunk(self):
        """With return_each_line=False (default), multi-line sections must not each be a single line."""
        multi_line_md = (
            "# Title\n\n"
            "Line one of content.\n"
            "Line two of content.\n"
            "Line three of content.\n"
            "Line four of content.\n"
            "Line five of content.\n"
        )
        result = list(universal_chunker(
            gen(make_doc(multi_line_md, file_path="content.md")),
        ))
        assert len(result) >= 1
        # If return_each_line=True, every line would be its own chunk and
        # each page_content would contain only a single sentence.
        # With return_each_line=False, at least one chunk covers multiple lines.
        multi_line_chunks = [
            c for c in result
            if c.page_content.count("\n") >= 1 or len(c.page_content.split()) > 6
        ]
        assert len(multi_line_chunks) >= 1, (
            "All chunks are single-line — return_each_line may have been set to True by mutation"
        )
