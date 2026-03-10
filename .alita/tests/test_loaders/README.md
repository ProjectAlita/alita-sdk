# Alita SDK Document Loader Test Framework

**Declarative regression testing for 60+ document loaders with production-realistic configurations**

## Overview

A comprehensive baseline-driven testing system that validates document loader behavior across all supported formats. Tests use production configuration logic and manually-created expectations to catch bugs before they reach production.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Production Configuration** | Replicates exact `process_content_by_type` logic with 3-layer config resolution |
| **Baseline-Driven Testing** | Manually-created expectations ensure correctness, not just consistency |
| **Comprehensive Coverage** | Tests exercise all parameters in `allowed_to_override` for each loader |
| **Edge Case Validation** | Empty files, tiny content, unicode, boundary conditions, extreme values |
| **Automated Baseline Generation** | Optional tool for initial baseline creation (verify correctness first) |
| **Detailed Failure Reporting** | Exact metadata field mismatches with doc-level diff output |
| **Multiple Loaders Support** | Text, CSV, Excel, JSON, Markdown, YAML, HTML, XML, code files |
| **Chunking Analysis** | Comprehensive parameter coverage for token-based chunking (overlap, boundaries) |

### Architecture

**Execution Flow**: Config Resolution → Loader Invocation → Document Extraction → Baseline Comparison → Report

1. `run_tests.py list` - Discover all test cases across loaders
2. `run_tests.py run <Loader>` - Execute tests with production config logic
3. Compare actual output against baseline using metadata-aware comparison
4. Generate detailed pass/fail reports with exact mismatches
5. Optional: `generate` command for initial baseline creation (verify first)

**Tech Stack**: LangChain (loaders), Production config from `constants.py`, JSON baselines, Python comparison engine

---

## 🔴 Two Critical Mandatory Requirements

### 1. chunk_id Field in ALL Baselines

**The `chunk_id` field MUST be present in EVERY baseline document, regardless of loader implementation.**

- **Not optional**: This is a testing requirement
- **Forcefully inject**: Include it even if loader code doesn't set it
- **1-indexed sequential**: Format is 1, 2, 3, ... across all chunks
- **Purpose**: Catch incomplete loader implementations
- **When test fails**: If actual output missing chunk_id, this is a LOADER BUG (do not remove from baseline)

**Example**:
```json
[
  {"page_content": "chunk 1", "metadata": {"chunk_id": 1, "source": "...", ...}},
  {"page_content": "chunk 2", "metadata": {"chunk_id": 2, "source": "...", ...}}
]
```

### 2. Large Files for Chunking Loaders (max_tokens Testing)

**For loaders with `max_tokens` parameter (AlitaTextLoader, AlitaMarkdownLoader), tests MUST include:**

- **Large file**: ≥800 tokens that will be split into multiple chunks
- **Multiple max_tokens configs**: Test range 50, 100, 256, 512, 2000
- **10+ chunks**: At least one config should produce many chunks (e.g., max_tokens=50)
- **Purpose**: Small files that fit in one chunk do NOT test chunking behavior

**Why this is critical**: Without large file testing, chunking bugs, overlap logic, and chunk_id sequencing issues go undetected. The max_tokens parameter is the PRIMARY feature of chunking loaders.

### 3. Mandatory Chunking in Baselines

**🔴 CRITICAL: If content size exceeds default max_tokens value, baselines MUST contain multiple chunks.**

- **Automatic chunking requirement**: Content > default max_tokens → baseline MUST show chunks
- **Chunk size = max_tokens parameter** (±5 tokens for natural boundaries)
  - Config has `"max_tokens": 50` → expect ~45-55 tokens per chunk
  - Config has `"max_tokens": 100` → expect ~95-105 tokens per chunk
  - 🔴 **NEVER estimate by word count** - Use exact tokenizer measurements
- **Use tokenize utility to count tokens**:
  ```bash
  # Returns JSON array of token strings (count = array length)
  python run_tests.py tokenize "Your text content"
  ```
- **Understand semantic chunking**: `markdown_chunker` splits on paragraphs first, then applies token limits
- **Do NOT check loader implementation**: Calculate chunks independently using tokenization rules
- **Do NOT run loader code**: Baselines must be created manually, never by executing loader
- **Purpose**: Test validates that loader correctly implements chunking, not that baseline matches buggy output

**Example**: `AlitaTextLoader` default max_tokens=512:
- A 1000-token file with 2 paragraphs (500 tokens each):
  - Chunk 1: paragraph 1, tokens 0-499 (500 tokens, fits in max_tokens=512)
  - Chunk 2: paragraph 2, tokens 0-499 (500 tokens)
  - Total: 2 chunks (paragraph boundaries preserved)
- Same file with max_tokens=50:
  - Each 500-token paragraph splits into ~10-11 chunks of ~50 tokens each
  - Total: ~20-22 chunks with 10-token overlap

---

## Quick Start

### Prerequisites

```bash
# Install SDK with all dependencies
pip install -U '.[all]'

# Key files to understand
cat alita_sdk/runtime/langchain/document_loaders/constants.py  # Loader configs
cat .alita/tests/test_loaders/scripts/loader_test_runner.py  # Test runner
cat .alita/tests/test_loaders/scripts/loader_test_utils.py   # Comparison & serialization
```

### Run Your First Test

```bash
cd .alita/tests/test_loaders

# List all available tests
python run_tests.py list

# Run all tests for a loader
python run_tests.py run AlitaCSVLoader

# Run specific test input
python run_tests.py run AlitaCSVLoader csv_simple

# Run single config (fast iteration)
python run_tests.py run AlitaCSVLoader csv_simple -c 1

# Test chunking with custom text
python run_tests.py tokenize "Your text here"
```

**Results**: Console output shows pass/fail, mismatches saved to `test_results/output_YYYYMMDD_HHMMSS/`



---

## Configuration Strategy

### How Loaders Are Configured

Document loaders in Alita SDK follow a three-layer configuration model:

#### 1. Function Signature Defaults

Default parameter values in the loader's `__init__` method:

```python
class AlitaCSVLoader(AlitaTableLoader):
    def __init__(self,
                 file_path: str = None,
                 raw_content: bool = False,  # ← Function default
                 cleanse: bool = True,
                 ...):
```

