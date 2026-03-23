"""Serialization and comparison utilities for document loader tests."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


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
    "AlitaImageLoader": {
        "source": "path_suffix",
        "similarity_threshold": 0.6,  # Lower threshold for LLM-based outputs (non-deterministic)
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


def _calculate_tfidf_similarity(text1: str, text2: str) -> Optional[float]:
    """Calculate TF-IDF + cosine similarity between two texts.
    
    Returns:
        Similarity score (0.0-1.0) or None if sklearn unavailable
    """
    if not SKLEARN_AVAILABLE:
        return None
    
    try:
        vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(similarity)
    except Exception:
        return None


def _calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between two texts (fallback method).
    
    Returns:
        Similarity score (0.0-1.0)
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts using TF-IDF or Jaccard fallback.
    
    Returns:
        Similarity score (0.0-1.0)
    """
    # Try TF-IDF first
    similarity = _calculate_tfidf_similarity(text1, text2)
    if similarity is not None:
        return similarity
    
    # Fallback to Jaccard
    return _calculate_jaccard_similarity(text1, text2)


@dataclass
class DocumentDiff:
    index: int
    field: str
    actual: Any
    expected: Any
    diff_type: str = "value"  # value | missing_key | extra_key | type_mismatch | similarity | llm_validation
    similarity: Optional[float] = None  # For page_content similarity comparison
    explanation: Optional[str] = None  # For LLM validation explanation

    def __str__(self) -> str:
        tag = {
            "missing_key":   "MISSING KEY   ",
            "extra_key":     "EXTRA KEY     ",
            "type_mismatch": "TYPE MISMATCH ",
            "similarity":    "",
            "llm_validation": "LLM VALIDATION FAILED ",
            "value":         "",
        }.get(self.diff_type, "")
        
        # Special handling for similarity matrix (multi-line formatted output)
        if self.field == "similarity_matrix":
            return f"  {self.actual}"
        
        # Special handling for extra/missing documents (multi-line formatted output)
        if self.field in ("extra_documents", "missing_documents"):
            content = self.actual if self.actual else self.expected
            return f"  {content}"
        
        # Smart comparison for LLM validation failures
        if self.field == "page_content" and self.diff_type == "llm_validation":
            actual_len = len(self.actual) if isinstance(self.actual, str) else 0
            expected_len = len(self.expected) if isinstance(self.expected, str) else 0
            similarity_str = str(self.similarity) if self.similarity is not None else "N/A"
            
            lines = [
                f"  [doc #{self.index}] {tag}{self.field}:",
                f"    LLM determined content is not semantically equivalent",
            ]
            if self.explanation:
                lines.append(f"    LLM explanation: {self.explanation}")
            lines.extend([
                f"    (similarity score: {similarity_str})",
                f"    actual length  : {actual_len} chars",
                f"    expected length: {expected_len} chars",
            ])
            return "\n".join(lines)
        
        # Smart comparison for page_content fields (always show similarity and lengths)
        if self.field == "page_content" and self.diff_type == "similarity":
            actual_len = len(self.actual) if isinstance(self.actual, str) else 0
            expected_len = len(self.expected) if isinstance(self.expected, str) else 0
            similarity_str = str(self.similarity) if self.similarity is not None else "N/A"
            
            lines = [
                f"  [doc #{self.index}] {tag}{self.field}:",
                f"    Actual not match expected (similarity: {similarity_str})",
                f"    actual length  : {actual_len} chars",
                f"    expected length: {expected_len} chars",
            ]
            return "\n".join(lines)
        
        # Default: show truncated repr
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


