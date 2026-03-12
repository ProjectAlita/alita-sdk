# AlitaMarkdownLoader Test Suite

## Test Coverage

- **Test files**: 5
- **Total configs**: 15 (3 per file)
- **Parameters tested**: max_tokens (DEFAULT_ALLOWED_BASE)
- **Coverage**: 1/1 parameters (100%)

## Overview

This test suite validates the `AlitaMarkdownLoader` document loader implementation. The loader uses `markdown_chunker` to chunk Markdown text with header-aware splitting while respecting the `max_tokens` limit.

### Loader Configuration

- **kwargs**: `{}` (empty, uses internal chunker_config)
- **allowed_to_override**: `DEFAULT_ALLOWED_BASE` = `{'max_tokens': 512}`
- **Default chunker_config**:
  - `strip_header`: False
  - `return_each_line`: False
  - `headers_to_split_on`: []
  - `max_tokens`: 512
  - `token_overlap`: 10
- **Behavior**: 
  - Uses `markdown_chunker` for header-aware text splitting
  - Respects markdown structure (headers as natural boundaries)
  - Adds metadata: `source`, `headers`, `chunk_id`, `chunk_type`, `method_name`

## Test Breakdown

| File | Configs | Purpose | Expected Behavior |
|------|---------|---------|-------------------|
| **markdown_simple.md** | 3 | Simple markdown with one H1 header and paragraphs | Single chunk for all configs (~90 tokens) |
| **markdown_headers.md** | 3 | Document with H1 and multiple H2 sections | Single chunk for all configs (~120 tokens) |
| **markdown_nested.md** | 3 | Nested headers (H1, H2, H3) with content | Single chunk for all configs (~160 tokens) |
| **markdown_empty.md** | 3 | Empty markdown file (0 bytes) | Empty result list `[]` |
| **markdown_large.md** | 3 | Large document with multiple sections | Multiple chunks with smaller max_tokens (~900 tokens) |

### Configuration Matrix

Each test file is processed with 3 configurations:

| Config | max_tokens | Purpose |
|--------|------------|---------|
| 0 | `{}` (default 512) | Production default behavior |
| 1 | 256 | Smaller chunks, more aggressive splitting |
| 2 | 1024 | Larger chunks, less splitting |

## Test Data Details

### markdown_simple.md
- **Size**: ~450 characters (~90 tokens)
- **Structure**: Single H1 header with 3 paragraphs
- **Content**: Introduction to Python programming language
- **Expected chunks**: 1 for all configs

### markdown_headers.md
- **Size**: ~600 characters (~120 tokens)
- **Structure**: H1 with 4 H2 sections
- **Content**: Software development lifecycle phases
- **Expected chunks**: 1 for all configs

### markdown_nested.md
- **Size**: ~800 characters (~160 tokens)
- **Structure**: H1 > H2 (×2) > H3 (×6)
- **Content**: Web development topics (frontend and backend)
- **Expected chunks**: 1 for all configs

### markdown_empty.md
- **Size**: 0 bytes
- **Structure**: Empty file
- **Expected chunks**: 0 (empty list `[]`)

### markdown_large.md
- **Size**: ~4500 characters (~900 tokens)
- **Structure**: H1 with 9 H2 sections and 13 H3 subsections
- **Content**: Comprehensive cloud computing guide
- **Expected chunks**:
  - Config 0 (512 tokens): 3 chunks (split by major sections)
  - Config 1 (256 tokens): 8 chunks (split by H2 headers)
  - Config 2 (1024 tokens): 1 chunk (entire file)

## Coverage Metrics

### allowed_to_override Parameters

| Parameter | Tested | Test Files | Notes |
|-----------|--------|------------|-------|
| max_tokens | ✅ | All files (15 configs) | Tested with values: default (512), 256, 1024 |

**Total Coverage**: 1/1 (100%)

## Running Tests

All commands are run from the project root with the virtualenv active.

```bash
# Run all Markdown loader tests
pytest tests/runtime/langchain/document_loaders/test_alita_markdown_loader.py -v

# Run a specific input file
pytest tests/runtime/langchain/document_loaders/test_alita_markdown_loader.py -v -k "markdown_large"

# Run all document loader tests at once
pytest tests/runtime/langchain/document_loaders/ -v
```