#### 2. Production Defaults (constants.py)

Default kwargs applied by the platform when loading files. Defined in `alita_sdk/runtime/langchain/document_loaders/constants.py`:

```python
document_loaders_map = {
    '.csv': {
        'class': AlitaCSVLoader,
        'kwargs': {
            'encoding': 'utf-8',
            'raw_content': True,    # ← Production default
            'cleanse': False
        },
        'allowed_to_override': DEFAULT_ALLOWED_TABLE
    }
}
```

#### 3. User Overrides (chunking_config)

Users can customize loader behavior via `chunking_config` in indexing operations:

```python
# Example: Override CSV loader to use parsed mode
chunking_config = {
    ".csv": {
        "raw_content": False,
        "cleanse": True
    }
}
```

**Override Logic:**
- Only parameters in `allowed_to_override` can be customized
- User values replace production defaults when different
- This prevents unauthorized changes to critical loader settings

### Test Configuration Resolution

Tests replicate this production configuration logic:

```
Final kwargs = Production defaults (kwargs)
                + User overrides (test config)
                  (filtered by allowed_to_override)
```

**Example for CSV loader:**

```json
// Config 0: {} (empty) → uses production defaults
{
  "encoding": "utf-8",
  "raw_content": true,   // from kwargs
  "cleanse": false
}

// Config 1: {"raw_content": false} → overrides one param
{
  "encoding": "utf-8",
  "raw_content": false,  // overridden
  "cleanse": false
}
```

---

## Designing Test Configs

### Strategy: Cover All allowed_to_override Parameters

For each loader, identify the `allowed_to_override` set in constants.py and create configs that exercise:

1. **Default behavior** (`{}` config → production defaults)
2. **Each override parameter** (change one at a time)
3. **Parameter combinations** (common usage patterns)
4. **Edge cases** (extreme values, boundary conditions)

### Common allowed_to_override Sets

#### DEFAULT_ALLOWED_BASE
```python
{'max_tokens': LOADER_MAX_TOKENS_DEFAULT}
```
**Loaders:** Text, YAML, JSON, JSONL, Code files  
**Test configs:** `{}`, `{"max_tokens": 512}`, `{"max_tokens": 2000}`

#### DEFAULT_ALLOWED_TABLE
```python
{
    'max_tokens': LOADER_MAX_TOKENS_DEFAULT,
    'encoding': 'utf-8',
    'autodetect_encoding': True,
    'raw_content': True,
    'cleanse': False,
    'json_documents': True,
    'columns': None
}
```
**Loaders:** CSV  
**Test configs:**
- `{}` (raw_content=True, production default)
- `{"raw_content": false}` (parsed mode)
- `{"raw_content": false, "json_documents": false}` (tab-separated)
- `{"raw_content": false, "cleanse": true}` (cleansed text)

#### DEFAULT_ALLOWED_WITH_LLM
```python
{
    'max_tokens': LOADER_MAX_TOKENS_DEFAULT,
    'use_llm': False,
    'use_default_prompt': False,
    'prompt': ""
}
```
**Loaders:** PDF, HTML, XML, Images, DOCX, PPTX  
**Test configs:**
- `{}` (no LLM)
- `{"use_llm": true, "use_default_prompt": true}` (LLM with default prompt)
- `{"use_llm": true, "prompt": "Custom prompt"}` (LLM with custom prompt)

#### DEFAULT_ALLOWED_EXCEL
```python
{
    'max_tokens': LOADER_MAX_TOKENS_DEFAULT,
    'use_llm': False,
    'use_default_prompt': False,
    'prompt': "",
    'add_header_to_chunks': False,
    'header_row_number': 1,
    'sheet_name': ''
}
```
**Loaders:** Excel (XLSX, XLS)  
**Test configs:**
- `{}` (all sheets)
- `{"sheet_name": "Sheet1"}` (specific sheet)
- `{"add_header_to_chunks": true}` (include headers)
- `{"header_row_number": 2}` (custom header row)

### Chunking-Based Loaders

For loaders that use chunkers (AlitaTextLoader, AlitaMarkdownLoader), create **multiple test files** with varying content characteristics.

#### 🔴 MANDATORY REQUIREMENT: Large File for max_tokens Testing

**Critical:** Chunking loaders MUST include a large test file (≥800 tokens) with multiple max_tokens configs to validate actual chunking behavior:

| Requirement | Rationale |
|-------------|-----------|
| File ≥800 tokens | Small files fit in one chunk, don't test chunking |
| max_tokens: 50, 100, 256, 512, 2000 | Tests full range from aggressive to no splitting |
| 10+ chunks expected | Validates chunking pipeline, overlap logic, chunk_id sequencing |
| Baseline with multiple docs | Shows correct behavior across chunk boundaries |

**Without large file testing, chunking bugs go undetected.** The max_tokens parameter is the PRIMARY feature of these loaders and must be tested with files that require actual splitting.

#### Recommended Test File Matrix

| File Type | Purpose | Example Configs |
|-----------|---------|-----------------|
| 🔴 **Large** | **≥800 tokens (MANDATORY)** | `{}`, `{"max_tokens": 50}`, `{"max_tokens": 100}`, `{"max_tokens": 256}`, `{"max_tokens": 512}`, `{"max_tokens": 2000}` |
| Empty | 0-byte file | `{}`, `{"max_tokens": 512}` |
| Tiny | < 100 chars | `{}`, `{"max_tokens": 1024}` |
| Long line | 500+ chars, no breaks | `{"token_overlap": 0}`, `{"token_overlap": 20}` |
| Fragments | Multiple small paras | `{"max_tokens": 512}` |
| Unicode | Multi-byte characters | `{}`, `{"max_tokens": 1024}` |
| Overlap | Dedicated overlap testing | 6 configs: overlap 0%, 10%, 20%, 30%, 40% |
| Boundary | Token boundary alignment | `{"max_tokens": 10}`, `{"max_tokens": 50}`, `{"max_tokens": 2000}` |
| Medium | 1-3KB | `{}`, `{"max_tokens": 512}`, `{"max_tokens": 2048}` |

---

## Directory Structure

