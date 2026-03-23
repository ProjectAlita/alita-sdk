# BaseIndexerToolkit Search Tests - Implementation Summary

## 📋 Overview

Comprehensive data-driven test suite for `BaseIndexerToolkit.search_index()` with:
- ✅ **10 parametrized filter test cases** covering basic to advanced scenarios
- ✅ **Pre-populated pgvector database** (12 test documents, no need to run `index_data`)
- ✅ **Automated setup/teardown scripts** for pgvector container
- ✅ **GitHub Actions CI/CD workflow** with pgvector service
- ✅ **Complete documentation** with troubleshooting guides

## 📁 Files Created

```
tests/tools/
├── test_base_indexer_toolkit.py                    # Main test suite (369 lines)
│   └── 10+ test cases with parametrization
│
└── fixtures/pgvector/
    ├── README.md                                   # Full documentation (400+ lines)
    ├── QUICK_REFERENCE.md                          # Quick start guide
    ├── setup_pgvector.sh                           # Setup script (executable)
    ├── teardown_pgvector.sh                        # Cleanup script (executable)
    └── init_db.sql                                 # Test data SQL dump (250+ lines)

.github/workflows/
└── test-base-indexer-toolkit.yml                   # CI/CD workflow (200+ lines)
```

## 🎯 Test Cases Implemented

### Basic Filters (5 tests)
1. **empty_filter** - Search all documents (no filter)
2. **filter_by_status** - Single field: `{"status": "active"}`
3. **filter_by_category** - Single field: `{"category": "documentation"}`
4. **filter_multiple_fields** - Multiple: `{"status": "active", "category": "documentation"}`
5. **custom_search_params** - Custom `cut_off` and `search_top`

### Advanced Filters (5 tests)
6. **filter_with_operator** - Comparison: `{"priority": {"$gte": 5}}`
7. **filter_array_in** - Array field: `{"tags": {"$in": ["python", "testing"]}}`
8. **filter_json_string** - Filter as JSON string: `'{"status": "active"}'`
9. **filter_no_index_name** - Empty index_name (search all collections)
10. **filter_nonexistent_field** - Non-existent metadata field

### Edge Cases (3+ tests)
11. **test_search_index_invalid_collection** - Non-existent collection
12. **test_search_index_complex_filter** - Nested `$and`/`$or` filters
13. **test_search_index_with_reranker** - Reranker configuration
14. **test_search_index_with_full_text_search** - Full-text search params
15. **test_list_collections** - Verify test data loaded

## 🗄️ Test Database Structure

### Collections
- **test_indexer_collection__test_idx** (10 documents about Python testing)
- **test_indexer_collection__other_idx** (2 documents about JS/Go testing)

### Document Metadata Fields
- `status`: active | archived | draft | inactive
- `category`: documentation | tutorial | code | reference | urgent
- `priority`: 2-10 (integer)
- `tags`: Array of strings ["python", "testing", ...]
- `author`: test_author_1 | test_author_2 | test_author_3
- `created_at`: ISO date strings (2023-2024)

### Sample Documents
```json
{
  "document": "Comprehensive guide to Python testing frameworks...",
  "metadata": {
    "status": "active",
    "category": "documentation",
    "priority": 8,
    "tags": ["python", "testing", "pytest"],
    "author": "test_author_1",
    "created_at": "2024-01-15"
  }
}
```

## 🚀 Usage

### Quick Start
```bash
# 1. Start pgvector and load test data
./tests/tools/fixtures/pgvector/setup_pgvector.sh

# 2. Run all tests
pytest tests/tools/test_base_indexer_toolkit.py -v

# 3. Cleanup
./tests/tools/fixtures/pgvector/teardown_pgvector.sh
```

### Run Specific Tests
```bash
# Single test case
pytest tests/tools/test_base_indexer_toolkit.py -v -k "filter_by_status"

# Multiple tests
pytest tests/tools/test_base_indexer_toolkit.py -v -k "filter_by"

# With marker
pytest tests/tools/test_base_indexer_toolkit.py -v -m "search_test"

# With output
pytest tests/tools/test_base_indexer_toolkit.py -v -s
```

### Manual Docker Setup
```bash
# Start container
docker run --name pgvector-test \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=postgres \
  -p 5435:5432 \
  -d ankane/pgvector

# Load test data
docker exec -i pgvector-test psql -U postgres -d postgres \
  < tests/tools/fixtures/pgvector/init_db.sql

# Verify
docker exec -i pgvector-test psql -U postgres -d postgres \
  -c "SELECT COUNT(*) FROM langchain_pg_embedding"
# Expected: count = 12
```

## 🔧 Configuration

### Environment Variables
```bash
# Database connection (required for tests)
export PGVECTOR_TEST_CONNECTION_STRING="postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres"

# AlitaClient credentials (uses test defaults if not set)
export DEPLOYMENT_URL="https://dev.elitea.ai"
export ALITA_API_KEY="your_api_key"
export PROJECT_ID="121"

# Container configuration (for setup script)
export PGVECTOR_CONTAINER_NAME="pgvector-test"
export PGVECTOR_PORT="5435"
export PGVECTOR_TIMEOUT="30"
```

### Connection Strings by Environment
```bash
# Local development (default)
postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres

# Inside Docker network
postgresql+psycopg://postgres:yourpassword@pgvector-test:5432/postgres

# GitHub Actions (service container)
postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres
```

## 🤖 CI/CD Integration

**GitHub Actions Workflow:** `.github/workflows/test-base-indexer-toolkit.yml`