### Filtering by Tag

Test files are tagged in `input/*.json`. Use `-m` to select subsets:

```bash
# All Markdown loader tests
pytest -m "loader_markdown" -v

# Markdown tests exercising chunking
pytest -m "loader_markdown and feature_chunking" -v

# Large-file / performance tests only
pytest -m "performance" -v

# Edge-case tests across all loaders
pytest -m "edge_empty_input" -v
```

| Tag | pytest mark | Applied to |
|-----|-------------|------------|
| `loader:markdown` | `loader_markdown` | All Markdown configs |
| `content:empty` | `content_empty` | markdown_empty configs |
| `content:headers` | `content_headers` | markdown_headers configs |
| `content:large` | `content_large` | markdown_large configs |
| `content:nested` | `content_nested` | markdown_nested configs |
| `content:simple` | `content_simple` | markdown_simple configs |
| `feature:chunking` | `feature_chunking` | All Markdown configs |
| `performance` | `performance` | markdown_large configs |
| `edge:empty-input` | `edge_empty_input` | markdown_empty configs |

## Expected Results

All 15 tests (5 files × 3 configs) should pass with 100% success rate.

## Key Test Scenarios

1. **Simple Markdown** (`markdown_simple.md`): Validates basic markdown loading with single header
2. **Header Structure** (`markdown_headers.md`): Tests header-based organization (H1 + H2)
3. **Nested Headers** (`markdown_nested.md`): Validates deeply nested header hierarchies (H1 > H2 > H3)
4. **Empty Edge Case** (`markdown_empty.md`): Tests loader behavior with empty file
5. **Chunking Behavior** (`markdown_large.md`): Validates header-aware splitting with different max_tokens values

## Notes

- The loader uses `markdown_chunker` for header-aware text splitting
- Chunking respects markdown structure (headers as natural boundaries)
- Token overlap is 10 tokens by default (configurable in chunker_config)
- Empty files return empty list `[]`, not a document with empty content
- Metadata `method_name`:
  - `"text"` for single chunk (entire file fits in max_tokens)
  - `"markdown"` for multiple chunks (file split due to size)
- Metadata `headers` contains header text for the section (empty string for document root)
- Metadata `chunk_id` is sequential (1, 2, 3, ...) across all chunks

## Loader Behavior

### Header-Aware Splitting

The markdown chunker splits text at header boundaries when content exceeds max_tokens:
- Respects markdown header hierarchy (H1, H2, H3, etc.)
- Tries to keep header sections together when possible
- Splits within sections only when a section exceeds max_tokens

### Token Overlap

With default 10-token overlap:
- Last 10 tokens of chunk N appear at the start of chunk N+1
- Maintains context continuity across chunk boundaries
- Helps with semantic coherence in downstream processing

### Metadata Structure

Each document chunk includes:
```json
{
  "page_content": "Markdown text content...",
  "metadata": {
    "source": "path/to/file.md",
    "headers": "",
    "chunk_id": 1,
    "chunk_type": "document",
    "method_name": "text" // or "markdown" for multi-chunk
  }
}
```

## Test File Locations

```
AlitaMarkdownLoader/
├── files/               # Test data files
│   ├── markdown_simple.md
│   ├── markdown_headers.md
│   ├── markdown_nested.md
│   ├── markdown_empty.md
│   └── markdown_large.md
├── input/               # Input JSON descriptors
│   ├── markdown_simple.json
│   ├── markdown_headers.json
│   ├── markdown_nested.json
│   ├── markdown_empty.json
│   └── markdown_large.json
└── output/              # Baseline expectations
    ├── markdown_simple_config_0.json
    ├── markdown_simple_config_1.json
    ├── markdown_simple_config_2.json
    ├── markdown_headers_config_0.json
    ├── markdown_headers_config_1.json
    ├── markdown_headers_config_2.json
    ├── markdown_nested_config_0.json
    ├── markdown_nested_config_1.json
    ├── markdown_nested_config_2.json
    ├── markdown_empty_config_0.json
    ├── markdown_empty_config_1.json
    ├── markdown_empty_config_2.json
    ├── markdown_large_config_0.json
    ├── markdown_large_config_1.json
    └── markdown_large_config_2.json
```