```
.alita/tests/test_loaders/
├── README.md                    # This file
├── run_tests.py                 # Standalone test runner
├── AlitaCSVLoader/
│   ├── files/                   # Test data files
│   │   ├── csv_simple.csv
│   │   ├── csv_empty.csv
│   │   └── csv_unicode.csv
│   ├── input/                   # Input descriptors
│   │   ├── csv_simple.json      # file_path + configs array
│   │   ├── csv_empty.json
│   │   └── csv_unicode.json
│   └── output/                  # Baseline expectations (committed)
│       ├── csv_simple_config_0.json
│       ├── csv_simple_config_1.json
│       └── ...
├── AlitaTextLoader/
│   ├── files/
│   ├── input/
│   └── output/
├── AlitaExcelLoader/
│   └── ...
└── test_results/                # Actual test runs (gitignored)
    └── output_YYYYMMDD_HHMMSS/
        ├── AlitaCSVLoader/
        │   ├── csv_simple_config_0.json
        │   └── ...
        └── AlitaTextLoader/
            └── ...
```

---

## Input JSON Format

Each test input is a JSON file in `<LoaderName>/input/` with:

```json
{
    "file_path": "../files/csv_simple.csv",
    "configs": [
        {},
        {"raw_content": false},
        {"raw_content": false, "json_documents": false},
        {"raw_content": false, "cleanse": true}
    ]
}
```

**Key fields:**
- `file_path`: Relative path to test data file (relative to input JSON location)
- `configs`: Array of configuration objects (each becomes a test case)

**Config 0** (empty `{}`) always tests production defaults from constants.py.

---

## Baseline JSON Format

Baselines are JSON files containing serialized `List[Document]`:

```json
[
  {
    "page_content": "product\tprice\tquantity\tcategory",
    "metadata": {
      "source": ".alita/tests/test_loaders/AlitaCSVLoader/files/csv_simple.csv:1",
      "table_source": ".alita/tests/test_loaders/AlitaCSVLoader/files/csv_simple.csv",
      "header": "true",
      "chunk_id": 1
    }
  },
  {
    "page_content": "Laptop\n899.99\n5\nElectronics",
    "metadata": {
      "source": ".alita/tests/test_loaders/AlitaCSVLoader/files/csv_simple.csv:2",
      "table_source": ".alita/tests/test_loaders/AlitaCSVLoader/files/csv_simple.csv",
      "columns": ["product", "price", "quantity", "category"],
      "og_data": "{\"product\": \"Laptop\", \"price\": \"899.99\", \"quantity\": \"5\", \"category\": \"Electronics\"}",
      "chunk_id": 2
    }
  }
]
```

**Critical rules:**
1. **All metadata fields**: Include every field the loader sets (read loader source code)
2. **chunk_id is mandatory**: Always include (1-indexed), even if loader doesn't set it
3. **Path format**: Use `.alita/tests/test_loaders/<Loader>/files/<file>` for path fields
4. **Exact values**: Metadata must match loader output exactly (except path suffix for `source`/`table_source`)

---

## Execution Modes

### 1. Run All Loaders

```bash
# Test all document loaders
python .alita/tests/test_loaders/run_tests.py run

# Results shown for each loader with pass/fail counts
```

**Use case**: CI/CD validation, comprehensive regression testing

### 2. Run Single Loader

```bash
# Test one loader class
python .alita/tests/test_loaders/run_tests.py run AlitaCSVLoader

# Output:
# AlitaCSVLoader
# --------------
#   [+] csv_simple[0]     docs: 1/1
#   [+] csv_simple[1]     docs: 6/6
#   [F] csv_unicode[2]    docs: 5/5  (metadata mismatch)
# Results: 2/3 passed
```

**Use case**: Testing after loader code changes, focused debugging

### 3. Run Single Test Input

```bash
# Test specific input JSON with all its configs
python .alita/tests/test_loaders/run_tests.py run AlitaCSVLoader csv_simple

# Runs all configs (0, 1, 2, ...) defined in csv_simple.json
```

**Use case**: Iterating on test data or baseline refinement

### 4. Run Single Config

```bash
# Test one config from an input JSON (fast iteration)
python .alita/tests/test_loaders/run_tests.py run AlitaCSVLoader csv_simple -c 1

# Runs only config[1] from csv_simple.json
```

**Use case**: Debugging specific configuration behavior

### 5. Manual Baseline Creation

**⚠️ Critical**: Baselines must be created manually by reasoning through loader behavior. Never generate them by running potentially buggy loaders.

**Baseline Creation Process**:

1. **Read the test data file** - Know the exact content
2. **Determine chunking requirement** - 🔴 **If content size > default max_tokens, baseline MUST contain multiple chunks**
3. **Understand loader configuration** - Check `constants.py` for production defaults and `allowed_to_override`
4. **Apply tokenization rules INDEPENDENTLY** - For text-based loaders:
   - Tokenize text using the configured encoding (typically cl100k_base for gpt-4)
   - Split into chunks based on `max_tokens` parameter
   - Apply **10 token overlap** between consecutive chunks
   - 🔴 **NEVER check loader implementation** - Calculate chunks using tokenization rules only
   - 🔴 **NEVER run loader code** - Baselines are specifications, not execution outputs
5. **Calculate metadata** - Determine all metadata fields the loader should set
6. **Create baseline JSON** - Write `List[Document]` with correct `page_content` and `metadata`
7. **Verify correctness** - Run test and fix baseline or loader if needed

**Tokenization Example**:
```bash
# Count tokens in text (returns JSON array of token strings)
python run_tests.py tokenize "Hello world! This is a test."
# Returns: ["Hello", " world", "!", " This", " is", " a", " test", "."]
# Token count: 8 tokens (length of array)

# For files: read content first, then tokenize
cat path/to/file.txt | python run_tests.py tokenize "$(cat path/to/file.txt)"

# Calculate chunks manually using 10-token overlap rule:
# For a 100-token document with max_tokens=50:
# Chunk 1: tokens 0-49   (50 tokens)
# Chunk 2: tokens 40-89  (50 tokens, 10 token overlap with chunk 1)
# Chunk 3: tokens 80-99  (20 tokens, 10 token overlap with chunk 2)
```

**Note on Semantic Chunking**: `markdown_chunker` splits on paragraph boundaries first, then applies token limits. A 100-token file with 2 paragraphs (50 tokens each) produces 2 chunks WITHOUT splitting, not 3 chunks with overlap.

