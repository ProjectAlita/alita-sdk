# BaseIndexerToolkit Search Tests

This directory contains comprehensive tests for the `BaseIndexerToolkit.search_index()` method with various filter configurations.

## Overview

The test suite validates search functionality with:
- **Data-driven tests**: Parametrized test cases for different filter scenarios
- **pgvector database**: Pre-populated test data (no need to run `index_data`)
- **Multiple filter types**: Empty filters, single/multiple fields, comparison operators, JSON strings
- **Edge cases**: Non-existent collections, complex nested filters, rerankers

## Quick Start

### 1. Setup pgvector Database

```bash
# Start pgvector container and load test data
./tests/tools/fixtures/pgvector/setup_pgvector.sh
```

This will:
- Start a Docker container named `pgvector-test` on port `5435`
- Install pgvector extension
- Create test collections with 12 pre-indexed documents
- Load metadata with various filterable fields

### 2. Run Tests

```bash
# Run all search tests
pytest tests/tools/test_base_indexer_toolkit.py -v

# Run specific test by ID
pytest tests/tools/test_base_indexer_toolkit.py -v -k "filter_by_status"

# Run with search_test marker
pytest tests/tools/test_base_indexer_toolkit.py -v -m "search_test"

# Run with output
pytest tests/tools/test_base_indexer_toolkit.py -v -s
```

### 3. Cleanup

```bash
# Stop and remove pgvector container
./tests/tools/fixtures/pgvector/teardown_pgvector.sh
```

## Test Data Structure

The test database contains two collections:

### Collection 1: `test_indexer_collection__test_idx`
10 documents about Python testing with metadata:
- **status**: `active`, `archived`, `draft`, `inactive`
- **category**: `documentation`, `tutorial`, `code`, `reference`, `urgent`
- **priority**: 2-10 (integer)
- **tags**: Arrays like `["python", "testing", "pytest"]`
- **author**: `test_author_1`, `test_author_2`, `test_author_3`
- **created_at**: Date strings

### Collection 2: `test_indexer_collection__other_idx`
2 documents about JavaScript and Go testing (for cross-collection tests)

### Example Document Metadata

```json
{
  "status": "active",
  "category": "documentation",
  "priority": 8,
  "tags": ["python", "testing", "pytest"],
  "author": "test_author_1",
  "created_at": "2024-01-15"
}
```

## Test Cases

### Basic Filters
- `empty_filter`: No filter (search all documents)
- `filter_by_status`: Single field filter `{"status": "active"}`
- `filter_by_category`: Single field filter `{"category": "documentation"}`
- `filter_multiple_fields`: Multiple fields `{"status": "active", "category": "documentation"}`

### Advanced Filters
- `filter_with_operator`: Comparison operator `{"priority": {"$gte": 5}}`
- `filter_array_in`: Array field `{"tags": {"$in": ["python", "testing"]}}`
- `filter_json_string`: Filter as JSON string `'{"status": "active"}'`

### Edge Cases
- `filter_no_index_name`: Empty index_name (search across all collections)
- `custom_search_params`: Custom `cut_off` and `search_top`
- `filter_nonexistent_field`: Non-existent metadata field
- `test_search_index_invalid_collection`: Non-existent collection
- `test_search_index_complex_filter`: Nested `$and`/`$or` filters

### Optional Features
- `test_search_index_with_reranker`: Reranker configuration
- `test_search_index_with_full_text_search`: Full-text search parameters

## Configuration

### Environment Variables

```bash
# Database connection (default shown)
export PGVECTOR_TEST_CONNECTION_STRING="postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres"

# AlitaClient configuration (optional, uses test defaults)
export DEPLOYMENT_URL="https://dev.elitea.ai"
export ALITA_API_KEY="your_api_key"
export PROJECT_ID="121"

# Container configuration (for setup script)
export PGVECTOR_CONTAINER_NAME="pgvector-test"
export PGVECTOR_PORT="5435"
export PGVECTOR_TIMEOUT="30"
```

### Docker Connection String

When running tests inside Docker (e.g., in CI/CD), adjust the hostname:

```bash
# Local development
postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres

# Inside Docker network
postgresql+psycopg://postgres:yourpassword@pgvector-test:5432/postgres
```

## Manual Database Operations

### Connect to Database

