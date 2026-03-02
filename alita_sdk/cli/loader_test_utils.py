"""Serialization and comparison utilities for document loader tests."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document


# Fields excluded from comparison AND from saved baselines.
# Absolute paths (table_source, source) are machine-specific and must be ignored.
DEFAULT_IGNORE_METADATA = frozenset({"chunk_id", "source", "table_source"})


def serialize_document(
    doc: Document,
    ignore_fields: Optional[frozenset] = None,
) -> Dict[str, Any]:
    """Convert a LangChain Document to a JSON-serialisable dict.

    Fields listed in *ignore_fields* are stripped from metadata so that
    machine-specific values (absolute paths, etc.) never end up in baselines.
    """
    skip = ignore_fields if ignore_fields is not None else frozenset()
    return {
        "page_content": doc.page_content,
        "metadata": {
            k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            for k, v in doc.metadata.items()
            if k not in skip
        },
    }


def serialize_documents(
    docs: List[Document],
    ignore_fields: Optional[frozenset] = None,
) -> str:
    """Serialise a list of Documents to a pretty-printed JSON string."""
    return json.dumps(
        [serialize_document(d, ignore_fields=ignore_fields) for d in docs],
        indent=2,
        ensure_ascii=False,
    )


def deserialize_document(data: Dict[str, Any]) -> Document:
    """Reconstruct a Document from a dict produced by serialize_document."""
    return Document(
        page_content=data["page_content"],
        metadata=data.get("metadata", {}),
    )


def load_expected_documents(json_path) -> List[Document]:
    """Read an expected-output JSON file and return a list of Documents."""
    path = Path(json_path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(data).__name__}")
    return [deserialize_document(item) for item in data]


def save_documents(docs: List[Document], json_path) -> None:
    """Persist a list of Documents to a JSON file, stripping ignored metadata fields."""
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(serialize_documents(docs, ignore_fields=DEFAULT_IGNORE_METADATA))


def normalize_text(text: str) -> str:
    """Collapse all whitespace sequences to a single space and strip ends."""
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class DocumentDiff:
    index: int
    field: str
    actual: Any
    expected: Any

    def __str__(self) -> str:
        lines = [
            f"  [doc #{self.index}] {self.field}:",
            f"    actual  : {repr(self.actual)[:200]}",
            f"    expected: {repr(self.expected)[:200]}",
        ]
        return "\n".join(lines)


@dataclass
class ComparisonResult:
    passed: bool
    actual_count: int
    expected_count: int
    diffs: List[DocumentDiff] = field(default_factory=list)
    error: Optional[str] = None

    def summary(self) -> str:
        if self.error:
            return f"ERROR: {self.error}"
        status = "PASS" if self.passed else "FAIL"
        msg = f"{status}  (actual={self.actual_count} docs, expected={self.expected_count} docs)"
        if self.diffs:
            msg += "\n" + "\n".join(str(d) for d in self.diffs)
        return msg


def compare_documents(
    actual: List[Document],
    expected: List[Document],
    ignore_metadata_fields=None,
    normalize: bool = True,
) -> ComparisonResult:
    """Deep-compare two Document lists."""
    ignore = set(ignore_metadata_fields) if ignore_metadata_fields is not None else DEFAULT_IGNORE_METADATA
    diffs: List[DocumentDiff] = []

    if len(actual) != len(expected):
        return ComparisonResult(
            passed=False,
            actual_count=len(actual),
            expected_count=len(expected),
            diffs=[DocumentDiff(index=-1, field="count", actual=len(actual), expected=len(expected))],
        )

    for i, (a_doc, e_doc) in enumerate(zip(actual, expected)):
        a_content = normalize_text(a_doc.page_content) if normalize else a_doc.page_content
        e_content = normalize_text(e_doc.page_content) if normalize else e_doc.page_content
        if a_content != e_content:
            diffs.append(DocumentDiff(index=i, field="page_content", actual=a_content, expected=e_content))

        a_meta = {k: v for k, v in a_doc.metadata.items() if k not in ignore}
        e_meta = {k: v for k, v in e_doc.metadata.items() if k not in ignore}
        for key in sorted(set(a_meta) | set(e_meta)):
            av = a_meta.get(key)
            ev = e_meta.get(key)
            if str(av) != str(ev):
                diffs.append(DocumentDiff(index=i, field=f"metadata.{key}", actual=av, expected=ev))

    return ComparisonResult(
        passed=len(diffs) == 0,
        actual_count=len(actual),
        expected_count=len(expected),
        diffs=diffs,
    )