**Workflow**:
1. Create test data file and input JSON
2. **Use tokenize utility to count tokens** (avoid manual word-count estimation)
3. **Manually calculate chunks** using tokenization rules (10-token overlap, paragraph boundaries)
4. Create baseline JSON: `<Loader>/output/<input>_config_N.json`
5. Inspect baseline to ensure correctness (chunk sizes match max_tokens ±5)
6. Run test to validate: `python run_tests.py run <Loader> <input>`

### 6. 🔴 MANDATORY: chunk_id in All Baselines

**Critical Testing Requirement**: The `chunk_id` field MUST be present in EVERY baseline document, regardless of whether the loader implementation sets it.

**Why This is Mandatory**:
- **Not optional**: This is a testing requirement, not a loader feature
- **Catch bugs**: If loader doesn't set chunk_id, test fails INTENTIONALLY
- **Do not rely on implementation**: Forcefully inject it in baselines even if loader code doesn't mention it
- **Purpose**: Ensure loaders properly track chunk sequencing

**Format Requirements**:
```json
{
  "page_content": "...",
  "metadata": {
    "chunk_id": 1,  // 🔴 MANDATORY: 1-indexed integer
    "source": "...",
    "other_fields": "..."
  }
}
```

**Rules**:
- Start at 1 (not 0)
- Increment sequentially (1, 2, 3, 4, ...)
- Include in EVERY document, even single-chunk cases
- Include even if loader source code doesn't set it

**Example - Multiple Chunks**:
```json
[
  {"page_content": "chunk 1", "metadata": {"chunk_id": 1, ...}},
  {"page_content": "chunk 2", "metadata": {"chunk_id": 2, ...}},
  {"page_content": "chunk 3", "metadata": {"chunk_id": 3, ...}}
]
```

**Example - Single Chunk**:
```json
[
  {"page_content": "entire file", "metadata": {"chunk_id": 1, ...}}
]
```

**What Happens If You Skip It**:
- ❌ Test fails with metadata mismatch
- ✅ This is CORRECT - it exposes incomplete loader implementation
- **Do not "fix" by removing from baseline** - this defeats the purpose
- Instead: Either fix the loader OR document as blocked (loader bug)

---

## Debugging Tests

### Quick Debug Loop

```bash
# 1. Run failing test to see error
python run_tests.py run AlitaCSVLoader csv_unicode -c 2

# 2. Inspect actual output
cat test_results/output_YYYYMMDD_HHMMSS/AlitaCSVLoader/csv_unicode_config_2.json

# 3. Compare with baseline
cat AlitaCSVLoader/output/csv_unicode_config_2.json

# 4. Fix loader or baseline, then re-run
python run_tests.py run AlitaCSVLoader csv_unicode -c 2
```

### Debugging Strategies

#### 1. IDE Debugging

```bash
# Set breakpoint in scripts/loader_test_runner.py or loader source
python -m pdb run_tests.py run AlitaCSVLoader csv_simple -c 1
```

**Key files to debug**:
- `.alita/tests/test_loaders/scripts/loader_test_runner.py` - Test execution logic
- `.alita/tests/test_loaders/scripts/loader_test_utils.py` - Comparison logic
- `alita_sdk/runtime/langchain/document_loaders/<LoaderClass>.py` - Loader implementation

#### 2. Verbose Failure Analysis

```bash
# Run test and capture full output
python run_tests.py run AlitaCSVLoader csv_simple 2>&1 | tee debug.log

# Search for specific metadata fields
grep -A 5 "metadata.chunk_id" debug.log
```

#### 3. Manual Loader Invocation

```python
# Test loader directly in Python REPL
from alita_sdk.runtime/langchain/document_loaders/AlitaCSVLoader import AlitaCSVLoader

loader = AlitaCSVLoader(
    file_path=".alita/tests/test_loaders/AlitaCSVLoader/files/csv_simple.csv",
    raw_content=False,
    cleanse=True
)
docs = loader.load()

# Inspect output
for i, doc in enumerate(docs):
    print(f"Doc {i}: {doc.page_content[:50]}...")
    print(f"Metadata: {doc.metadata}")
```

#### 4. Configuration Resolution Debugging

```python
# Verify config resolution logic
from alita_sdk.tools.utils.content_parser import process_content_by_type
from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map

# Check production defaults
csv_config = loaders_map['.csv']
print(f"kwargs: {csv_config['kwargs']}")
print(f"allowed_to_override: {csv_config['allowed_to_override']}")

# Test config resolution
test_config = {"raw_content": False, "cleanse": True}
# ... apply resolution logic
```

#### 5. Baseline Validation

```bash
# Validate baseline JSON syntax
python -m json.tool AlitaCSVLoader/output/csv_simple_config_0.json

# Check for required fields
jq '.[] | .metadata | keys' AlitaCSVLoader/output/csv_simple_config_0.json

# Verify chunk_id sequence
jq '.[] | .metadata.chunk_id' AlitaCSVLoader/output/csv_simple_config_0.json
```

### Common Debug Scenarios

| Problem | Debug Command | Solution |
|---------|---------------|----------|
| Metadata mismatch | `diff -u baseline.json actual.json` | Fix loader or baseline |
| Missing chunk_id | `jq '.[] .metadata.chunk_id' actual.json` | Add to loader implementation |
| Wrong token count | Run with `max_tokens=50` (small value) | Check chunking logic |
| Path format error | `grep source baseline.json` | Use `.alita/tests/test_loaders/<Loader>/files/<file>` format |
| Config has no effect | Check `allowed_to_override` in constants.py | Param may not be overridable |

---

## Test Output Interpretation

### Success Output

```
AlitaCSVLoader
--------------
  [+] csv_simple[0]                           docs: 1/1
  [+] csv_simple[1]                           docs: 6/6
  [+] csv_unicode[0]                          docs: 5/5

Results: 3/3 passed  (0 failed, 0 errors)
```

**Meaning**: All tests passed, document counts match, all metadata fields match exactly

### Failure (Metadata Mismatch)

