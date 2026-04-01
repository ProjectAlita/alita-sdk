"""Shared helpers for content_parser unit tests."""

from pathlib import Path

_TEST_DATA = (
    Path(__file__).resolve().parent.parent
    / "document_loaders"
    / "test_data"
)


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def page_contents(docs: list) -> list:
    return [doc.page_content for doc in docs]
