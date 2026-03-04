# AlitaCSVLoader Test Suite

## Test Coverage

- **Test files**: 3
- **Total configs**: 6
- **Parameters tested**: `max_tokens` (from `DEFAULT_ALLOWED_BASE`)
- **Loader behavior**: With production default `raw_content=True`, returns entire CSV as single document

## Test Breakdown

| File | Configs | Purpose |
|------|---------|---------|
| `csv_simple.csv` | 2 | Basic CSV with headers and 3 data rows |
| `csv_empty.csv` | 2 | Empty CSV file (0 bytes) - validates empty file handling |
| `csv_unicode.csv` | 2 | Unicode characters (emoji, CJK, Arabic) - validates encoding |

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

```bash
# Run all CSV loader tests
python .alita/tests/test_loaders/run_tests.py run AlitaCSVLoader

# Run specific test input
python .alita/tests/test_loaders/run_tests.py run AlitaCSVLoader csv_simple

# Run single config (fast iteration)
python .alita/tests/test_loaders/run_tests.py run AlitaCSVLoader csv_simple -c 0

# List all tests
python .alita/tests/test_loaders/run_tests.py list
```

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