```
AlitaCSVLoader
--------------
  [F] csv_simple[1]                           docs: 6/6
       Baseline: .alita/tests/test_loaders/AlitaCSVLoader/output/csv_simple_config_1.json
       FAIL  (actual=6 docs, expected=6 docs)
         [doc #1] metadata.source:
           actual  : '.../csv_simple.csv:1'
           expected: '.../csv_simple.csv:2'
         [doc #3] metadata.chunk_id:
           actual  : 3
           expected: 4

Results: 0/1 passed  (1 failed, 0 errors)
```

**Meaning:** Document count matches but specific metadata fields differ. Shows exact field paths and values.

**Action**: Inspect `test_results/output_YYYYMMDD_HHMMSS/AlitaCSVLoader/csv_simple_config_1.json` and compare with baseline

### Error (Loader Exception)

```
AlitaCSVLoader
--------------
  [E] csv_malformed[0]                        docs: 0/6
       ERROR: Loader exception: ValueError: invalid literal for int() with base 10: 'abc'
       Traceback:
         File "AlitaCSVLoader.py", line 123, in _parse_row
           int(value)

Results: 0/1 passed  (0 failed, 1 errors)
```

**Meaning**: Loader crashed during execution (not a comparison failure)

**Action**: Fix loader bug or test data file

### Document Count Mismatch

```
AlitaCSVLoader
--------------
  [F] csv_simple[2]                           docs: 5/6
       Baseline: .alita/tests/test_loaders/AlitaCSVLoader/output/csv_simple_config_2.json
       FAIL  (actual=5 docs, expected=6 docs)

Results: 0/1 passed  (1 failed, 0 errors)
```

**Meaning**: Loader produced different number of documents than expected

**Action**: Verify chunking logic or baseline document count

---

## Advanced Topics

### Custom Comparison Logic

Tests use special comparison rules for certain metadata fields:

**Path Suffix Matching** (for `source`, `table_source`):
```python
# Actual path can be absolute, baseline uses relative path
# Comparison: actual.endswith(expected) → True

# Actual:   /Users/user/alita-sdk/.alita/tests/test_loaders/AlitaCSVLoader/files/data.csv
# Expected: .alita/tests/test_loaders/AlitaCSVLoader/files/data.csv
# Result:   PASS (suffix matches)
```

**Loader-Specific Field Mappings**:
- Text loaders: Check `source` field for path suffix
- Table loaders (CSV, Excel): Check both `source` and `table_source`
- Defined in `LOADER_SPECIAL_FIELDS` in `loader_test_utils.py`

### Extending the Test Framework

**Add new loader tests**:
1. Create `<LoaderClassName>/` directory
2. Add `files/`, `input/`, `output/` subdirectories
3. Create test data files in `files/`
4. Create input JSON descriptors in `input/`
5. Manually create baseline JSON files in `output/`
6. Run `python run_tests.py run <LoaderClassName>`

**Custom metadata validators**:
Edit `loader_test_utils.py` to add special comparison rules for new fields.

### Multi-Loader Test Suites

```bash
# Test multiple loaders in sequence
for loader in AlitaTextLoader AlitaCSVLoader AlitaJSONLoader; do
  python run_tests.py run $loader || exit 1
done

# Or use run without arguments to test all
python run_tests.py run  # Tests all loaders with test data
```

### CI/CD Integration

**GitHub Actions Example**:
```yaml
- name: Run Loader Tests
  run: |
    cd .alita/tests/test_loaders
    python run_tests.py run
  env:
    PYTHONPATH: ${{ github.workspace }}

- name: Upload Test Results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: loader-test-results
    path: .alita/tests/test_loaders/test_results/
```

**Exit Codes**:
- `0` - All tests passed
- `1` - One or more tests failed or errored

### Performance Optimization

**Parallel execution** (for multiple loaders):
```bash
# Run loaders in parallel (requires GNU parallel or xargs)
echo "AlitaTextLoader AlitaCSVLoader AlitaJSONLoader" | \
  xargs -n 1 -P 3 python run_tests.py run
```

**Incremental testing**:
```bash
# Test only loaders with recent code changes
git diff --name-only HEAD~1 | \
  grep 'document_loaders/' | \
  awk -F'/' '{print $NF}' | \
  sed 's/.py$//' | \
  xargs -I {} python run_tests.py run {}
```

---

## Quick Reference

### Command Cheat Sheet

```bash
# Discovery
python run_tests.py list                              # List all test cases

# Execution
python run_tests.py run                               # Run all loaders
python run_tests.py run <Loader>                      # Run one loader
python run_tests.py run <Loader> <input>              # Run one input (all configs)
python run_tests.py run <Loader> <input> -c N         # Run one config

# Tokenization Helper
python run_tests.py tokenize "Your text"              # Count tokens (returns JSON token string array)
```

### File Locations

| Item | Location |
|------|----------|
| Test runner | `.alita/tests/test_loaders/run_tests.py` |
| Loader configs | `alita_sdk/runtime/langchain/document_loaders/constants.py` |
| Loader source | `alita_sdk/runtime/langchain/document_loaders/<LoaderClass>.py` |
| Test data | `.alita/tests/test_loaders/<LoaderClass>/files/` |
| Input JSONs | `.alita/tests/test_loaders/<LoaderClass>/input/` |
| Baselines | `.alita/tests/test_loaders/<LoaderClass>/output/` |
| Test results | `.alita/tests/test_loaders/test_results/output_YYYYMMDD_HHMMSS/` |
| Comparison logic | `.alita/tests/test_loaders/scripts/loader_test_utils.py` |
| Test runner logic | `.alita/tests/test_loaders/scripts/loader_test_runner.py` |

### Configuration Quick Reference

