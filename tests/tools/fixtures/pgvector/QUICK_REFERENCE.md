# BaseIndexerToolkit Search Tests - Quick Reference

## Setup & Run (Quick Start)

```bash
# 1. Start pgvector with test data
./tests/tools/fixtures/pgvector/setup_pgvector.sh

# 2. Run all tests
pytest tests/tools/test_base_indexer_toolkit.py -v

# 3. Cleanup
./tests/tools/fixtures/pgvector/teardown_pgvector.sh
```

## Run Specific Tests

```bash
# Run single test case
pytest tests/tools/test_base_indexer_toolkit.py -v -k "filter_by_status"

# Run multiple related tests
pytest tests/tools/test_base_indexer_toolkit.py -v -k "filter_by"

# Run with search_test marker
pytest tests/tools/test_base_indexer_toolkit.py -v -m "search_test"

# Run with detailed output
pytest tests/tools/test_base_indexer_toolkit.py -v -s
```

## Manual pgvector Setup (Alternative)

```bash
# Start container
docker run --name pgvector-test \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=postgres \
  -p 5435:5432 \
  -d ankane/pgvector

# Wait for ready
docker exec pgvector-test pg_isready -U postgres

# Load test data
docker exec -i pgvector-test psql -U postgres -d postgres \
  < tests/tools/fixtures/pgvector/init_db.sql

# Verify
docker exec -i pgvector-test psql -U postgres -d postgres \
  -c "SELECT COUNT(*) FROM langchain_pg_embedding"
```

## Environment Variables

```bash
# Override connection string
export PGVECTOR_TEST_CONNECTION_STRING="postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres"

# Override AlitaClient settings (optional)
export DEPLOYMENT_URL="https://dev.elitea.ai"
export ALITA_API_KEY="your_api_key"
export PROJECT_ID="121"
```

## Test Data Overview

- **Collection 1:** `test_indexer_collection__test_idx` (10 Python docs)
- **Collection 2:** `test_indexer_collection__other_idx` (2 JS/Go docs)

**Metadata fields:**
- `status`: active, archived, draft, inactive
- `category`: documentation, tutorial, code, reference, urgent
- `priority`: 2-10
- `tags`: ["python", "testing", ...]
- `author`: test_author_1, test_author_2, test_author_3
- `created_at`: ISO date strings

## Test Scenarios Covered

1. **Basic Filters**
   - Empty filter (all docs)
   - Single field (`status`, `category`)
   - Multiple fields

2. **Advanced Filters**
   - Comparison operators (`$gte`, `$in`)
   - JSON string filters
   - Array field filters

3. **Edge Cases**
   - Empty index_name (search all)
   - Non-existent collection
   - Non-existent field
   - Complex nested filters

4. **Search Parameters**
   - Custom `cut_off` threshold
   - Custom `search_top` limit
   - Reranker configuration
   - Full-text search

## Troubleshooting

```bash
# Check if container is running
docker ps | grep pgvector-test

# View container logs
docker logs pgvector-test

# Test connection
psql "postgresql://postgres:yourpassword@localhost:5435/postgres" -c "SELECT 1"

# Restart container
docker restart pgvector-test

# Full reset
./tests/tools/fixtures/pgvector/teardown_pgvector.sh
./tests/tools/fixtures/pgvector/setup_pgvector.sh
```

## CI/CD

GitHub Actions workflow: `.github/workflows/test-base-indexer-toolkit.yml`

Triggers on:
- Manual dispatch
- Push to main/develop
- PRs affecting indexer toolkit

## Files Structure

```
tests/tools/
├── test_base_indexer_toolkit.py          # Main test file
└── fixtures/pgvector/
    ├── README.md                         # Detailed documentation
    ├── QUICK_REFERENCE.md                # This file
    ├── setup_pgvector.sh                 # Setup script
    ├── teardown_pgvector.sh              # Cleanup script
    └── init_db.sql                       # Test data (12 documents)

.github/workflows/
└── test-base-indexer-toolkit.yml         # CI/CD workflow
```

## Connection Strings

**Local development:**
```
postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres
```

**Inside Docker network:**
```
postgresql+psycopg://postgres:yourpassword@pgvector-test:5432/postgres
```

**From GitHub Actions:**
```
postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres
```
(Service container mapped to host)

## Extend Tests

Add to `FILTER_TEST_CASES` in [test_base_indexer_toolkit.py](../../test_base_indexer_toolkit.py):

```python
pytest.param(
    {
        "query": "python testing",
        "index_name": "test_idx",
        "filter": {"your_field": "value"},
        "expected_min_results": 0,
        "description": "Your description"
    },
    id="your_test_id"
),
```

Add documents to [init_db.sql](init_db.sql):

```sql
INSERT INTO langchain_pg_embedding (...)
VALUES (...);
```

Then reload: `./tests/tools/fixtures/pgvector/setup_pgvector.sh`
