"""
Pytest tests for BaseIndexerToolkit search_index functionality.

This test suite validates the search_index tool with various filter configurations
using a pre-populated pgvector database.

Prerequisites:
  - pgvector running with test data
  - Valid Alita credentials in environment

Setup:
  1. Set environment variables:
       export DEPLOYMENT_URL=https://dev.elitea.ai
       export ALITA_API_KEY=your_api_key
       export PROJECT_ID=your_project_id
       export DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS=gpt-4o-mini  # optional
  
  2. Start pgvector and load test data:
       ./tests/tools/fixtures/pgvector/setup_pgvector.sh
  
  3. Run tests:
       pytest tests/tools/test_base_indexer_toolkit.py -v

Skip behavior:
  - Tests will skip if credentials are not set (no default values)
  - Tests will skip if pgvector is not running or has no test data
  - Tests will skip if AlitaClient initialization fails

Run:
  pytest tests/tools/test_base_indexer_toolkit.py -v
  pytest tests/tools/test_base_indexer_toolkit.py -v -k "filter_by_status"
  pytest tests/tools/test_base_indexer_toolkit.py -v -m "search_test"
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from pydantic import SecretStr

from alita_sdk.runtime.clients.client import AlitaClient
from alita_sdk.tools.base_indexer_toolkit import BaseIndexerToolkit

# Test configuration
PGVECTOR_CONNECTION_STRING = os.getenv(
    "PGVECTOR_TEST_CONNECTION_STRING",
    "postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres"
)
TEST_COLLECTION_NAME = "test_indexer_collection"

# Required environment variables (no defaults - must be explicitly set)
DEPLOYMENT_URL = os.getenv("DEPLOYMENT_URL")
API_KEY = os.getenv("ALITA_API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS", "gpt-4o-mini")


def _check_credentials_available() -> bool:
    """Check if all required credentials are available."""
    return all([DEPLOYMENT_URL, PROJECT_ID, API_KEY])


@pytest.fixture(scope="module")
def alita_client():
    """Create AlitaClient instance for tests.
    
    Requires environment variables:
    - DEPLOYMENT_URL: Alita deployment URL
    - PROJECT_ID: Project ID  
    - ALITA_API_KEY: API key
    """
    if not _check_credentials_available():
        pytest.skip(
            "Skipping test: Missing required credentials. "
            "Set DEPLOYMENT_URL, PROJECT_ID, and ALITA_API_KEY environment variables."
        )
    
    try:
        client = AlitaClient(
            base_url=DEPLOYMENT_URL,
            project_id=int(PROJECT_ID),
            auth_token=API_KEY,
        )
        return client
    except Exception as e:
        pytest.skip(f"Failed to create AlitaClient: {e}")


@pytest.fixture(scope="module")
def llm_model(alita_client):
    """Create LLM instance for tests."""
    try:
        return alita_client.get_llm(
            DEFAULT_LLM_MODEL,
            model_config={"max_tokens": 1024, "top_p": 0.7, "temperature": 0.7}
        )
    except Exception as e:
        pytest.skip(f"Failed to create LLM model: {e}")


@pytest.fixture(scope="module")
def indexer_toolkit(alita_client, llm_model):
    """
    Create BaseIndexerToolkit instance with pgvector connection.
    
    Note: BaseIndexerToolkit is abstract, so we use a minimal concrete implementation.
    """
    class TestIndexerToolkit(BaseIndexerToolkit):
        """Minimal concrete implementation for testing."""
        
        doctype: str = "test_document"
        
        def _get_indexed_data(self, index_name: str):
            """Mock implementation - not used in search_index tests."""
            return {}
        
        def key_fn(self, document):
            """Mock implementation - not used in search_index tests."""
            return document.metadata.get('id', '')
        
        def compare_fn(self, document, idx):
            """Mock implementation - not used in search_index tests."""
            return True
        
        def remove_ids_fn(self, idx_data, key: str):
            """Mock implementation - not used in search_index tests."""
            pass
    
    try:
        toolkit = TestIndexerToolkit(
            connection_string=SecretStr(PGVECTOR_CONNECTION_STRING),
            collection_schema=TEST_COLLECTION_NAME,
            vectorstore_type="PGVector",
            embedding_model='text-embedding-ada-002',
            llm=llm_model,
            alita=alita_client,
        )
        
        # Verify pgvector has test data loaded
        try:
            collections = toolkit.list_collections()
            if not collections or collections == "No indexed collections":
                pytest.skip(
                    "Skipping test: No test data found in pgvector. "
                    "Run: ./tests/tools/fixtures/pgvector/setup_pgvector.sh"
                )
        except Exception:
            # If list_collections fails, still allow tests to run (they might handle missing collections)
            pass
        
        return toolkit
    except Exception as e:
        pytest.skip(f"Failed to create indexer toolkit: {e}. Ensure pgvector is running.")


# Test data: various filter scenarios
FILTER_TEST_CASES = [
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": {},
            "expected_min_results": 1,
            "description": "Empty filter - search across all documents",
            "validate_metadata": {}  # No specific metadata to validate
        },
        id="empty_filter"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": {"status": "active"},
            "expected_min_results": 1,
            "description": "Filter by status=active",
            "validate_metadata": {"status": "active"}
        },
        id="filter_by_status"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": {"category": "documentation"},
            "expected_min_results": 1,
            "description": "Filter by category=documentation",
            "validate_metadata": {"category": "documentation"}
        },
        id="filter_by_category"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": {"status": "active", "category": "documentation"},
            "expected_min_results": 1,
            "description": "Multiple filters: status AND category",
            "validate_metadata": {"status": "active", "category": "documentation"}
        },
        id="filter_multiple_fields"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": {"priority": {"$gte": 5}},
            "expected_min_results": 1,
            "description": "Filter with comparison operator (priority >= 5)",
            "validate_metadata": {"priority": {"$gte": 5}}  # Special validation for operators
        },
        id="filter_with_operator"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": {"tags": {"$in": ["python", "testing"]}},
            "expected_min_results": 1,
            "description": "Filter with $in operator for array field",
            "validate_metadata": {"tags": {"$in": ["python", "testing"]}}  # Special validation for $in
        },
        id="filter_array_in"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": '{"status": "active"}',  # JSON string format
            "expected_min_results": 1,
            "description": "Filter as JSON string",
            "validate_metadata": {"status": "active"}
        },
        id="filter_json_string"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "",  # Empty index_name searches all collections
            "filter": {"status": "active"},
            "expected_min_results": 1,
            "description": "Filter with empty index_name (search all)",
            "validate_metadata": {"status": "active"}
        },
        id="filter_no_index_name"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": {},
            "cut_off": 0.5,
            "search_top": 5,
            "expected_min_results": 1,
            "description": "Search with custom cut_off and search_top",
            "validate_metadata": {}
        },
        id="custom_search_params"
    ),
    pytest.param(
        {
            "query": "python testing",
            "index_name": "test_idx",
            "filter": {"nonexistent_field": "value"},
            "expected_min_results": 0,
            "description": "Filter with non-existent field (should return no results)",
            "validate_metadata": {}
        },
        id="filter_nonexistent_field"
    ),
]


@pytest.mark.search_test
@pytest.mark.parametrize("test_case", FILTER_TEST_CASES)
def test_search_index_with_filters(indexer_toolkit, test_case):
    """
    Test search_index with various filter configurations.
    
    This is a data-driven test that validates:
    - Basic filtering (single field, multiple fields)
    - Comparison operators ($gte, $in, etc.)
    - JSON string filters
    - Empty filters and index names
    - Custom search parameters
    - Metadata contains filtered fields with correct values
    """
    query = test_case["query"]
    index_name = test_case["index_name"]
    filter_param = test_case["filter"]
    cut_off = test_case.get("cut_off", 0.1)
    search_top = test_case.get("search_top", 10)
    expected_min_results = test_case["expected_min_results"]
    description = test_case["description"]
    validate_metadata = test_case.get("validate_metadata", {})
    
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"Query: {query}")
    print(f"Index: {index_name if index_name else '<all>'}")
    print(f"Filter: {json.dumps(filter_param, indent=2)}")
    print(f"Expected min results: {expected_min_results}")
    print(f"{'='*70}")
    
    try:
        # Execute search
        result = indexer_toolkit.search_index(
            query=query,
            index_name=index_name,
            filter=filter_param,
            cut_off=cut_off,
            search_top=search_top,
        )
        
        print(f"Result type: {type(result)}")
        
        # Validate result format
        if isinstance(result, str):
            # Result could be error message or "No documents found..."
            if "No documents found" in result or "not found" in result.lower():
                # This is acceptable only if expected_min_results is 0
                assert expected_min_results == 0, \
                    f"Expected at least {expected_min_results} results but got none. Message: {result}"
                print(f"✓ Test passed: {description} (no results expected)")
                return
            else:
                # Try to parse as JSON
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, list):
                        result = parsed
                    else:
                        pytest.fail(f"Unexpected result format: {type(parsed)}")
                except json.JSONDecodeError:
                    # Not JSON, treat as error
                    pytest.fail(f"Unexpected result: {result}")
        
        if isinstance(result, list):
            # Result is a list of documents
            print(f"Found {len(result)} documents")
            
            assert len(result) >= expected_min_results, \
                f"Expected at least {expected_min_results} results, got {len(result)}"
            
            # Validate each document structure and metadata
            for idx, doc in enumerate(result):
                assert isinstance(doc, dict), f"Document {idx} should be a dictionary, got {type(doc)}"
                
                # Check metadata exists
                if 'metadata' not in doc and 'cmetadata' not in doc:
                    pytest.fail(f"Document {idx} missing metadata field. Available fields: {doc.keys()}")
                
                # Get metadata (handle both 'metadata' and 'cmetadata' keys)
                doc_metadata = doc.get('metadata') or doc.get('cmetadata', {})
                
                # Validate filtered fields are present in metadata
                if validate_metadata:
                    for field, expected_value in validate_metadata.items():
                        if isinstance(expected_value, dict):
                            # Handle operators like $gte, $in
                            if "$gte" in expected_value:
                                # Validate field >= value
                                assert field in doc_metadata, \
                                    f"Document {idx} missing field '{field}' in metadata. Available: {doc_metadata.keys()}"
                                actual_value = doc_metadata[field]
                                expected_threshold = expected_value["$gte"]
                                assert actual_value >= expected_threshold, \
                                    f"Document {idx} field '{field}' value {actual_value} is not >= {expected_threshold}"
                                print(f"  ✓ Document {idx}: {field}={actual_value} >= {expected_threshold}")
                            elif "$in" in expected_value:
                                # Validate field contains at least one value from list
                                assert field in doc_metadata, \
                                    f"Document {idx} missing field '{field}' in metadata. Available: {doc_metadata.keys()}"
                                actual_value = doc_metadata[field]
                                expected_values = expected_value["$in"]
                                # actual_value could be a list or single value
                                if isinstance(actual_value, list):
                                    # Check if any expected value is in actual list
                                    has_match = any(val in actual_value for val in expected_values)
                                    assert has_match, \
                                        f"Document {idx} field '{field}' {actual_value} doesn't contain any of {expected_values}"
                                else:
                                    # Single value - check if it's in expected list
                                    assert actual_value in expected_values, \
                                        f"Document {idx} field '{field}' value {actual_value} not in {expected_values}"
                                print(f"  ✓ Document {idx}: {field}={actual_value} matches $in filter")
                        else:
                            # Simple equality check
                            assert field in doc_metadata, \
                                f"Document {idx} missing field '{field}' in metadata. Available: {doc_metadata.keys()}"
                            actual_value = doc_metadata[field]
                            assert actual_value == expected_value, \
                                f"Document {idx} field '{field}' has value '{actual_value}', expected '{expected_value}'"
                            print(f"  ✓ Document {idx}: {field}={actual_value}")
            
            print(f"✓ Test passed: {description} ({len(result)} documents returned)")
        
        elif isinstance(result, dict):
            # Result might be a single document or structured response
            pytest.fail(f"Unexpected result format: single dict. Expected list of documents.")
        else:
            pytest.fail(f"Unexpected result type: {type(result)}")
        
    except Exception as e:
        pytest.fail(f"Search failed for test '{description}': {str(e)}")


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v", "-s"])