**Triggers:**
- Manual dispatch (with filters)
- Push to `main` or `develop`
- PRs affecting indexer toolkit files

**Features:**
- pgvector service container with health checks
- Automated test data loading
- JUnit XML + HTML reports
- Test results published to PR comments
- Artifact uploads (30-day retention)

**Manual Dispatch Options:**
- `test_filter` - Pytest `-k` expression
- `pytest_mark` - Pytest `-m` marker (default: `search_test`)
- `extra_pytest_args` - Additional args (default: `-v`)

## 📊 Test Coverage

### Filter Types
- [x] Empty filters
- [x] Single field filters
- [x] Multiple field filters (AND logic)
- [x] Comparison operators (`$gte`, `$lte`, `$in`)
- [x] Array field filters
- [x] JSON string filters
- [x] Complex nested filters (`$and`, `$or`)

### Search Parameters
- [x] Custom `cut_off` threshold
- [x] Custom `search_top` limit
- [x] Empty `index_name` (cross-collection)
- [x] Reranker configuration
- [x] Full-text search parameters

### Edge Cases
- [x] Non-existent collection
- [x] Non-existent metadata field
- [x] Invalid filter values
- [x] Collection listing

## 📝 Extending Tests

### Add New Test Case
Edit `tests/tools/test_base_indexer_toolkit.py`:

```python
pytest.param(
    {
        "query": "python testing",
        "index_name": "test_idx",
        "filter": {"your_custom_field": "value"},
        "expected_min_results": 0,
        "description": "Your test description"
    },
    id="your_test_id"
),
```

### Add Test Documents
Edit `tests/tools/fixtures/pgvector/init_db.sql`:

```sql
INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
VALUES (
    test_idx_id,
    (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
    'Your document content',
    '{"your_field": "value", "status": "active"}'::jsonb,
    'doc_custom_001'
);
```

Then reload: `./tests/tools/fixtures/pgvector/setup_pgvector.sh`

## 🐛 Troubleshooting

### Docker Not Running
```bash
# Error: Docker is not running
# ➜ Start Docker Desktop and retry
docker info
```

### Port Already in Use
```bash
# Error: port 5435 already allocated
# ➜ Use different port or stop conflicting service
lsof -i :5435
export PGVECTOR_PORT=5436
./tests/tools/fixtures/pgvector/setup_pgvector.sh
```

### Connection Refused
```bash
# Check container status
docker ps | grep pgvector-test

# View logs
docker logs pgvector-test

# Restart if needed
docker restart pgvector-test

# Test connection
psql "postgresql://postgres:yourpassword@localhost:5435/postgres" -c "SELECT 1"
```

### Tests Skip with "Failed to create indexer toolkit"
```bash
# Verify pgvector is running
docker ps | grep pgvector-test

# Verify test data loaded
docker exec -i pgvector-test psql -U postgres -d postgres \
  -c "SELECT COUNT(*) FROM langchain_pg_embedding"

# Check connection string
echo $PGVECTOR_TEST_CONNECTION_STRING
```

### No Test Results
The test data uses random embeddings, so search results may vary. Tests validate the search mechanism, not result quality. This is expected behavior.

## 🔗 References

### Documentation
- [BaseIndexerToolkit source](../../alita_sdk/tools/base_indexer_toolkit.py)
- [Full README](fixtures/pgvector/README.md) - Detailed documentation
- [Quick Reference](fixtures/pgvector/QUICK_REFERENCE.md) - Command cheat sheet

### External
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [LangChain PGVector](https://python.langchain.com/docs/integrations/vectorstores/pgvector)
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html)

## ✅ Validation Steps

To verify the implementation:

1. **Start pgvector** (requires Docker running):
   ```bash
   ./tests/tools/fixtures/pgvector/setup_pgvector.sh
   ```

2. **Run tests**:
   ```bash
   pytest tests/tools/test_base_indexer_toolkit.py -v
   ```

3. **Expected output**:
   - 15+ test cases executed
   - Most tests should pass or skip gracefully
   - Some tests may skip if optional features (reranker, full-text) not configured

4. **Verify test data**:
   ```bash
   docker exec -i pgvector-test psql -U postgres -d postgres \
     -c "SELECT name, (SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = uuid) FROM langchain_pg_collection"
   ```
   Expected: 2 collections (10 + 2 documents)

5. **Cleanup**:
   ```bash
   ./tests/tools/fixtures/pgvector/teardown_pgvector.sh
   ```

## 🎓 Key Features

1. **No index_data needed** - Pre-populated database via SQL dump
2. **Data-driven design** - Easy to add new test scenarios
3. **Realistic test data** - 12 documents with rich metadata
4. **Production-like setup** - pgvector with proper indexes
5. **CI/CD ready** - GitHub Actions workflow included
6. **Self-contained** - Scripts handle setup/teardown
7. **Well documented** - Multiple documentation levels (README, Quick Ref, SUMMARY)

## 📦 Next Steps

To run tests locally:
1. Ensure Docker is running
2. Execute setup script: `./tests/tools/fixtures/pgvector/setup_pgvector.sh`
3. Run tests: `pytest tests/tools/test_base_indexer_toolkit.py -v`
4. (Optional) Cleanup: `./tests/tools/fixtures/pgvector/teardown_pgvector.sh`

To run in CI/CD:
- Push changes to trigger workflow
- Or manually trigger via GitHub Actions UI

The implementation is complete and ready for use! 🚀
