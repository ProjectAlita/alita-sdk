# AlitaJSONLoader Test Suite

## Test Coverage

- **Test files**: 5
- **Total configs**: 15 (3 per file)
- **Parameters tested**: max_tokens (DEFAULT_ALLOWED_BASE)
- **Coverage**: 1/1 parameters (100%)

## Overview

This test suite validates the `AlitaJSONLoader` document loader implementation. The loader uses `RecursiveJsonSplitter` to chunk JSON data based on structural boundaries while respecting the `max_tokens` limit.

### Loader Configuration

- **kwargs**: `{}` (no production defaults)
- **allowed_to_override**: `DEFAULT_ALLOWED_BASE` = `{'max_tokens': 512}`
- **Behavior**: 
  - Converts JSON arrays to dictionaries with string indices
  - Uses `RecursiveJsonSplitter` for structural chunking
  - Adds metadata: `source`, `chunk_id` (1-indexed)

## Test Breakdown

| File | Configs | Purpose | Expected Behavior |
|------|---------|---------|-------------------|
| **json_simple.json** | 3 | Simple flat object with 8 key-value pairs | Single chunk for all configs (small size) |
| **json_array.json** | 3 | Array of 3 product objects | Converted to dict, single chunk for all configs |
| **json_nested.json** | 3 | Deeply nested company structure | Single chunk for all configs (moderate size) |
| **json_empty.json** | 3 | Empty JSON object `{}` | Single chunk containing empty object |
| **json_large.json** | 3 | Large nested structure with 3 users, profiles, posts | Multiple chunks for smaller max_tokens |

### Configuration Matrix

Each test file is processed with 3 configurations:

| Config | max_tokens | Purpose |
|--------|------------|---------|
| 0 | `{}` (default 512) | Production default behavior |
| 1 | 256 | Smaller chunks, more aggressive splitting |
| 2 | 1024 | Larger chunks, less splitting |

## Test Data Details

### json_simple.json
- **Size**: ~200 characters
- **Structure**: Flat object with employee data
- **Fields**: name, age, email, active, department, role, location, hire_date
- **Expected chunks**: 1 for all configs

### json_array.json
- **Size**: ~300 characters
- **Structure**: Array of 3 product objects
- **Conversion**: Array → `{"0": {...}, "1": {...}, "2": {...}}`
- **Expected chunks**: 1 for all configs

### json_nested.json
- **Size**: ~500 characters
- **Structure**: Nested company object with headquarters and departments
- **Depth**: 4 levels of nesting
- **Expected chunks**: 1 for all configs

### json_empty.json
- **Size**: 2 characters (`{}`)
- **Structure**: Empty object
- **Expected chunks**: 1 (containing `{}`)

### json_large.json
- **Size**: ~3000 characters (~700 tokens)
- **Structure**: Complex nested structure with users array
- **Content**: 3 users with profiles, skills, education, and posts
- **Expected chunks**:
  - Config 0 (512 tokens): 3 chunks (split by users)
  - Config 1 (256 tokens): 9 chunks (split by users, profiles, and posts)
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
# Run all JSON loader tests
pytest tests/runtime/langchain/document_loaders/test_alita_json_loader.py -v

# Run a specific input file
pytest tests/runtime/langchain/document_loaders/test_alita_json_loader.py -v -k "json_large"

# Run all document loader tests at once
pytest tests/runtime/langchain/document_loaders/ -v
```

### Filtering by Tag

Test files are tagged in `input/*.json`. Use `-m` to select subsets:

```bash
# All JSON loader tests
pytest -m "loader_json" -v

# JSON tests exercising chunking
pytest -m "loader_json and feature_chunking" -v

# Large-file / performance tests only
pytest -m "performance" -v

# Edge-case tests across all loaders
pytest -m "edge_empty_input" -v
```

| Tag | pytest mark | Applied to |
|-----|-------------|------------|
| `loader:json` | `loader_json` | All JSON configs |
| `content:array` | `content_array` | json_array configs |
| `content:empty` | `content_empty` | json_empty configs |
| `content:large` | `content_large` | json_large configs |
| `content:nested` | `content_nested` | json_nested configs |
| `content:simple` | `content_simple` | json_simple configs |
| `feature:chunking` | `feature_chunking` | All JSON configs |
| `performance` | `performance` | json_large configs |
| `edge:empty-input` | `edge_empty_input` | json_empty configs |

## Expected Results

All 15 tests (5 files × 3 configs) should pass with 100% success rate.

## Key Test Scenarios

1. **Simple JSON Objects** (`json_simple.json`): Validates basic object loading and single-chunk behavior
2. **Array Conversion** (`json_array.json`): Tests array-to-dict conversion before chunking
3. **Nested Structures** (`json_nested.json`): Validates handling of deeply nested objects
4. **Empty Edge Case** (`json_empty.json`): Tests loader behavior with empty JSON
5. **Chunking Behavior** (`json_large.json`): Validates RecursiveJsonSplitter with different max_tokens values

## Notes

- The loader always uses `RecursiveJsonSplitter` regardless of JSON size
- Arrays are converted to dictionaries with string indices before splitting
- Chunking respects JSON structural boundaries (no mid-object splits)
- Each chunk maintains valid JSON structure
- Metadata `chunk_id` is sequential (1, 2, 3, ...) across all chunks

## Test File Locations

```
AlitaJSONLoader/
├── files/               # Test data files
│   ├── json_simple.json
│   ├── json_array.json
│   ├── json_nested.json
│   ├── json_empty.json
│   └── json_large.json
├── input/               # Input JSON descriptors
│   ├── json_simple.json
│   ├── json_array.json
│   ├── json_nested.json
│   ├── json_empty.json
│   └── json_large.json
└── output/              # Baseline expectations
    ├── json_simple_config_0.json
    ├── json_simple_config_1.json
    ├── json_simple_config_2.json
    ├── json_array_config_0.json
    ├── json_array_config_1.json
    ├── json_array_config_2.json
    ├── json_nested_config_0.json
    ├── json_nested_config_1.json
    ├── json_nested_config_2.json
    ├── json_empty_config_0.json
    ├── json_empty_config_1.json
    ├── json_empty_config_2.json
    ├── json_large_config_0.json
    ├── json_large_config_1.json
    └── json_large_config_2.json
```
