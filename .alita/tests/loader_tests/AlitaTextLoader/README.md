# AlitaTextLoader Comprehensive Test Suite

## Overview

This directory contains a comprehensive test suite for `AlitaTextLoader` that systematically covers all parameters and corner cases in the chunking logic.

## Chunking Logic Understanding

### Flow
1. **AlitaTextLoader** receives `max_tokens` (default: 1024) and `token_overlap` (default: 10)
2. Passes these to **markdown_chunker** which:
   - Uses `min_chunk_chars=100` to merge small fragments
   - Splits content using `MarkdownHeaderTextSplitter` (no headers in plain text → single chunk)
   - If chunk > `max_tokens`: splits with `TokenTextSplitter` using `token_overlap`
   - Adds metadata: `headers`, `chunk_id`, `chunk_type`, `method_name`

### Key Parameters
- **max_tokens**: Maximum tokens per chunk (triggers splitting if exceeded)
- **token_overlap**: Overlap between consecutive chunks (context preservation)
- **min_chunk_chars**: 100 chars (hardcoded in markdown_chunker, merges tiny fragments)

### Tokenization
Uses `tiktoken` with `cl100k_base` encoding (GPT-4 tokenizer)

---

## Test Files

| File | Size | Purpose | Tests |
|------|------|---------|-------|
| `text_empty.txt` | 0 bytes | Edge: empty file | Empty input handling |
| `text_tiny.txt` | 15 chars | Edge: below min_chunk_chars | Sub-threshold content |
| `text_long_line.txt` | 502 chars | Edge: no newlines, long | Single-line splitting, overlap |
| `text_fragments.txt` | 107 chars | Edge: multiple tiny paras | Merge logic (min_chunk_chars) |
| `text_unicode.txt` | 547 chars | Unicode characters | Multi-byte char handling |
| `text_overlap.txt` | 958 chars | Designed for overlap tests | Token_overlap variations |
| `text_boundary.txt` | 619 chars | Boundary conditions | Exact token boundary behavior |
| `text_medium.txt` | 2300 chars | General case | Standard chunking (existing) |

---

## Test Configurations

### text_empty.json (3 configs)
Tests empty file handling with various settings.
```json
{} → max_tokens=1024, token_overlap=10
{"max_tokens": 100}
{"max_tokens": 1024, "token_overlap": 0}
```
**Expected**: 0 documents for all configs

### text_tiny.json (4 configs)
Tests content below min_chunk_chars (15 chars).
```json
{} → max_tokens=1024, token_overlap=10
{"max_tokens": 50}
{"max_tokens": 10}
{"max_tokens": 100, "token_overlap": 5}
```
**Expected**: 1 document for all (content too small to split)

### text_long_line.json (6 configs)
Tests single-line content that exceeds max_tokens. **Critical for overlap testing**.
```json
{} → 1 doc (502 chars < 1024 tokens)
{"max_tokens": 50, "token_overlap": 0} → Multiple docs, no overlap
{"max_tokens": 50, "token_overlap": 10} → Multiple docs, 10-token overlap
{"max_tokens": 50, "token_overlap": 20} → Multiple docs, 20-token overlap (40% overlap)
{"max_tokens": 100, "token_overlap": 5} → Fewer docs, minimal overlap
{"max_tokens": 100, "token_overlap": 30} → Fewer docs, high overlap (30%)
```
**Tests**: Overlap mechanism, no-overlap edge case, high-overlap edge case

### text_fragments.json (4 configs)
Tests merge logic for multiple small paragraphs (5 paras, each < 30 chars).
```json
{} → 1 doc (merged due to min_chunk_chars)
{"max_tokens": 50} → 1 doc (still merged)
{"max_tokens": 200} → 1 doc (entire content fits)
{"max_tokens": 100, "token_overlap": 20} → 1 doc (content too small)
```
**Tests**: min_chunk_chars merge behavior

### text_unicode.json (4 configs)
Tests Unicode/multi-byte character handling (Greek, Cyrillic, Chinese, Arabic, Emoji).
```json
{} → 1 doc
{"max_tokens": 100} → Multiple docs
{"max_tokens": 50, "token_overlap": 10} → More docs with overlap
{"max_tokens": 200, "token_overlap": 0} → Fewer docs, no overlap
```
**Tests**: Tokenization of multi-byte chars, overlap with Unicode

### text_overlap.json (6 configs)
Dedicated overlap testing with systematic token_overlap variations.
```json
{"max_tokens": 100, "token_overlap": 0} → Zero overlap baseline
{"max_tokens": 100, "token_overlap": 10} → 10% overlap
{"max_tokens": 100, "token_overlap": 20} → 20% overlap
{"max_tokens": 100, "token_overlap": 40} → 40% overlap (high)
{"max_tokens": 150, "token_overlap": 50} → 33% overlap
{"max_tokens": 50, "token_overlap": 15} → 30% overlap, small chunks
```
**Tests**: Full spectrum of overlap values (0%, 10%, 20%, 30%, 40%)