```bash
# Using Docker exec
docker exec -it pgvector-test psql -U postgres -d postgres

# Using local psql
psql "postgresql://postgres:yourpassword@localhost:5435/postgres"
```

### Verify Test Data

```sql
-- List collections
SELECT name, cmetadata FROM langchain_pg_collection;

-- Count documents per collection
SELECT 
    c.name AS collection_name,
    COUNT(e.id) AS document_count
FROM langchain_pg_collection c
LEFT JOIN langchain_pg_embedding e ON c.uuid = e.collection_id
GROUP BY c.name;

-- View sample documents with metadata
SELECT 
    custom_id,
    substring(document, 1, 80) AS doc_preview,
    cmetadata->>'status' AS status,
    cmetadata->>'category' AS category,
    cmetadata->>'priority' AS priority
FROM langchain_pg_embedding
WHERE collection_id = (
    SELECT uuid FROM langchain_pg_collection 
    WHERE name = 'test_indexer_collection__test_idx'
)
ORDER BY custom_id;
```

### Reload Test Data

```bash
# Reload from SQL dump
docker exec -i pgvector-test psql -U postgres -d postgres \
  < tests/tools/fixtures/pgvector/init_db.sql
```

## Troubleshooting

### Container Won't Start

```bash
# Check if port 5435 is already in use
lsof -i :5435

# Use different port
export PGVECTOR_PORT=5436
./tests/tools/fixtures/pgvector/setup_pgvector.sh
```

### Connection Refused

```bash
# Check container status
docker ps -a | grep pgvector-test

# Check container logs
docker logs pgvector-test

# Restart container
docker restart pgvector-test

# Wait for PostgreSQL to be ready
docker exec pgvector-test pg_isready -U postgres
```

### Tests Skip with "Failed to create indexer toolkit"

This usually means pgvector is not running or connection string is incorrect.

```bash
# Verify container is running
docker ps | grep pgvector-test

# Test connection
psql "postgresql://postgres:yourpassword@localhost:5435/postgres" -c "SELECT 1"

# Check connection string in test output
pytest tests/tools/test_base_indexer_toolkit.py -v -s
```

### No Results in Tests

The test data uses random embeddings. Searches may return few or no results.This is expected and tests validate the search mechanism, not the quality of results.

```bash
# Verify data is loaded
docker exec -i pgvector-test psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM langchain_pg_embedding"

# Should show: count = 12
```

## CI/CD Integration

See [.github/workflows/execute-indexing-tests-on-demand.yml](../../../.github/workflows/execute-indexing-tests-on-demand.yml) for GitHub Actions workflow that:
1. Starts pgvector service container
2. Loads test data
3. Runs test suite
4. Publishes results

### GitHub Actions Example

```yaml
services:
  pgvector-test:
    image: ankane/pgvector
    env:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: yourpassword
      POSTGRES_DB: postgres
    ports:
      - 5435:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5

steps:
  - name: Load test data
    run: |
      psql "postgresql://postgres:yourpassword@localhost:5435/postgres" \
        -f tests/tools/fixtures/pgvector/init_db.sql
  
  - name: Run tests
    run: pytest tests/tools/test_base_indexer_toolkit.py -v
```

## Extending Tests

### Add New Filter Test Case

Edit [test_base_indexer_toolkit.py](test_base_indexer_toolkit.py) and add to `FILTER_TEST_CASES`:

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

### Add New Test Documents

Edit [init_db.sql](fixtures/pgvector/init_db.sql) and add INSERT statements with your custom metadata:

```sql
INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
VALUES (
    test_idx_id,
    (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
    'Your document content here',
    '{"your_field": "your_value", "status": "active"}'::jsonb,
    'doc_custom_001'
);
```

Then reload the database:

```bash
./tests/tools/fixtures/pgvector/setup_pgvector.sh
```

## Files

```
tests/tools/
├── test_base_indexer_toolkit.py          # Main test file
└── fixtures/pgvector/
    ├── README.md                         # This file
    ├── setup_pgvector.sh                 # Setup script
    ├── teardown_pgvector.sh              # Cleanup script
    └── init_db.sql                       # Test data SQL dump
```

## References

- [BaseIndexerToolkit source](../../alita_sdk/tools/base_indexer_toolkit.py)
- [pgvector documentation](https://github.com/pgvector/pgvector)
- [LangChain PGVector](https://python.langchain.com/docs/integrations/vectorstores/pgvector)
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html)