```python
# DEFAULT_ALLOWED_BASE (Text, JSON, YAML, Code)
{'max_tokens': LOADER_MAX_TOKENS_DEFAULT}

# DEFAULT_ALLOWED_TABLE (CSV)
{
    'max_tokens': ...,
    'encoding': 'utf-8',
    'autodetect_encoding': True,
    'raw_content': True,
    'cleanse': False,
    'json_documents': True,
    'columns': None
}

# DEFAULT_ALLOWED_WITH_LLM (PDF, Images, HTML, XML, DOCX, PPTX)
{
    'max_tokens': ...,
    'use_llm': False,
    'use_default_prompt': False,
    'prompt': ""
}

# DEFAULT_ALLOWED_EXCEL (XLSX, XLS)
{
    # ... WITH_LLM fields ...
    'add_header_to_chunks': False,
    'header_row_number': 1,
    'sheet_name': ''
}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All tests passed |
| `1` | One or more tests failed or errored |

---

## Best Practices

### Test Data Creation

**DO**:
- ✅ Keep files small (1-3KB) for fast execution
- 🔴 **MANDATORY for chunking loaders:** Include large file (≥800 tokens) to test actual chunking
- ✅ Use deterministic content (no timestamps, UUIDs, randomness)
- ✅ Cover edge cases (empty, single-line, unicode, boundary conditions)
- ✅ Use realistic, domain-appropriate content
- ✅ Test unicode with multiple scripts (emoji, CJK, Arabic, Cyrillic)

**DON'T**:
- ❌ Use large files (>10KB) unless testing chunking behavior
- 🔴 **CRITICAL ERROR:** Test chunking loaders WITHOUT large files that actually chunk
- ❌ Include dynamic content that changes between runs
- ❌ Use Lorem Ipsum or meaningless text
- ❌ Ignore edge cases (empty files are critical)
- 🔴 **CRITICAL ERROR:** Test max_tokens with only small files that fit in one chunk

### Config Design

**DO**:
- ✅ Always start with `{}` config (tests production defaults)
- 🔴 **MANDATORY for chunking loaders:** Test max_tokens with range 50-2000 on large file
- ✅ Change one parameter at a time (isolates effects)
- ✅ Exercise all parameters in `allowed_to_override`
- ✅ Test edge values (min/max, zero, negative where applicable)
- ✅ Document why each config exists

**DON'T**:
- ❌ Test parameters NOT in `allowed_to_override` (users can't override them)
- ❌ Create redundant configs (same effective behavior)
- ❌ Skip the `{}` config (critical for production defaults)
- 🔴 **CRITICAL ERROR:** Test max_tokens with only one or two values

### Baseline Creation

**DO**:
- ✅ Read loader specification and constants.py before writing baselines
- ✅ Manually calculate expected output using tokenization rules (10 token overlap)
- ✅ Use `python run_tests.py tokenize "text"` to count tokens (returns token string array)
- ✅ Include ALL metadata fields loader produces
- 🔴 **MANDATORY: Forcefully inject `chunk_id` field in EVERY baseline document**
  - Do NOT rely on loader implementation to set it
  - Format: 1-indexed integer (1, 2, 3, ...), sequential
  - This is a testing requirement - if loader doesn't set it, test fails INTENTIONALLY
  - Purpose: Catch incomplete loader implementations
- ✅ Use relative paths in path fields
- ✅ Verify baseline correctness before committing

**DON'T**:
- ❌ Run potentially buggy loader code to generate baselines
- ❌ Rely on existing loader implementation to calculate expected chunks
- 🔴 **CRITICAL ERROR: Guess token counts by word count** - Always use tokenize utility
- 🔴 **CRITICAL ERROR: Check loader implementation to determine if chunks should exist** - Use content size vs default max_tokens instead
- 🔴 **CRITICAL ERROR: Run loader to see what it outputs** - Baselines are independent specifications
- 🔴 **CRITICAL ERROR: Create baselines without running tokenize command** - You cannot accurately predict chunks manually
- ❌ Omit metadata fields to "simplify" baselines
- ❌ Use absolute paths in baselines
- 🔴 **CRITICAL ERROR: Skip `chunk_id` field because loader doesn't set it**
- ❌ Forget the 10 token overlap rule for chunked loaders
- 🔴 **CRITICAL ERROR: Create single-chunk baseline for content > default max_tokens**
- 🔴 **CRITICAL ERROR: Assume chunk size will be exactly max_tokens** - Semantic chunking respects paragraph boundaries (±5 tokens variance)

### Development Workflow

**Recommended Flow**:
1. Study `allowed_to_override` in constants.py for target loader
2. Create test data file exercising parameters
3. Create input JSON with all `allowed_to_override` params
4. Manually create baseline by reasoning through loader behavior
5. Run test: `python run_tests.py run <Loader> <input>`
6. If fails, debug: is baseline wrong or loader wrong?
7. Fix either baseline or loader, re-run
8. Document coverage in loader's README.md

**Fast Iteration**:
```bash
# 1. First run (all configs)
python run_tests.py run AlitaCSVLoader csv_simple

# 2. Focus on failing config
python run_tests.py run AlitaCSVLoader csv_simple -c 2

# 3. Inspect actual output
cat test_results/output_*/AlitaCSVLoader/csv_simple_config_2.json

# 4. Fix and re-test (repeat step 2)
```

### Performance Tips

**Execution Speed**:
- Specific loader: `10x faster` than all loaders
- Specific input: `5x faster` than full loader
- Specific config: `2x faster` than full input

**Example**:
```bash
# Slowest: All loaders (~60s for 8 loaders)
python run_tests.py run

# Faster: One loader (~6s for 8 inputs)
python run_tests.py run AlitaCSVLoader

