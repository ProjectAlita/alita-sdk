"""Serialization and comparison utilities for document loader tests."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document


# Map loader types to fields requiring special comparison logic
LOADER_SPECIAL_FIELDS = {
    "AlitaTextLoader": {
        "source": "path_suffix",  # actual must end with expected (OS-agnostic)
    },
    "AlitaMarkdownLoader": {
        "source": "path_suffix",
    },
    "AlitaCSVLoader": {
        "source": "path_suffix",
        "table_source": "path_suffix",
    },
    "AlitaExcelLoader": {
        "source": "path_suffix",
        "table_source": "path_suffix",
    },
    "AlitaJSONLoader": {
        "source": "path_suffix",
    },
    "AlitaJSONLinesLoader": {
        "source": "path_suffix",
    },
    "AlitaYamlLoader": {
        "source": "path_suffix",
    },
    "AlitaXMLLoader": {
        "source": "path_suffix",
    },
    "AlitaHTMLLoader": {
        "source": "path_suffix",
    },
}

# Default: compare all fields (no ignoring)
DEFAULT_IGNORE_METADATA = frozenset()


def _normalize_path(path: str) -> str:
    """Normalize path separators for cross-platform comparison."""
    if not isinstance(path, str):
        return path
    # Convert backslashes to forward slashes and collapse multiple slashes
    normalized = path.replace('\\', '/').replace('//', '/')
    # Remove trailing slash
    return normalized.rstrip('/')


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
            k: v if isinstance(v, (str, int, float, bool, type(None), list, dict)) else str(v)
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
    diff_type: str = "value"  # value | missing_key | extra_key | type_mismatch

    def __str__(self) -> str:
        tag = {
            "missing_key":   "MISSING KEY   ",
            "extra_key":     "EXTRA KEY     ",
            "type_mismatch": "TYPE MISMATCH ",
            "value":         "",
        }.get(self.diff_type, "")
        lines = [
            f"  [doc #{self.index}] {tag}{self.field}:",
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


def _compare_metadata(
    actual_meta: Dict[str, Any],
    expected_meta: Dict[str, Any],
    doc_index: int,
    ignore: set,
    loader_name: Optional[str] = None,
) -> List[DocumentDiff]:
    """Compare metadata dicts checking schema structure (keys + types) and values."""
    diffs: List[DocumentDiff] = []
    a = {k: v for k, v in actual_meta.items() if k not in ignore}
    e = {k: v for k, v in expected_meta.items() if k not in ignore}
    
    # Get special field rules for this loader
    special_fields = LOADER_SPECIAL_FIELDS.get(loader_name, {}) if loader_name else {}

    # Keys in baseline but absent in actual output → missing field
    for key in sorted(e):
        if key not in a:
            diffs.append(DocumentDiff(
                index=doc_index, field=f"metadata.{key}",
                actual="<missing>", expected=e[key],
                diff_type="missing_key",
            ))

    # Keys in actual output but absent in baseline → unexpected field
    for key in sorted(a):
        if key not in e:
            diffs.append(DocumentDiff(
                index=doc_index, field=f"metadata.{key}",
                actual=a[key], expected="<not present>",
                diff_type="extra_key",
            ))

    # Keys present in both → check type then value
    for key in sorted(set(a) & set(e)):
        av, ev = a[key], e[key]
        
        # Type check first
        if type(av) is not type(ev):
            diffs.append(DocumentDiff(
                index=doc_index, field=f"metadata.{key}",
                actual=f"{av!r} (type={type(av).__name__})",
                expected=f"{ev!r} (type={type(ev).__name__})",
                diff_type="type_mismatch",
            ))
            continue
        
        # Value comparison with special rules for this loader
        comparison_type = special_fields.get(key)
        
        if comparison_type == "path_suffix":
            # For path fields: actual should end with expected (normalized)
            if isinstance(av, str) and isinstance(ev, str):
                actual_normalized = _normalize_path(av)
                expected_normalized = _normalize_path(ev)
                if not actual_normalized.endswith(expected_normalized):
                    diffs.append(DocumentDiff(
                        index=doc_index, field=f"metadata.{key}",
                        actual=f"{av} (normalized: ...{actual_normalized[-50:]})",
                        expected=f"{ev} (should end with: {expected_normalized})",
                        diff_type="value",
                    ))
            else:
                # Not strings, compare normally
                if av != ev:
                    diffs.append(DocumentDiff(
                        index=doc_index, field=f"metadata.{key}",
                        actual=av, expected=ev,
                        diff_type="value",
                    ))
        else:
            # Default comparison
            if av != ev:
                diffs.append(DocumentDiff(
                    index=doc_index, field=f"metadata.{key}",
                    actual=av, expected=ev,
                    diff_type="value",
                ))

    return diffs


def compare_documents(
    actual: List[Document],
    expected: List[Document],
    ignore_metadata_fields=None,
    normalize: bool = True,
    loader_name: Optional[str] = None,
) -> ComparisonResult:
    """Deep-compare two Document lists: count, page_content, and metadata schema+values.
    
    Args:
        actual: Documents produced by the loader
        expected: Documents from baseline
        ignore_metadata_fields: Fields to exclude from comparison (deprecated, use loader-specific rules)
        normalize: Whether to normalize whitespace in page_content
        loader_name: Loader class name (e.g., "AlitaTextLoader") for loader-specific comparison rules
    """
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
        # page_content
        a_content = normalize_text(a_doc.page_content) if normalize else a_doc.page_content
        e_content = normalize_text(e_doc.page_content) if normalize else e_doc.page_content
        if a_content != e_content:
            diffs.append(DocumentDiff(
                index=i, field="page_content",
                actual=a_content, expected=e_content,
                diff_type="value",
            ))

        # metadata structure + values
        diffs.extend(_compare_metadata(a_doc.metadata, e_doc.metadata, i, ignore, loader_name))

    return ComparisonResult(
        passed=len(diffs) == 0,
        actual_count=len(actual),
        expected_count=len(expected),
        diffs=diffs,
    )
