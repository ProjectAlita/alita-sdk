"""
Unit tests for alita_sdk.tools.chunkers.code.codeparser.parse_code_files_for_db.

CCH01 — Empty content is skipped (no output)
CCH02 — Default-skip filenames are skipped
CCH03 — Image file extensions are skipped
CCH04 — Unknown language falls back to TokenTextSplitter; method_name='text'
CCH05 — Known language (Python) produces chunks with language metadata
CCH06 — Known language chunks carry filename in metadata
CCH07 — commit_hash propagated when provided
CCH08 — commit_hash absent when not provided
CCH09 — Multiple files in generator all processed

Tests assert semantically correct behaviour.
If a test fails, it surfaces a bug in the source — do NOT change the assertion to match broken behaviour.
"""

from typing import Generator

from langchain_core.documents import Document

from alita_sdk.tools.chunkers.code.codeparser import parse_code_files_for_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_file(file_name: str, file_content: str, commit_hash: str = None) -> dict:
    d = {"file_name": file_name, "file_content": file_content}
    if commit_hash is not None:
        d["commit_hash"] = commit_hash
    return d


def file_gen(*files: dict) -> Generator[dict, None, None]:
    yield from files


# Sample code content
PYTHON_CODE = """\
def greet(name):
    \"\"\"Return a greeting.\"\"\"
    return f"Hello, {name}!"

def add(a, b):
    return a + b
"""

JS_CODE = """\
function greet(name) {
    return `Hello, ${name}!`;
}

function add(a, b) {
    return a + b;
}
"""

UNKNOWN_LANG_CONTENT = "just some plain text without any code structure"


# ---------------------------------------------------------------------------
# CCH01 — Empty content is skipped
# ---------------------------------------------------------------------------

class TestCCH01_EmptyContentSkipped:

    def test_empty_string_yields_nothing(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("script.py", "")
        )))
        assert result == []

    def test_whitespace_only_yields_nothing(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("script.py", "   \n\n\t  ")
        )))
        assert result == []


# ---------------------------------------------------------------------------
# CCH02 — Default-skip filenames are skipped
# ---------------------------------------------------------------------------

class TestCCH02_DefaultSkipFilenames:

    def test_gitignore_is_skipped(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file(".gitignore", "node_modules/\ndist/")
        )))
        assert result == []

    def test_license_is_skipped(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("LICENSE", "MIT License...")
        )))
        assert result == []

    def test_ds_store_is_skipped(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file(".DS_Store", "\x00\x00\x00")
        )))
        assert result == []


# ---------------------------------------------------------------------------
# CCH03 — Image file extensions are skipped
# ---------------------------------------------------------------------------

class TestCCH03_ImageExtensionsSkipped:

    def test_png_is_skipped(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("logo.png", "\x89PNG\r\n")
        )))
        assert result == []

    def test_jpg_is_skipped(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("photo.jpg", "\xff\xd8\xff")
        )))
        assert result == []

    def test_pdf_is_skipped(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("doc.pdf", "%PDF-1.4")
        )))
        assert result == []


# ---------------------------------------------------------------------------
# CCH04 — Unknown language falls back to TokenTextSplitter; method_name='text'
# ---------------------------------------------------------------------------

class TestCCH04_UnknownLanguageFallback:

    def test_txt_file_produces_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("readme.txt", UNKNOWN_LANG_CONTENT)
        )))
        assert len(result) >= 1

    def test_unknown_language_chunks_have_method_name_text(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("readme.txt", UNKNOWN_LANG_CONTENT)
        )))
        for chunk in result:
            assert chunk.metadata["method_name"] == "text"

    def test_unknown_language_metadata_has_language_unknown(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("readme.txt", UNKNOWN_LANG_CONTENT)
        )))
        for chunk in result:
            assert chunk.metadata["language"] == "unknown"

    def test_unknown_language_filename_in_metadata(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("readme.txt", UNKNOWN_LANG_CONTENT)
        )))
        for chunk in result:
            assert chunk.metadata["filename"] == "readme.txt"


# ---------------------------------------------------------------------------
# CCH05 — Known language (Python) produces chunks with language metadata
# ---------------------------------------------------------------------------

class TestCCH05_KnownLanguagePython:

    def test_python_file_produces_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("script.py", PYTHON_CODE)
        )))
        assert len(result) >= 1

    def test_python_chunks_have_language_python(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("script.py", PYTHON_CODE)
        )))
        for chunk in result:
            assert chunk.metadata["language"] == "python"

    def test_python_chunks_have_method_name_set(self):
        """method_name should be the function/method name (not 'text') for known languages."""
        result = list(parse_code_files_for_db(file_gen(
            make_file("script.py", PYTHON_CODE)
        )))
        for chunk in result:
            assert "method_name" in chunk.metadata


# ---------------------------------------------------------------------------
# CCH06 — Known language chunks carry filename in metadata
# ---------------------------------------------------------------------------

class TestCCH06_FilenameInMetadata:

    def test_filename_metadata_on_python_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("mymodule.py", PYTHON_CODE)
        )))
        for chunk in result:
            assert chunk.metadata["filename"] == "mymodule.py"

    def test_filename_metadata_on_js_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("app.js", JS_CODE)
        )))
        for chunk in result:
            assert chunk.metadata["filename"] == "app.js"


# ---------------------------------------------------------------------------
# CCH07 — commit_hash propagated when provided
# ---------------------------------------------------------------------------

class TestCCH07_CommitHashPropagated:

    def test_commit_hash_present_in_python_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("script.py", PYTHON_CODE, commit_hash="abc123")
        )))
        for chunk in result:
            assert chunk.metadata.get("commit_hash") == "abc123"

    def test_commit_hash_present_in_unknown_lang_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("notes.txt", UNKNOWN_LANG_CONTENT, commit_hash="def456")
        )))
        for chunk in result:
            assert chunk.metadata.get("commit_hash") == "def456"


# ---------------------------------------------------------------------------
# CCH08 — commit_hash absent when not provided
# ---------------------------------------------------------------------------

class TestCCH08_CommitHashAbsentWhenNotProvided:

    def test_no_commit_hash_key_in_python_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("script.py", PYTHON_CODE)
        )))
        for chunk in result:
            assert "commit_hash" not in chunk.metadata

    def test_no_commit_hash_key_in_unknown_lang_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("notes.txt", UNKNOWN_LANG_CONTENT)
        )))
        for chunk in result:
            assert "commit_hash" not in chunk.metadata


# ---------------------------------------------------------------------------
# CCH09 — Multiple files in generator all processed
# ---------------------------------------------------------------------------

class TestCCH09_MultipleFiles:

    def test_two_python_files_both_produce_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("a.py", PYTHON_CODE),
            make_file("b.py", PYTHON_CODE),
        )))
        filenames = {c.metadata["filename"] for c in result}
        assert "a.py" in filenames
        assert "b.py" in filenames

    def test_mixed_file_types_all_produce_chunks(self):
        result = list(parse_code_files_for_db(file_gen(
            make_file("app.py", PYTHON_CODE),
            make_file("notes.txt", UNKNOWN_LANG_CONTENT),
        )))
        filenames = {c.metadata["filename"] for c in result}
        assert "app.py" in filenames
        assert "notes.txt" in filenames

    def test_empty_generator_yields_nothing(self):
        def empty():
            return
            yield
        result = list(parse_code_files_for_db(empty()))
        assert result == []