# Fastest: One config (~0.3s)
python run_tests.py run AlitaCSVLoader csv_simple -c 1
```

---

## Reference Materials

### Key Files

| File | Purpose |
|------|---------|
| `alita_sdk/runtime/langchain/document_loaders/constants.py` | Loader-to-extension mapping, defaults, allowed_to_override |
| `alita_sdk/runtime/langchain/document_loaders/AlitaTableLoader.py` | Base class for CSV/Excel loaders |
| `alita_sdk/runtime/langchain/document_loaders/AlitaTextLoader.py` | Text/code file loader with chunking |
| `.alita/tests/test_loaders/scripts/loader_test_runner.py` | Test execution engine |
| `.alita/tests/test_loaders/scripts/loader_test_utils.py` | Document comparison & serialization |
| `alita_sdk/tools/utils/content_parser.py` | Production loader invocation |

### Example Test Suites

| Loader | Location | Notable Features |
|--------|----------|------------------|
| AlitaTextLoader | `.alita/tests/test_loaders/AlitaTextLoader/` | 8 files, 33 configs, comprehensive chunking coverage |
| AlitaCSVLoader | `.alita/tests/test_loaders/AlitaCSVLoader/` | Raw vs parsed modes, cleansing, tab-separated |

---

## Troubleshooting

### Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| **Baseline not found** | No baseline created yet | Manually create baseline in `<Loader>/output/` |
| **Config has no effect** | Parameter not in `allowed_to_override` | Check constants.py, param may not be user-overridable |
| **Metadata mismatch on `source`** | Path format incorrect | Use `.alita/tests/test_loaders/<Loader>/files/<file>` format |
| **Document count mismatch** | Chunking calculation error | Recalculate using tokenization rules (10 token overlap) |
| **chunk_id missing** | Baseline incomplete | Add `chunk_id` field to baseline (1-indexed, sequential) |
| **Unicode encoding errors** | Test data encoding issue | Ensure UTF-8 encoding for test files |
| **JSON parse error in baseline** | Invalid JSON syntax | `python -m json.tool <baseline>.json` to validate |
| **All tests fail after SDK update** | Breaking change in loaders | Verify correctness, update baselines if behavior is correct |

### Debugging Checklist

When a test fails:

1. **Identify failure type**: Metadata mismatch, document count, or loader error?
   ```bash
   python run_tests.py run <Loader> <input> -c N  # Focused run
   ```

2. **Inspect actual output**: 
   ```bash
   cat test_results/output_*/< Loader>/<input>_config_N.json
   ```

3. **Compare with baseline**:
   ```bash
   diff -u <Loader>/output/<input>_config_N.json \
           test_results/output_*/<Loader>/<input>_config_N.json
   ```

4. **Verify configuration**: Config parameter actually overrides production default?
   ```bash
   grep -A 10 "'.ext':" alita_sdk/runtime/langchain/document_loaders/constants.py
   ```

5. **Test loader manually**: Isolate loader from test framework
   ```python
   from alita_sdk.runtime.langchain.document_loaders.<Loader> import <Loader>
   loader = <Loader>(file_path="...", config_param=value)
   docs = loader.load()
   print(docs[0].metadata)  # Inspect
   ```

6. **Determine root cause**: Is baseline wrong or loader wrong?
   - Read loader source to understand expected behavior
   - Calculate expected output manually
   - Compare with both actual and baseline

7. **Fix and re-test**:
   - Fix loader code OR
   - Fix baseline JSON OR
   - Fix test data file
   ```bash
   python run_tests.py run <Loader> <input> -c N  # Verify fix
   ```

### Getting Help

**Before filing an issue:**
- ✅ Check this troubleshooting section
- ✅ Run with single config (`-c N`) for focused error
- ✅ Inspect actual output in `test_results/`
- ✅ Verify `allowed_to_override` in constants.py
- ✅ Test loader manually in Python REPL

**When filing issues, include:**
- Test command used: `python run_tests.py run ...`
- Full error output
- Actual output JSON: `test_results/output_*/<Loader>/<input>_config_N.json`
- Baseline JSON: `<Loader>/output/<input>_config_N.json`
- Test data file: `<Loader>/files/<file>`
- SDK version: `pip show alita-sdk`

---

## Creating New Tests

### Step-by-Step Guide

**1. Identify Target Loader**
```bash
# Check which loaders exist
ls alita_sdk/runtime/langchain/document_loaders/*.py | grep -v "__"

# Review loader configuration
grep -A 15 "'.ext':" alita_sdk/runtime/langchain/document_loaders/constants.py
```

**2. Analyze Configuration**
```python
# From constants.py, identify:
# - kwargs (production defaults)
# - allowed_to_override (user-configurable params)

# Example for CSV:
'.csv': {
    'kwargs': {'encoding': 'utf-8', 'raw_content': True, 'cleanse': False},
    'allowed_to_override': DEFAULT_ALLOWED_TABLE  # 7 parameters
}
```

**3. Create Directory Structure**
```bash
mkdir -p .alita/tests/test_loaders/AlitaMyLoader/{files,input,output}
```

**4. Create Test Data Files**
```bash
# Create files that enable testing all allowed_to_override params
# Example for CSV: files exercise raw_content, cleanse, json_documents, etc.

cat > AlitaMyLoader/files/my_simple.ext << EOF
... test data ...
EOF

# Create edge case files
touch AlitaMyLoader/files/my_empty.ext             # Empty file
echo "tiny" > AlitaMyLoader/files/my_tiny.ext      # Tiny content
```

**5. Create Input JSON**
```json
// AlitaMyLoader/input/my_simple.json
{
    "file_path": "../files/my_simple.ext",
    "configs": [
        {},                                  // Production defaults
        {"param1": value1},                  // Override single param
        {"param1": value1, "param2": value2}, // Combination
        {"param1": extreme_value}            // Edge case
    ]
}
```

**6. Manually Create Baselines**
```bash
# CRITICAL: Never run the loader to generate baselines - calculate them manually!

# 1. Read test data file
cat AlitaMyLoader/files/my_simple.ext

# 2. Check tokenization (for text-based loaders)
python .alita/tests/test_loaders/run_tests.py tokenize "$(cat AlitaMyLoader/files/my_simple.ext)"

# 3. Apply config resolution
# Final kwargs = production kwargs + test config (filtered by allowed_to_override)
grep -A 10 "'.ext':" alita_sdk/runtime/langchain/document_loaders/constants.py

# 4. Calculate expected documents manually
# For text-based loaders:
#   - Tokenize content using cl100k_base encoding
#   - Split into chunks of max_tokens size
#   - Apply 10 token overlap between chunks
#   - Calculate metadata fields per loader specification

# 5. Write baseline JSON
cat > AlitaMyLoader/output/my_simple_config_0.json << 'EOF'
[
  {
    "page_content": "...",
    "metadata": {
      "source": ".alita/tests/test_loaders/AlitaMyLoader/files/my_simple.ext",
      "chunk_id": 1,
      "chunk_type": "document",
      "method_name": "text",
      "headers": ""
    }
  }
]
EOF
```

**7. Run Tests**
```bash
# Test all configs
python run_tests.py run AlitaMyLoader my_simple

# If failures, debug
python run_tests.py run AlitaMyLoader my_simple -c 0

# Inspect actual output
cat test_results/output_*/AlitaMyLoader/my_simple_config_0.json

# Fix baseline or loader, then re-run
```

**8. Document Coverage**
```bash
# Create README.md
cat > AlitaMyLoader/README.md << 'EOF'
# AlitaMyLoader Test Suite

## Test Coverage