### text_boundary.json (6 configs)
Tests exact token boundary behavior with various max_tokens.
```json
{} → max_tokens=1024
{"max_tokens": 50}
{"max_tokens": 75}
{"max_tokens": 100}
{"max_tokens": 150}
{"max_tokens": 2000} → No splitting (exceeds content)
```
**Tests**: Boundary conditions, no-split case (max_tokens > content)

### text_medium.json (3 configs) - EXISTING
Standard chunking test (2.3KB structured prose).
```json
{} → 1 doc
{"max_tokens": 200} → 3 docs
{"max_tokens": 100} → 6 docs
```
**Tests**: Standard chunking progression

---

## Coverage Matrix

| Parameter | Values Tested | Configs |
|-----------|---------------|---------|
| **max_tokens** | 10, 50, 75, 100, 150, 200, 1024 (default), 2000 | 31 |
| **token_overlap** | 0, 5, 10 (default), 15, 20, 30, 40, 50 | 16 |

### Corner Cases Covered
✅ Empty file (0 bytes)  
✅ Tiny content (< min_chunk_chars)  
✅ Single line without newlines  
✅ Content exceeding max_tokens  
✅ Exact token boundaries  
✅ Multiple small fragments (merge logic)  
✅ Unicode/multi-byte characters  
✅ Zero overlap (token_overlap=0)  
✅ High overlap (token_overlap ≥ 30% of max_tokens)  
✅ No splitting needed (max_tokens > content)  
✅ Aggressive chunking (max_tokens=10, 50)  
✅ Standard chunking (max_tokens=100, 200, 1024)  
✅ Large buffer (max_tokens=2000)

---

## Running Tests

### Generate All Baselines
```bash
# From project root, generate baselines for all test inputs
for input in text_empty text_tiny text_long_line text_fragments text_unicode text_overlap text_boundary text_medium; do
    python .alita/tests/loader_tests/run_tests.py generate AlitaTextLoader $input --force
done
```

### Run All Tests
```bash
# All AlitaTextLoader tests
.venv/bin/python3 .alita/tests/loader_tests/run_tests.py run AlitaTextLoader

# Specific input
.venv/bin/python3 .alita/tests/loader_tests/run_tests.py run AlitaTextLoader text_overlap

# All loaders
.venv/bin/python3 .alita/tests/loader_tests/run_tests.py run
```

### Test Specific Config
```bash
# Run only config 2 of text_overlap
.venv/bin/python3 .alita/tests/loader_tests/run_tests.py run AlitaTextLoader text_overlap -c 2
```

---

## Expected Results Summary

**Total configs**: 36 (8 inputs × 3-6 configs each)

| Input | Configs | Expected Behavior |
|-------|---------|-------------------|
| text_empty | 3 | 0 docs (empty content) |
| text_tiny | 4 | 1 doc (below split threshold) |
| text_long_line | 6 | 1-3 docs (varies by max_tokens/overlap) |
| text_fragments | 4 | 1 doc (merged by min_chunk_chars) |
| text_unicode | 4 | 1-3 docs (tokenization test) |
| text_overlap | 6 | 3-6 docs (dedicated overlap testing) |
| text_boundary | 6 | 1-5 docs (boundary conditions) |
| text_medium | 3 | 1, 3, 6 docs (standard progression) |

---

## Metadata Schema

All chunks include:
```json
{
  "metadata": {
    "headers": "str (empty for plain text)",
    "chunk_id": "int (sequential)",
    "chunk_type": "str (document)",
    "method_name": "str (text|markdown)"
  }
}
```

**Note**: `source` and `chunk_id` are in `DEFAULT_IGNORE_METADATA` and excluded from baselines/comparison.

---

## Implementation Notes

### Limitations
- **min_chunk_chars** (100) is hardcoded in `markdown_chunker` and cannot be overridden via AlitaTextLoader
- **headers_to_split_on**, **strip_header**, **return_each_line** are not exposed by AlitaTextLoader
- **autodetect_encoding** parameter exists but requires non-UTF8 test files (not covered in this suite)

### Future Coverage
- Non-UTF8 encoding files (Latin-1, Windows-1252, etc.)
- Explicit encoding parameter testing
- File content vs file path modes (currently only file_path tested)

---

## Validation Checklist

Before committing baselines:

- [x] All 8 input JSONs created with valid `file_path: "../files/<name>.txt"`
- [x] All 8 test files exist in `files/` directory
- [ ] Baselines generated: `python run_tests.py generate AlitaTextLoader <input> --force`
- [ ] All tests pass: `run_tests.py run AlitaTextLoader` returns 36/36 passed
- [ ] No empty baseline files (except for text_empty which should have `[]`)
- [ ] Overlap configs show repeated content in adjacent chunks
- [ ] Zero-overlap configs show no repeated content

---

## Authoring Notes

Created: 2026-03-03  
Author: GitHub Copilot (Loaders Tests mode)  
Loader: AlitaTextLoader  
Chunker: markdown_chunker (alita_sdk/tools/chunkers/sematic/markdown_chunker.py)  
Coverage: 36 configs, 8 test files, all corner cases