def _llm_validate_content_old_method(
    actual_content: str,
    expected_content: str,
    llm,
) -> tuple[bool, str]:
    """Old validation method using direct LLM text response parsing.
    
    This is kept for comparison purposes during the transition period.
    
    Args:
        actual_content: Actual page_content to validate
        expected_content: Expected page_content (baseline)
        llm: LangChain LLM instance for validation
        
    Returns:
        Tuple of (is_valid: bool, explanation: str)
    """
    prompt = f"""You are a test validation assistant. Compare the following two text outputs and determine if they are semantically equivalent.

The EXPECTED output is the baseline/reference output.
The ACTUAL output is the current test output.

Your task:
1. Determine if ACTUAL and EXPECTED convey the same information and meaning
2. Minor differences in wording, formatting, or style are acceptable
3. Focus on semantic equivalence, not exact text matching
4. Respond with ONLY 'VALID' or 'INVALID' on the first line
5. On the second line, provide a brief explanation (max 100 words)

EXPECTED OUTPUT:
{expected_content}

ACTUAL OUTPUT:
{actual_content}

Validation result:"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        result_text = response.content.strip()
        
        # Parse response - first line should be VALID/INVALID
        lines = result_text.split('\n', 1)
        verdict = lines[0].strip().upper()
        explanation = lines[1].strip() if len(lines) > 1 else "No explanation provided"
        
        is_valid = verdict == "VALID"
        return is_valid, explanation
    except Exception as e:
        # If LLM validation fails, return False and error info
        return False, f"LLM validation failed: {str(e)}"


def _log_llm_validation_comparison(
    actual_content: str,
    expected_content: str,
    old_result: tuple[bool, str],
    new_result: tuple[bool, str, float, dict],
    text_similarity: float,
    log_file_path: str,
    prompt_text: str = None,
):
    """Log both validation methods' results to a debug file for comparison.
    
    Args:
        actual_content: Actual content being validated
        expected_content: Expected content
        old_result: Result from old text-based validation (is_valid, explanation)
        new_result: Result from new JSON-based validation (is_valid, explanation, confidence, full_dict)
        text_similarity: Traditional TF-IDF similarity score
        log_file_path: Path to debug log file
        prompt_text: The prompt template sent to LLM for validation
    """
    import json
    from datetime import datetime
    from pathlib import Path
    
    # Ensure log directory exists
    Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
    
    old_valid, old_explanation = old_result
    new_valid, new_explanation, new_confidence, new_full_result = new_result
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "validation_comparison": {
            "old_method": {
                "type": "text_based_parsing",
                "is_valid": old_valid,
                "explanation": old_explanation,
            },
            "new_method": {
                "type": "json_structured_output",
                "result": new_full_result,  # Contains: equivalent, confidence, reason, key_differences, passed, score
            },
            "text_similarity": {
                "tfidf_cosine": text_similarity,
            },
            "agreement": old_valid == new_valid,
        },
        "content": {
            "actual_length": len(actual_content),
            "expected_length": len(expected_content),
            "actual_preview": actual_content,
            "expected_preview": expected_content,
        }
    }
    
    # Add prompt_text if provided
    if prompt_text:
        log_entry["validation_prompt"] = prompt_text
    
    # Append to log file (JSON Lines format with formatting)
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False, indent=2) + '\n')


def _save_validation_result(
    full_result: dict,
    actual_content: str,
    expected_content: str,
    debug_log_path: str,
    doc_index: int,
):
    """Save detailed validation result to test_results folder for debugging.
    
    Args:
        full_result: Full evaluation result dict from _llm_validate_content
        actual_content: Actual page_content
        expected_content: Expected page_content
        debug_log_path: Base path for debug logging
        doc_index: Document index
    """
    from datetime import datetime
    from pathlib import Path
    
    try:
        # Create validation_results subfolder in test_results
        log_path = Path(debug_log_path)
        validation_dir = log_path.parent / "validation_results"
        validation_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename based on debug_log_path and doc_index
        base_name = log_path.stem
        result_file = validation_dir / f"{base_name}_doc{doc_index}_validation.json"
        
        # Build detailed result
        detailed_result = {
            "timestamp": datetime.now().isoformat(),
            "doc_index": doc_index,
            "evaluation": full_result,
            "content_comparison": {
                "actual_length": len(actual_content),
                "expected_length": len(expected_content),
                "actual_preview": actual_content[:500] if len(actual_content) > 500 else actual_content,
                "expected_preview": expected_content[:500] if len(expected_content) > 500 else expected_content,
            }
        }
        
        # Save to JSON
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_result, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        import logging
        logging.warning(f"Failed to save validation result: {e}")


from deepeval.models import DeepEvalBaseLLM


class LangChainDeepEvalModel(DeepEvalBaseLLM):
    """Custom DeepEval model wrapper for LangChain LLMs.
    
    Implements DeepEval's expected interface for custom LLM integration.
    """
    
    def __init__(self, langchain_llm):
        """Wrap a LangChain LLM for use with DeepEval.
        
        Args:
            langchain_llm: LangChain LLM instance (e.g., ChatAnthropic)
        """
        self.langchain_llm = langchain_llm
        
        # Extract model name for DeepEval
        if hasattr(langchain_llm, 'model_name'):
            self.model = langchain_llm.model_name
        elif hasattr(langchain_llm, 'model'):
            self.model = langchain_llm.model
        else:
            self.model = langchain_llm.__class__.__name__
    
    def generate(self, prompt: str) -> str:
        """Generate response using LangChain LLM."""
        from langchain_core.messages import HumanMessage
        response = self.langchain_llm.invoke([HumanMessage(content=prompt)])
        return response.content
    
    async def a_generate(self, prompt: str) -> str:
        """Async generate response using LangChain LLM."""
        from langchain_core.messages import HumanMessage
        response = await self.langchain_llm.ainvoke([HumanMessage(content=prompt)])
        return response.content
    
    def get_model_name(self) -> str:
        """Return model name for logging."""
        return self.model
    
    def load_model(self):
        """DeepEval interface - model is already loaded."""
        return self.langchain_llm


def _llm_validate_content(
    actual_content: str,
    expected_content: str,
    llm,
    debug_log_path: str = None,
    input_context: str = "",
) -> tuple[bool, str, float, dict]:
    """Use DeepEval to semantically validate if actual and expected content are equivalent.
    
    Uses DeepEval's G-Eval metric for LLM-based semantic scoring with custom LangChain LLM.
    
    Args:
        actual_content: Actual page_content to validate
        expected_content: Expected page_content (baseline)
        llm: LangChain LLM instance for validation
        debug_log_path: Optional path to debug log file for comparison logging
        input_context: Optional input/prompt that generated the content (for LLM-based loaders)
        
    Returns:
        Tuple of (is_valid: bool, explanation: str, confidence: float, full_result: dict)
    """
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    
    # Wrap LangChain LLM for DeepEval
    deepeval_model = LangChainDeepEvalModel(llm)
    
    # Build evaluation criteria with optional input context
    if input_context:
        criteria = (f"Evaluate if the actual output and expected output contain the same essential information "
                    f"in response to (semantically equivalent response to): '{input_context}'. "
                    f"Actual output can be more verbose or formatted differently, but should convey the same meaning as the expected output.")
    else:
        criteria = ("Evaluate if the actual output and expected output contain equivalent essential information. "
                    "Actual output can be more verbose or formatted differently, but should convey the same meaning as the expected output.")
    
    # Create DeepEval G-Eval metric with custom model
    metric = GEval(
        name="Semantic Equivalence",
        criteria=criteria,
        # evaluation_steps=evaluation_steps,
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
        threshold=0.7,  # Pass threshold
        model=deepeval_model  # Use wrapped LangChain LLM
    )
    
    # Create test case
    test_case = LLMTestCase(
        input=input_context,
        actual_output=actual_content,
        expected_output=expected_content
    )
    
    # Run evaluation
    metric.measure(test_case)
    
    # Extract results
    score = metric.score  # 0.0-1.0
    is_valid = metric.is_successful()  # True if score >= 0.7
    reasoning = metric.reason  # Explanation from LLM
    
    # Build full result dict
    full_result = {
        "score": score,
        "reasoning": reasoning,
        "passed": is_valid,
        "method": "deepeval_geval",
        "threshold": 0.7,
        "model": deepeval_model.get_model_name(),
        "criteria": criteria
    }
    
    # Log comparison with old method if debug enabled
    if debug_log_path:
        try:
            old_result = _llm_validate_content_old_method(actual_content, expected_content, llm)
            text_similarity = calculate_text_similarity(actual_content, expected_content)
            
            # Log comparison
            _log_llm_validation_comparison(
                actual_content,
                expected_content,
                old_result,
                (is_valid, reasoning, score, full_result),
                text_similarity,
                debug_log_path,
                criteria
            )
        except Exception as e:
            import logging
            logging.warning(f"Failed to log validation comparison: {e}")
    
    return is_valid, reasoning, score, full_result


def _compare_page_content(
    actual_content: str,
    expected_content: str,
    doc_index: int,
    similarity_threshold: float = 0.95,
    llm=None,
    debug_log_path: str = None,
    input_context: str = None,
) -> Optional[DocumentDiff]:
    """Compare page_content using LLM validation (if available) or similarity score.
    
    Args:
        actual_content: Actual page_content (normalized)
        expected_content: Expected page_content (normalized)
        doc_index: Document index for error reporting
        similarity_threshold: Minimum similarity to pass (1.0 = exact match required)
        llm: Optional LLM instance for semantic validation
        debug_log_path: Optional path to debug log file for validation comparison
        input_context: Optional input/prompt that generated the content (for LLM-based loaders)
        
    Returns:
        DocumentDiff if content doesn't match threshold, None otherwise
    """
    # Try LLM validation first if available
    if llm is not None:
        try:
            is_valid, explanation, confidence, full_result = _llm_validate_content(
                actual_content, expected_content, llm, debug_log_path, input_context
            )
            
            # Save full_result to test_results folder for debugging
            if debug_log_path:
                _save_validation_result(full_result, actual_content, expected_content, debug_log_path, doc_index)
            
            if is_valid:
                return None
            
            # LLM validation failed - return diff with explanation and confidence
            # Also calculate traditional similarity for reference
            text_similarity = calculate_text_similarity(actual_content, expected_content)
            
            # Enrich explanation with key differences if available
            key_diffs = full_result.get("key_differences", [])
            if key_diffs:
                explanation += f" | Key differences: {', '.join(key_diffs[:3])}"
            
            return DocumentDiff(
                index=doc_index,
                field="page_content",
                actual=actual_content,
                expected=expected_content,
                diff_type="llm_validation",
                similarity=text_similarity,
                explanation=f"{explanation} (LLM confidence: {confidence:.2f})",
            )
        except Exception as e:
            # If LLM validation fails with exception, fallback to similarity
            import logging
            logging.warning(f"LLM validation failed with exception, falling back to similarity: {e}")
    
    # Fallback to similarity-based comparison
    similarity = calculate_text_similarity(actual_content, expected_content)
    
    # Check if similarity meets threshold
    if similarity >= similarity_threshold:
        return None
    
    return DocumentDiff(
        index=doc_index,
        field="page_content",
        actual=actual_content,
        expected=expected_content,
        diff_type="similarity",
        similarity=similarity,
    )


def _build_similarity_matrix(
    actual: List[Document],
    expected: List[Document],
    normalize: bool = True,
) -> List[DocumentDiff]:
    """Build similarity matrix when document counts differ.
    
    This helps identify which documents match and which are extra/missing.
    
    Args:
        actual: Actual documents from loader
        expected: Expected documents from baseline
        normalize: Whether to normalize text before comparison
        
    Returns:
        List of DocumentDiff objects showing similarity analysis
    """
    diffs: List[DocumentDiff] = []
    
    if not actual or not expected:
        return diffs
    
    # Normalize content for comparison
    actual_contents = [
        normalize_text(doc.page_content) if normalize else doc.page_content
        for doc in actual
    ]
    expected_contents = [
        normalize_text(doc.page_content) if normalize else doc.page_content
        for doc in expected
    ]
    
    # Calculate similarity matrix (actual vs expected)
    similarity_scores = []
    for i, a_content in enumerate(actual_contents):
        row = []
        for j, e_content in enumerate(expected_contents):
            sim_score = calculate_text_similarity(a_content, e_content)
            row.append((i, j, sim_score))
        similarity_scores.extend(row)
    
    # Sort by similarity (highest first) to find best matches
    similarity_scores.sort(key=lambda x: x[2], reverse=True)
    
    # Track which documents have been matched
    matched_actual = set()
    matched_expected = set()
    matches = []
    
    # Greedily match documents with highest similarity
    for actual_idx, expected_idx, score in similarity_scores:
        if actual_idx not in matched_actual and expected_idx not in matched_expected:
            matches.append((actual_idx, expected_idx, score))
            matched_actual.add(actual_idx)
            matched_expected.add(expected_idx)
    
    # Report matched pairs with similarity scores
    if matches:
        # Create a summary diff showing matches
        match_lines = []
        for actual_idx, expected_idx, score in sorted(matches):
            match_lines.append(f"    actual[{actual_idx}] ↔ expected[{expected_idx}]: similarity={score:.6f}")
        
        diffs.append(DocumentDiff(
            index=-1,
            field="similarity_matrix",
            actual=f"Best matches found:\n" + "\n".join(match_lines),
            expected="",
            diff_type="similarity",
        ))
    
    # Report unmatched actual documents (extras)
    unmatched_actual = set(range(len(actual))) - matched_actual
    if unmatched_actual:
        extra_info = []
        for idx in sorted(unmatched_actual):
            content_preview = actual_contents[idx][:100] + "..." if len(actual_contents[idx]) > 100 else actual_contents[idx]
            extra_info.append(f"    actual[{idx}]: {len(actual_contents[idx])} chars - {content_preview}")
        
        diffs.append(DocumentDiff(
            index=-1,
            field="extra_documents",
            actual=f"Found {len(unmatched_actual)} extra document(s) in actual:\n" + "\n".join(extra_info),
            expected="",
            diff_type="extra_key",
        ))
    
    # Report unmatched expected documents (missing)
    unmatched_expected = set(range(len(expected))) - matched_expected
    if unmatched_expected:
        missing_info = []
        for idx in sorted(unmatched_expected):
            content_preview = expected_contents[idx][:100] + "..." if len(expected_contents[idx]) > 100 else expected_contents[idx]
            missing_info.append(f"    expected[{idx}]: {len(expected_contents[idx])} chars - {content_preview}")
        
        diffs.append(DocumentDiff(
            index=-1,
            field="missing_documents",
            actual="",
            expected=f"Missing {len(unmatched_expected)} document(s) from expected:\n" + "\n".join(missing_info),
            diff_type="missing_key",
        ))
    
    return diffs


def compare_documents(
    actual: List[Document],
    expected: List[Document],
    ignore_metadata_fields=None,
    normalize: bool = True,
    loader_name: Optional[str] = None,
    llm=None,
    debug_log_path: str = None,
    input_context: str = None,
) -> ComparisonResult:
    """Deep-compare two Document lists following the flow:
    1. Compare document count
    2. Compare page_content using LLM validation (if available) or similarity
    3. Compare metadata structure and values
    
    Args:
        actual: Documents produced by the loader
        expected: Documents from baseline
        ignore_metadata_fields: Fields to exclude from comparison (deprecated, use loader-specific rules)
        normalize: Whether to normalize whitespace in page_content
        loader_name: Loader class name (e.g., "AlitaTextLoader") for loader-specific comparison rules
        llm: Optional LLM instance for semantic content validation
        debug_log_path: Optional path to debug log file for validation method comparison
        input_context: Optional input/prompt used to generate content (e.g., for LLM-based image analysis)
    """
    ignore = set(ignore_metadata_fields) if ignore_metadata_fields is not None else DEFAULT_IGNORE_METADATA
    diffs: List[DocumentDiff] = []

    # Step 1: Compare document count
    if len(actual) != len(expected):
        # Count mismatch - still try to match documents by similarity to identify differences
        diffs.append(DocumentDiff(index=-1, field="count", actual=len(actual), expected=len(expected)))
        
        # Build similarity matrix to find best matches
        similarity_matrix = _build_similarity_matrix(actual, expected, normalize)
        diffs.extend(similarity_matrix)
        
        return ComparisonResult(
            passed=False,
            actual_count=len(actual),
            expected_count=len(expected),
            diffs=diffs,
        )

    # Step 2 & 3: Compare each document's page_content and metadata
    # Get custom similarity threshold for this loader (default 0.95)
    special_fields = LOADER_SPECIAL_FIELDS.get(loader_name, {}) if loader_name else {}
    similarity_threshold = special_fields.get('similarity_threshold', 0.95)
    
    for i, (a_doc, e_doc) in enumerate(zip(actual, expected)):
        # Step 2: Compare page_content using LLM validation (if available) or similarity
        a_content = normalize_text(a_doc.page_content) if normalize else a_doc.page_content
        e_content = normalize_text(e_doc.page_content) if normalize else e_doc.page_content
        
        content_diff = _compare_page_content(a_content, e_content, i, similarity_threshold, llm=llm, debug_log_path=debug_log_path, input_context=input_context)
        if content_diff:
            diffs.append(content_diff)

        # Step 3: Compare metadata structure and values
        diffs.extend(_compare_metadata(a_doc.metadata, e_doc.metadata, i, ignore, loader_name))

    return ComparisonResult(
        passed=len(diffs) == 0,
        actual_count=len(actual),
        expected_count=len(expected),
        diffs=diffs,
    )