- **Test files**: 3 (simple, empty, unicode)
- **Total configs**: 12
- **Parameters tested**: param1, param2, param3 (from allowed_to_override)
- **Edge cases**: Empty file, tiny content, extreme values

## Test Breakdown

| File | Configs | Purpose |
|------|---------|---------|
| my_simple.ext | 4 | Standard behavior with all param overrides |
| my_empty.ext | 2 | Edge case: empty file handling |
| my_unicode.ext | 3 | Multi-byte character support |

## Coverage Metrics

- allowed_to_override: 4 parameters
- Tested: 4/4 (100%)
- Untested: None
EOF

# Optional: Create COVERAGE_REPORT.json for tracking
```

**9. Verify 100% Pass Rate**
```bash
python run_tests.py run AlitaMyLoader

# Expected output:
# AlitaMyLoader
# --------------
#   [+] my_simple[0]      docs: N/N
#   [+] my_simple[1]      docs: N/N
#   ...
# Results: X/X passed  (0 failed, 0 errors)
```

### Minimal Test Template

```json
// AlitaMyLoader/input/my_minimal.json
{
    "file_path": "../files/my_minimal.ext",
    "configs": [
        {},                              // Must have: production defaults
        {"param1": value1}               // Optional: single override
    ]
}
```

```json
// AlitaMyLoader/output/my_minimal_config_0.json
[
  {
    "page_content": "expected content",
    "metadata": {
      "source": ".alita/tests/test_loaders/AlitaMyLoader/files/my_minimal.ext",
      "chunk_id": 1
    }
  }
]
```

---

## Contributing

When adding tests for a new loader:

**Prerequisites**:
1. Read `constants.py` - Identify `kwargs` and `allowed_to_override`
2. Read loader source - Understand metadata fields and behavior
3. Read this README - Follow established patterns

**Required Deliverables**:
1. Test data files (3+ files recommended: simple, empty, edge case)
2. Input JSON descriptors (exercise all `allowed_to_override` params)
3. Baseline JSON files (manually created by reasoning, not generated)
4. README.md documenting coverage (see AlitaTextLoader for template)
5. 100% pass rate: `python run_tests.py run <Loader>`

**Quality Standards**:
- ✅ All `allowed_to_override` parameters tested
- ✅ Edge cases included (empty, tiny, unicode)
- ✅ Baselines verified correct (not just generated)
- ✅ All metadata fields included in baselines
- ✅ `chunk_id` field present (even if loader doesn't set it)
- ✅ Relative paths in baselines
- ✅ Documentation explains test strategy

**Review Checklist**:
```bash
# Before submitting:
- [ ] All tests pass: python run_tests.py run <Loader>
- [ ] README.md documents coverage
- [ ] Baselines include all metadata fields
- [ ] Edge cases covered (empty, tiny, unicode)
- [ ] All allowed_to_override params tested
- [ ] No absolute paths in baselines
```

---

## Architecture

### Execution Flow

```
┌────────────────────────────────────────────────────────────┐
│ 1. Test Discovery (run_tests.py list)                     │
│    • Scan <Loader>/input/*.json files                     │
│    • Extract file_path and configs count                  │
└─────────────────┬──────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────┐
│ 2. Config Resolution (scripts/loader_test_runner.py)      │
│    • Load production defaults from constants.py           │
│    • Apply test config (filtered by allowed_to_override)  │
│    • Final kwargs = kwargs + test_config                  │
└─────────────────┬──────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────┐
│ 3. Loader Invocation (_load_documents_with_production_config) │
│    • Instantiate loader class with resolved kwargs        │
│    • Call load() method                                   │
│    • Capture List[Document] output                        │
└─────────────────┬──────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────┐
│ 4. Baseline Comparison (loader_test_utils.py)             │
│    • Load baseline JSON from <Loader>/output/             │
│    • Compare document count                               │
│    • Compare each document's metadata fields              │
│    • Special rules: path suffix matching for source fields│
└─────────────────┬──────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────┐
│ 5. Report Generation                                       │
│    • [+] Pass: all match                                  │
│    • [F] Fail: metadata mismatch (show exact diff)        │
│    • [E] Error: loader exception (show traceback)         │
│    • Save actual output to test_results/                  │
└────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Responsibility |
|-----------|------|----------------|
| **Test Runner** | `run_tests.py` | CLI entry point, test discovery, orchestration |
| **Execution Engine** | `loader_test_runner.py` | Config resolution, loader invocation, baseline loading |
| **Comparison Logic** | `loader_test_utils.py` | Document comparison, metadata field matching |
| **Loader Configs** | `constants.py` | Production defaults (`kwargs`), overridable params |
| **Loaders** | `document_loaders/*.py` | Document loading implementations under test |

### Configuration Resolution Details

**Three-Layer Model**:
1. **Function defaults** (loader `__init__`) - Lowest priority, rarely used
2. **Production defaults** (constants.py `kwargs`) - Used by platform
3. **User overrides** (test config) - Highest priority, filtered by `allowed_to_override`

**Example**:
```python
# constants.py
'.csv': {
    'kwargs': {'raw_content': True, 'cleanse': False},      # Layer 2
    'allowed_to_override': {'raw_content', 'cleanse', ...}  # Filter
}

# test config
test_config = {'raw_content': False, 'cleanse': True}

# Resolution:
final_kwargs = {
    'raw_content': False,  # From test_config (overridden)
    'cleanse': True        # From test_config (overridden)
}
# Note: Only params in allowed_to_override can be overridden
```

---

## Contact & Support

**Documentation**:
- SDK Docs: `docs/` directory
- Loader Source: `alita_sdk/runtime/langchain/document_loaders/`
- Test Framework Code: `alita_sdk/cli/loader_test_*.py`

**Issues**:
- Test failures: Check `test_results/` output and this troubleshooting section
- New loader tests: Follow "Creating New Tests" guide above
- Framework bugs: File issue with reproduction steps

**Examples**:
- AlitaTextLoader: `.alita/tests/test_loaders/AlitaTextLoader/` (8 files, 33 configs)
- AlitaCSVLoader: `.alita/tests/test_loaders/AlitaCSVLoader/` (Raw vs parsed modes)

---

**Framework Version**: 1.0 | **Last Updated**: March 2026 | **Maintainer**: Alita SDK Team
