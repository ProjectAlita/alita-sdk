# 1.1 File Loaders Unit Tests

**Source:** [1.1 File Loaders Unit Tests - Chunkers & Loaders Test Plan](https://kb.epam.com/spaces/EPMALTA/pages/2774628837/Chunkers+Loaders+%E2%80%94+Test+Plan#Chunkers%26Loaders%E2%80%94TestPlan-11-file-loaders-unit-tests1.1FileLoadersUnitTests)

**Extracted:** March 13, 2026

## Overview

Each test instantiates the loader directly, calls `.load()`, and asserts on the returned `List[Document]`.

---

## AlitaTextLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| TL01 | Load UTF-8 plain text | simple.txt | 1 Document, page_content = file text |
| TL02 | Load YAML file | config.yaml | page_content = raw YAML text |
| TL03 | Auto-detect Latin-1 encoding | latin1.txt | No UnicodeDecodeError, content loaded |
| TL04 | Empty file | empty.txt | 1 Document with empty page_content |
| TL05 | Groovy script | build.groovy | page_content = script content |

---

## AlitaMarkdownLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| ML01 | Standard markdown | readme.md | Full markdown text in page_content |
| ML02 | Markdown with H1/H2/H3 | with_headers.md | Headers present in content |
| ML03 | Markdown with code blocks | with_code_blocks.md | Fenced code blocks in page_content |
| ML04 | Large file > 100 KB | large.md | Loads without timeout or memory error |

---

## AlitaCSVLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| CSV01 | Standard CSV | data.csv | Documents produced; metadata has source |
| CSV02 | raw_content=True | data.csv | Single Document with full raw CSV text |
| CSV03 | Quoted fields with commas | quoted.csv | Correct field parsing, no split errors |
| CSV04 | Headers-only CSV | headers_only.csv | 0 or empty content Documents, no crash |
| CSV05 | Latin-1 encoded CSV | latin1.csv | Encoding handled, content loaded |

---

## AlitaExcelLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| EL01 | Single sheet .xlsx | single_sheet.xlsx | Documents from all rows |
| EL02 | Multi-sheet .xlsx | multi_sheet.xlsx | Documents from each sheet |
| EL03 | Legacy .xls | legacy.xls | Documents produced |
| EL04 | add_header_to_chunks=True | single_sheet.xlsx | Column headers prepended to each chunk |
| EL05 | sheet_name filter | multi_sheet.xlsx + sheet_name="Sheet2" | Only Sheet2 content |
| EL06 | Excel with merged cells | merged.xlsx | No crash, content extracted |

---

## AlitaPDFLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| PL01 | Text-only PDF | text_only.pdf | page_content = extracted text, metadata has page |
| PL02 | Multi-page PDF | multipage.pdf | One Document per page |
| PL03 | PDF with tables | with_tables.pdf | Table content in text |
| PL04 | Scanned PDF (image-only) | scanned.pdf | Empty or minimal text, no crash |
| PL05 | Password-protected PDF | protected.pdf | Error raised, not silent |

---

## AlitaDocxMammothLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| DL01 | Standard DOCX | simple.docx | page_content = extracted text |
| DL02 | DOCX with images (extract_images=True) | with_images.docx | Image content or alt text included |
| DL03 | DOCX with tables | with_tables.docx | Table rows in content |
| DL04 | Paged mode (mode=paged) | simple.docx | One Document per page |

---

## AlitaJSONLoader / AlitaJSONLinesLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| JL01 | Flat JSON object | flat.json | Content as structured text |
| JL02 | Nested JSON | nested.json | Nested structure preserved |
| JL03 | JSON array at root | array.json | Elements loaded, no crash |
| JL04 | JSONL (one object per line) | data.jsonl | One Document per line |
| JL05 | Malformed JSON | bad.json | Clear error, not silent |

---

## AlitaImageLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| IL01 | PNG without LLM | diagram.png | Document with metadata, no crash |
| IL02 | PNG with mocked LLM | diagram.png + mock LLM | page_content = LLM-returned description |
| IL03 | JPEG | photo.jpg | Correct MIME type image/jpeg |
| IL04 | SVG (converted format) | icon.svg | Loads without conversion error |
| IL05 | Corrupted image | corrupted.png | Graceful error, no unhandled exception |

---

## AlitaPowerPointLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| PPL01 | PPTX text slides | simple.pptx | Text from all slides |
| PPL02 | mode=paged | simple.pptx | One Document per slide |
| PPL03 | Legacy .ppt | legacy.ppt | Content extracted, no crash |
| PPL04 | pages_per_chunk=5 | large_deck.pptx | 5 slides merged per Document |

---

## AlitaDirectoryLoader

| ID | Description | Input | Assert |
|----|-------------|-------|--------|
| DIR01 | Mixed-type directory | ./mixed_dir/ | Each file routed to correct sub-loader |
| DIR02 | index_file_exts=['.md','.txt'] | ./mixed_dir/ | Only .md and .txt loaded |
| DIR03 | index_exclude_file_exts=['.pdf'] | ./mixed_dir/ | PDF files skipped |
| DIR04 | Recursive (recursive=True) | ./nested_dir/ | Subdirectory files loaded |
| DIR05 | Non-recursive (recursive=False) | ./nested_dir/ | Top-level files only |
| DIR06 | sample_size=5 on 20-file dir | ./large_dir/ | Exactly 5 Documents returned |
| DIR07 | Empty directory | ./empty_dir/ | Empty list, no crash |
| DIR08 | silent_errors=True with one bad file | ./bad_mixed_dir/ | Error logged, other files loaded |
| DIR09 | silent_errors=False with one bad file | ./bad_mixed_dir/ | Exception raised |

---

## Test Fixture Location

```
tests/fixtures/chunkers_loaders/
├── text/
│   ├── simple.txt
│   ├── latin1.txt
│   └── empty.txt
├── markdown/
│   ├── with_headers.md
│   ├── long_section.md
│   ├── tiny_sections.md
│   └── no_headers.md
├── csv/
│   ├── data.csv
│   ├── quoted.csv
│   └── headers_only.csv
├── excel/
│   ├── single_sheet.xlsx
│   ├── multi_sheet.xlsx
│   ├── merged.xlsx
│   └── legacy.xls
├── pdf/
│   ├── text_only.pdf
│   ├── multipage.pdf
│   ├── with_tables.pdf
│   └── scanned.pdf
├── docx/
│   ├── simple.docx
│   ├── with_images.docx
│   └── with_tables.docx
├── json/
│   ├── flat.json
│   ├── nested.json
│   ├── array.json
│   └── data.jsonl
├── code/
│   ├── sample.py
│   ├── module.js
│   ├── component.ts
│   ├── Service.java
│   └── handler.go
├── images/
│   ├── diagram.png
│   ├── photo.jpg
│   ├── icon.svg
│   └── corrupted.png
├── presentations/
│   ├── simple.pptx
│   ├── large_deck.pptx
│   └── legacy.ppt
└── mixed_dir/
    ├── readme.md
    ├── data.csv
    ├── script.py
    ├── config.json
    └── image.png
```

---

## Test Execution

**Phase 1 - Loader unit tests**
- **When:** Every PR
- **External dependencies:** None
- **Scope:** Each loader tested in total isolation. No vector DB, no embeddings, no network calls.
- **Input:** Raw file content / string
- **Output:** List[Document] or chunk generator
- **Fixtures:** All tests use local fixture files from `tests/fixtures/chunkers_loaders/`

---

# Test Coverage Analysis

**Analysis Date:** March 13, 2026  
**Test Location:** `.alita/tests/test_loaders/`

## Executive Summary

| Metric | Value |
|--------|-------|
| **Loaders Covered** | 5 / 10 (50%) |
| **Core Requirements Met** | ~18 / 52 (35%) |
| **Test Input Files Created** | 31 files |
| **Loaders Complete** | 4 / 10 (AlitaTextLoader, AlitaMarkdownLoader, AlitaCSVLoader, JSON loaders) |
| **Loaders Missing Entirely** | 6 / 10 (Excel, PDF, DOCX, Image, PowerPoint, Directory) |

---

## Detailed Coverage by Loader

### ✅ AlitaTextLoader — 100% Complete (5/5)

| Test ID | Requirement | Status | Implementation |
|---------|-------------|--------|----------------|
| TL01 | Load UTF-8 plain text | ✅ | `text_simple.json` |
| TL02 | Load YAML file | ✅ | `text_yaml.json` |
| TL03 | Auto-detect Latin-1 encoding | ✅ | `text_latin1.json` |
| TL04 | Empty file | ✅ | `text_empty.json` |
| TL05 | Groovy script | ✅ | `text_groovy.json` |

**Extra Coverage:** `text_large.json`, `text_markdown.json`, `text_unicode.json`

**Files:** 8 test cases covering edge cases beyond requirements

---

### ✅ AlitaMarkdownLoader — 100% Complete (4/4)

| Test ID | Requirement | Status | Implementation |
|---------|-------------|--------|----------------|
| ML01 | Standard markdown | ✅ | `markdown_simple.json` |
| ML02 | Markdown with H1/H2/H3 | ✅ | `markdown_headers.json` |
| ML03 | Markdown with code blocks | ✅ | `markdown_code_blocks.json` |
| ML04 | Large file > 100 KB | ✅ | `markdown_large.json` |

**Extra Coverage:** `markdown_empty.json`, `markdown_nested.json`

**Files:** 6 test cases with additional edge case coverage

---

### ⚠️ AlitaCSVLoader — 80-90% Complete (4-5/5)

| Test ID | Requirement | Status | Implementation |
|---------|-------------|--------|----------------|
| CSV01 | Standard CSV | ✅ | `csv_simple.json` |
| CSV02 | raw_content=True | ✅ | `csv_raw_content.json` |
| CSV03 | Quoted fields with commas | ✅ | `csv_special.json` |
| CSV04 | Headers-only CSV | ⚠️ | `csv_empty.json` (verify) |
| CSV05 | Latin-1 encoded CSV | ✅ | `csv_latin1.json` |

**Extra Coverage:** `csv_large.json`, `csv_unicode.json`

**Files:** 7 test cases

**Action Required:** Verify `csv_empty.csv` tests headers-only scenario (not just empty file)

---

### ⚠️ AlitaJSONLoader / AlitaJSONLinesLoader — 80% Complete (4/5)

| Test ID | Requirement | Status | Implementation |
|---------|-------------|--------|----------------|
| JL01 | Flat JSON object | ✅ | `json_simple.json` |
| JL02 | Nested JSON | ✅ | `json_nested.json` |
| JL03 | JSON array at root | ✅ | `json_array.json` |
| JL04 | JSONL (one object per line) | ✅ | `jsonl_simple.json` |
| JL05 | Malformed JSON | ❌ | **MISSING** |

**Extra Coverage:** `json_empty.json`, `json_large.json`, `jsonl_empty.json`, `jsonl_large.json`, `jsonl_nested.json`, `jsonl_unicode.json`

**Files:** 10 test cases (5 JSON + 5 JSONL)

**Action Required:** Add malformed/invalid JSON test case

---

### ❌ AlitaExcelLoader — 0% Complete (0/6)

| Test ID | Requirement | Status |
|---------|-------------|--------|
| EL01 | Single sheet .xlsx | ❌ MISSING |
| EL02 | Multi-sheet .xlsx | ❌ MISSING |
| EL03 | Legacy .xls | ❌ MISSING |
| EL04 | add_header_to_chunks=True | ❌ MISSING |
| EL05 | sheet_name filter | ❌ MISSING |
| EL06 | Excel with merged cells | ❌ MISSING |

**Required Files:**
- `single_sheet.xlsx`
- `multi_sheet.xlsx`
- `legacy.xls`
- `merged.xlsx`

---

### ❌ AlitaPDFLoader — 0% Complete (0/5)

| Test ID | Requirement | Status |
|---------|-------------|--------|
| PL01 | Text-only PDF | ❌ MISSING |
| PL02 | Multi-page PDF | ❌ MISSING |
| PL03 | PDF with tables | ❌ MISSING |
| PL04 | Scanned PDF (image-only) | ❌ MISSING |
| PL05 | Password-protected PDF | ❌ MISSING |

**Required Files:**
- `text_only.pdf`
- `multipage.pdf`
- `with_tables.pdf`
- `scanned.pdf`
- `protected.pdf`

---

### ❌ AlitaDocxMammothLoader — 0% Complete (0/4)

| Test ID | Requirement | Status |
|---------|-------------|--------|
| DL01 | Standard DOCX | ❌ MISSING |
| DL02 | DOCX with images (extract_images=True) | ❌ MISSING |
| DL03 | DOCX with tables | ❌ MISSING |
| DL04 | Paged mode (mode=paged) | ❌ MISSING |

**Required Files:**
- `simple.docx`
- `with_images.docx`
- `with_tables.docx`

---

### ❌ AlitaImageLoader — 0% Complete (0/5)

| Test ID | Requirement | Status |
|---------|-------------|--------|
| IL01 | PNG without LLM | ❌ MISSING |
| IL02 | PNG with mocked LLM | ❌ MISSING |
| IL03 | JPEG | ❌ MISSING |
| IL04 | SVG (converted format) | ❌ MISSING |
| IL05 | Corrupted image | ❌ MISSING |

**Required Files:**
- `diagram.png`
- `photo.jpg`
- `icon.svg`
- `corrupted.png`

---

### ❌ AlitaPowerPointLoader — 0% Complete (0/4)

| Test ID | Requirement | Status |
|---------|-------------|--------|
| PPL01 | PPTX text slides | ❌ MISSING |
| PPL02 | mode=paged | ❌ MISSING |
| PPL03 | Legacy .ppt | ❌ MISSING |
| PPL04 | pages_per_chunk=5 | ❌ MISSING |

**Required Files:**
- `simple.pptx`
- `legacy.ppt`
- `large_deck.pptx`

---

### ❌ AlitaDirectoryLoader — 0% Complete (0/9)

| Test ID | Requirement | Status |
|---------|-------------|--------|
| DIR01 | Mixed-type directory | ❌ MISSING |
| DIR02 | index_file_exts=['.md','.txt'] | ❌ MISSING |
| DIR03 | index_exclude_file_exts=['.pdf'] | ❌ MISSING |
| DIR04 | Recursive (recursive=True) | ❌ MISSING |
| DIR05 | Non-recursive (recursive=False) | ❌ MISSING |
| DIR06 | sample_size=5 on 20-file dir | ❌ MISSING |
| DIR07 | Empty directory | ❌ MISSING |
| DIR08 | silent_errors=True with one bad file | ❌ MISSING |
| DIR09 | silent_errors=False with one bad file | ❌ MISSING |

**Required Setup:**
- `mixed_dir/` with various file types
- `nested_dir/` with subdirectories
- `large_dir/` with 20+ files
- `empty_dir/`
- `bad_mixed_dir/` with one corrupted file

---

## Priority TODO List

### 🔴 Priority 0 - Critical (Required for MVP)

1. **AlitaExcelLoader** (6 tests) - High business value, commonly used format
2. **AlitaPDFLoader** (5 tests) - Essential document format
3. **AlitaJSONLoader** - Add malformed JSON test (JL05)
4. **AlitaCSVLoader** - Verify CSV04 headers-only scenario

### 🟡 Priority 1 - High (Core Functionality)

5. **AlitaDocxMammothLoader** (4 tests) - Common document format
6. **AlitaDirectoryLoader** (9 tests) - Complex but essential for bulk operations
   - Start with DIR01 (mixed-type), DIR04 (recursive), DIR07 (empty dir)

### 🟢 Priority 2 - Medium (Nice to Have)

7. **AlitaImageLoader** (5 tests) - Special handling, LLM integration needed
8. **AlitaPowerPointLoader** (4 tests) - Less critical format

---

## Implementation Roadmap

### Phase 1: Complete P0 Tests (18 tests)
**Estimated Effort:** 3-4 days

- [ ] Create AlitaExcelLoader directory structure
- [ ] Generate 4 Excel test files (single, multi-sheet, legacy, merged)
- [ ] Write 6 input JSON configurations covering all EL01-EL06
- [ ] Create AlitaPDFLoader directory structure
- [ ] Generate 5 PDF test files (text-only, multi-page, tables, scanned, protected)
- [ ] Write 5 input JSON configurations covering PL01-PL05
- [ ] Add malformed JSON test for JL05
- [ ] Verify/fix CSV04 headers-only test

### Phase 2: Complete P1 Tests (13 tests)
**Estimated Effort:** 2-3 days

- [ ] Create AlitaDocxMammothLoader directory
- [ ] Generate 3 DOCX files with various features
- [ ] Write 4 configurations for DL01-DL04
- [ ] Create AlitaDirectoryLoader test structure
- [ ] Set up test directory hierarchies (mixed, nested, large, empty, corrupted)
- [ ] Write 9 configurations for DIR01-DIR09

### Phase 3: Complete P2 Tests (9 tests)
**Estimated Effort:** 2 days

- [ ] Create AlitaImageLoader with LLM mocking
- [ ] Generate/collect 4 image files + 1 corrupted
- [ ] Write 5 configurations for IL01-IL05
- [ ] Create AlitaPowerPointLoader directory
- [ ] Generate 3 PowerPoint files
- [ ] Write 4 configurations for PPL01-PPL04

**Total Remaining:** 40 test cases across 6 loaders  
**Total Estimated Effort:** 7-9 days

---

## Test File Inventory - Current State

### Implemented (31 test input files)

```
.alita/tests/test_loaders/
├── AlitaTextLoader/          ✅ 8 tests (5 required + 3 extra)
│   ├── input/
│   │   ├── text_simple.json
│   │   ├── text_yaml.json
│   │   ├── text_latin1.json
│   │   ├── text_empty.json
│   │   ├── text_groovy.json
│   │   ├── text_large.json
│   │   ├── text_markdown.json
│   │   └── text_unicode.json
│   └── files/
│       └── [9 corresponding files]
│
├── AlitaMarkdownLoader/      ✅ 6 tests (4 required + 2 extra)
│   ├── input/
│   │   ├── markdown_simple.json
│   │   ├── markdown_headers.json
│   │   ├── markdown_code_blocks.json
│   │   ├── markdown_large.json
│   │   ├── markdown_empty.json
│   │   └── markdown_nested.json
│   └── files/
│       └── [6 corresponding files]
│
├── AlitaCSVLoader/           ⚠️  7 tests (4-5 required + 2 extra)
│   ├── input/
│   │   ├── csv_simple.json
│   │   ├── csv_raw_content.json
│   │   ├── csv_special.json
│   │   ├── csv_empty.json
│   │   ├── csv_latin1.json
│   │   ├── csv_large.json
│   │   └── csv_unicode.json
│   └── files/
│       └── [6 corresponding files]
│
├── AlitaJSONLoader/          ⚠️  5 tests (4 required + 1 extra)
│   ├── input/
│   │   ├── json_simple.json
│   │   ├── json_nested.json
│   │   ├── json_array.json
│   │   ├── json_empty.json
│   │   └── json_large.json
│   └── files/
│       └── [5 corresponding files]
│
└── AlitaJSONLinesLoader/     ⚠️  5 tests (extra coverage)
    ├── input/
    │   ├── jsonl_simple.json
    │   ├── jsonl_empty.json
    │   ├── jsonl_large.json
    │   ├── jsonl_nested.json
    │   └── jsonl_unicode.json
    └── files/
        └── [5 corresponding files]
```

---

## Summary Statistics

| Category | Count |
|----------|-------|
| **Total Expected Test Cases** | 52 |
| **Core Requirements Met** | ~18 (35%) |
| **Core Requirements Missing** | ~34 (65%) |
| **Test Input Files Created** | 31 |
| **Test Data Files Created** | 29 |
| **Loaders 100% Complete** | 2 (TextLoader, MarkdownLoader) |
| **Loaders 80-99% Complete** | 2 (CSVLoader, JSON loaders) |
| **Loaders Not Started** | 6 |
| **Estimated Days to 100%** | 7-9 days |

---

## Next Actions

1. **Immediate:** Fix CSVLoader CSV04 and add JSON malformed test (JL05)
2. **Week 1:** Implement AlitaExcelLoader and AlitaPDFLoader (P0)
3. **Week 2:** Implement AlitaDocxMammothLoader and AlitaDirectoryLoader (P1)
4. **Week 3:** Implement AlitaImageLoader and AlitaPowerPointLoader (P2)
5. **Continuous:** Generate baselines and validate against production behavior
