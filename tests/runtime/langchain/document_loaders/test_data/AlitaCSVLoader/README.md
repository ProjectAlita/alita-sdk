# AlitaCSVLoader Test Suite

## Test Coverage

- **Test files**: 5
- **Total configs**: 12
- **Parameters tested**: `max_tokens` (from `DEFAULT_ALLOWED_BASE`)
- **Loader behavior**: With production default `raw_content=True`, returns entire CSV as single document

## Test Breakdown

| File | Configs | Purpose |
|------|---------|---------|
| `csv_simple.csv` | 2 | Basic CSV with headers and 3 data rows |
| `csv_empty.csv` | 2 | Empty CSV file (0 bytes) - validates empty file handling |
| `csv_unicode.csv` | 2 | Unicode characters (emoji, CJK, Arabic) - validates encoding |
| `csv_large.csv` | 4 | Large CSV with 30 employees (2.5KB) - validates large file handling with multiple max_tokens values |
| `csv_special.csv` | 2 | Special CSV characters (quoted fields, commas in values, newlines, escaped quotes) - validates edge case handling |

## Configuration Matrix

### csv_simple.csv
- **Config 0** (`{}`): Production defaults (encoding='utf-8', raw_content=True, cleanse=False, max_tokens=512)
- **Config 1** (`{"max_tokens": 1024}`): Override max_tokens to higher value

### csv_empty.csv
- **Config 0** (`{}`): Production defaults
- **Config 1** (`{"max_tokens": 1024}`): Override max_tokens

### csv_unicode.csv
- **Config 0** (`{}`): Production defaults with Unicode content
- **Config 1** (`{"max_tokens": 1024}`): Override max_tokens with Unicode

### csv_large.csv
- **Config 0** (`{}`): Production defaults (max_tokens=512) with 30-row employee data
- **Config 1** (`{"max_tokens": 50}`): Very small chunks to test boundary conditions
- **Config 2** (`{"max_tokens": 256}`): Medium chunk size
- **Config 3** (`{"max_tokens": 1024}`): Large chunk size

### csv_special.csv
- **Config 0** (`{}`): Production defaults with special CSV characters
- **Config 1** (`{"max_tokens": 256}`): Smaller chunks with special characters

## Coverage Metrics

### allowed_to_override Parameters

From `constants.py` - AlitaCSVLoader uses `DEFAULT_ALLOWED_BASE`:
```python
DEFAULT_ALLOWED_BASE = {'max_tokens': LOADER_MAX_TOKENS_DEFAULT}  # 512
```

**Coverage**: 1/1 parameters (100%)
- ✅ `max_tokens`: Tested with configs {} (default 512) and {"max_tokens": 1024}

### Production Defaults (kwargs)

From `constants.py`:
```python
'.csv': {
    'kwargs': {
        'encoding': 'utf-8',
        'raw_content': True,
        'cleanse': False
    }
}
```

All tests use these production defaults. The `raw_content=True` setting means the loader returns the entire CSV file content as a single document without row-by-row processing.

## Expected Behavior

### With raw_content=True (production default):
1. **Single Document**: Entire CSV content returned as one document
2. **Metadata fields**:
   - `source`: `<file_path>:1` (line number is always 1 since it's the whole file)
   - `table_source`: `<file_path>`
3. **Empty files**: Return single document with empty page_content `[{"page_content": "", "metadata": {...}}]`

**Note**: The CSV loader with `raw_content=True` does not set `chunk_id` since it doesn't perform chunking. The `chunk_id` field is added by the content parser in production, but not during direct loader testing.

## Running Tests

All commands are run from the project root with the virtualenv active.

```bash
# Run all CSV loader tests
pytest tests/runtime/langchain/document_loaders/test_alita_csv_loader.py -v

# Run a specific input file
pytest tests/runtime/langchain/document_loaders/test_alita_csv_loader.py -v -k "csv_simple"

# Run all document loader tests at once
pytest tests/runtime/langchain/document_loaders/ -v
```

### Filtering by Tag

Test files are tagged in `input/*.json`. Use `-m` to select subsets:

```bash
# All CSV loader tests
pytest -m "loader_csv" -v

# CSV tests exercising chunking
pytest -m "loader_csv and feature_chunking" -v

# Large-file / performance tests only
pytest -m "performance" -v

# Edge-case tests across all loaders
pytest -m "edge_empty_input or edge_encoding or edge_special_chars" -v
```

| Tag | pytest mark | Applied to |
|-----|-------------|------------|
| `loader:csv` | `loader_csv` | All CSV configs |
| `content:large` | `content_large` | csv_large configs |
| `feature:chunking` | `feature_chunking` | csv_simple, csv_large configs |
| `performance` | `performance` | csv_large configs |
| `edge:empty-input` | `edge_empty_input` | csv_empty configs |
| `edge:encoding` | `edge_encoding` | csv_unicode configs |
| `edge:special-chars` | `edge_special_chars` | csv_special configs |

## Test Data Details

### csv_simple.csv
```csv
name,age,city
Alice,30,New York
Bob,25,San Francisco
Charlie,35,Boston
```
**Size**: ~75 bytes  
**Test focus**: Basic functionality with headers and multiple rows

### csv_empty.csv
**Size**: 0 bytes  
**Test focus**: Empty file edge case

### csv_unicode.csv
**Size**: ~150 bytes  
**Test focus**: Unicode character handling (emoji, CJK, Arabic script)

### csv_large.csv
```csv
employee_id,first_name,last_name,email,department,position,salary,hire_date,city,country
1001,John,Smith,john.smith@company.com,Engineering,Senior Software Engineer,95000,2020-03-15,San Francisco,USA
... (30 total employee records)
```
**Size**: ~2.5KB  
**Test focus**: Large file handling with various max_tokens values (50, 256, 512, 1024)

### csv_special.csv
```csv
product_name,description,price,category,notes
"Laptop, Professional Edition","High-performance laptop with 16GB RAM, 512GB SSD...",1299.99,Electronics,"Popular choice...
"Coffee Maker ""Deluxe""",Programmable coffee maker...,89.95,Appliances,"Rated 4.5/5 stars
Customer favorite"
... (6 total products with special characters)
```
**Size**: ~850 bytes  
**Test focus**: CSV edge cases - quoted fields with commas, escaped quotes, embedded newlines

### csv_unicode.csv
```csv
name,emoji,language
Alice,😀,English
Bob,🎉,Español
Charlie,🌟,中文
مريم,🌙,العربية
```
**Size**: ~130 bytes  
**Test focus**: Multi-byte character encoding (UTF-8)

## Notes

- All test files use UTF-8 encoding
- Test data is deterministic (no timestamps, random values, or UUIDs)
- Baselines contain all metadata fields set by the loader
- Empty file returns `[]` (empty list of documents)
- Config overrides are filtered by `allowed_to_override` as per production behavior
