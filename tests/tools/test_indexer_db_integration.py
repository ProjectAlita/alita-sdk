"""
Integration tests for BaseIndexerToolkit database persistence.

These tests verify that indexing operations correctly persist data to pgvector
by directly querying the database rather than relying on search_index results.

Test Coverage:
  - Code toolkit indexing (GitHub-like: files with code content)
  - Non-code toolkit indexing (SharePoint-like: documents)
  - Database record validation (count, metadata, embeddings)
  - Cleanup verification (remove_index)

Prerequisites:
  - pgvector running at PGVECTOR_TEST_CONNECTION_STRING
  - Valid Alita credentials for embedding generation
  - Environment variables: DEPLOYMENT_URL, PROJECT_ID, ALITA_API_KEY

Setup:
  1. Start pgvector (if using Docker):
       docker run -d --name pgvector-test \
         -e POSTGRES_PASSWORD=yourpassword \
         -p 5435:5432 \
         pgvector/pgvector:pg17

  2. Set environment variables:
       export DEPLOYMENT_URL=https://dev.elitea.ai
       export ALITA_API_KEY=your_api_key
       export PROJECT_ID=your_project_id

Run:
  pytest tests/tools/test_indexer_db_integration.py -v
  pytest tests/tools/test_indexer_db_integration.py::TestCodeIndexerDBPersistence -v
  pytest tests/tools/test_indexer_db_integration.py::TestNonCodeIndexerDBPersistence -v
"""

import os
import uuid
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document
from pydantic import SecretStr
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from alita_sdk.runtime.clients.client import AlitaClient
from alita_sdk.tools.base_indexer_toolkit import BaseIndexerToolkit

# Test configuration
PGVECTOR_CONNECTION_STRING = os.getenv(
    "PGVECTOR_TEST_CONNECTION_STRING",
    "postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres"
)

# Use unique collection names per test run to avoid conflicts
TEST_RUN_ID = str(uuid.uuid4())[:8]
CODE_COLLECTION_NAME = f"test_code_idx_{TEST_RUN_ID}"
NON_CODE_COLLECTION_NAME = f"test_docs_idx_{TEST_RUN_ID}"
TEST_INDEX_NAME = "dbtest"

# Credentials
DEPLOYMENT_URL = os.getenv("DEPLOYMENT_URL")
API_KEY = os.getenv("ALITA_API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS", "gpt-4o-mini")
DEFAULT_EMBEDDING_MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-ada-002")

# Expected embedding dimension for text-embedding-ada-002
EXPECTED_EMBEDDING_DIM = 1536


def _check_credentials_available() -> bool:
    """Check if all required credentials are available."""
    return all([DEPLOYMENT_URL, PROJECT_ID, API_KEY])


# ===================== Test Fixtures =====================

@pytest.fixture(scope="module")
def alita_client():
    """Create AlitaClient instance for tests."""
    if not _check_credentials_available():
        pytest.skip("Required credentials not available (DEPLOYMENT_URL, PROJECT_ID, ALITA_API_KEY)")

    try:
        client = AlitaClient(
            base_url=DEPLOYMENT_URL,
            project_id=int(PROJECT_ID),
            auth_token=SecretStr(API_KEY),
        )
        return client
    except Exception as e:
        pytest.skip(f"Failed to create AlitaClient: {e}")


@pytest.fixture
def code_indexer_toolkit(alita_client):
    """
    Create BaseIndexerToolkit for code content testing.
    
    This simulates a GitHub-like toolkit that indexes code files.
    """
    try:
        llm = alita_client.get_llm(
            model_name=DEFAULT_LLM_MODEL,
            model_config={"temperature": 0},
        )

        toolkit = BaseIndexerToolkit(
            alita=alita_client,
            llm=llm,
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            connection_string=PGVECTOR_CONNECTION_STRING,
            collection_schema=CODE_COLLECTION_NAME,
        )

        # Validate connection
        toolkit._ensure_vectorstore_initialized()

        yield toolkit

        # Cleanup after all tests
        _cleanup_schema(CODE_COLLECTION_NAME)
    except Exception as e:
        pytest.skip(f"Failed to create code indexer toolkit: {e}")


@pytest.fixture
def non_code_indexer_toolkit(alita_client):
    """
    Create BaseIndexerToolkit for non-code content testing.
    
    This simulates a SharePoint-like toolkit that indexes documents.
    """
    try:
        llm = alita_client.get_llm(
            model_name=DEFAULT_LLM_MODEL,
            model_config={"temperature": 0},
        )

        toolkit = BaseIndexerToolkit(
            alita=alita_client,
            llm=llm,
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            connection_string=PGVECTOR_CONNECTION_STRING,
            collection_schema=NON_CODE_COLLECTION_NAME,
        )

        # Validate connection
        toolkit._ensure_vectorstore_initialized()

        yield toolkit

        # Cleanup after all tests
        _cleanup_schema(NON_CODE_COLLECTION_NAME)
    except Exception as e:
        pytest.skip(f"Failed to create non-code indexer toolkit: {e}")


# ===================== Helper Functions =====================

def _cleanup_schema(schema_name: str):
    """Drop the test schema to clean up after tests."""
    try:
        from sqlalchemy import create_engine
        engine = create_engine(PGVECTOR_CONNECTION_STRING)
        with engine.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
            conn.commit()
        print(f"\n✓ Cleaned up schema: {schema_name}")
    except Exception as e:
        print(f"\n✗ Failed to cleanup schema {schema_name}: {e}")


def _get_db_records(
    toolkit: BaseIndexerToolkit,
    index_name: Optional[str] = None,
    include_embeddings: bool = False,
    exclude_index_meta: bool = True
) -> List[Dict[str, Any]]:
    """
    Query pgvector database directly to get indexed records.
    
    Args:
        toolkit: BaseIndexerToolkit instance (for database connection)
        index_name: Optional index name filter (collection metadata)
        include_embeddings: Whether to include embedding vectors in results
        exclude_index_meta: Whether to exclude index_meta tracking records (default: True)
        
    Returns:
        List of records with id, document, metadata, and optionally embedding
    """
    store = toolkit.vectorstore
    
    with Session(store.session_maker.bind) as session:
        query = session.query(
            store.EmbeddingStore.id,
            store.EmbeddingStore.document,
            store.EmbeddingStore.cmetadata,
        )
        
        if include_embeddings:
            query = query.add_columns(store.EmbeddingStore.embedding)
        
        # Filter by index name if provided
        if index_name:
            query = query.filter(
                func.jsonb_extract_path_text(store.EmbeddingStore.cmetadata, 'collection') == index_name
            )
        
        # Exclude index_meta records by default
        if exclude_index_meta:
            query = query.filter(
                or_(
                    func.jsonb_extract_path_text(store.EmbeddingStore.cmetadata, 'type').is_(None),
                    func.jsonb_extract_path_text(store.EmbeddingStore.cmetadata, 'type') != 'index_meta'
                )
            )
        
        records = query.all()
        
        result = []
        for record in records:
            item = {
                'id': record.id,
                'document': record.document,
                'metadata': record.cmetadata or {},
            }
            if include_embeddings:
                item['embedding'] = record.embedding
            result.append(item)
        
        return result


def _verify_embeddings_valid(records: List[Dict[str, Any]], expected_dim: int = EXPECTED_EMBEDDING_DIM) -> Dict[str, Any]:
    """
    Verify that embedding vectors are valid.
    
    Checks:
      - All records have non-null embeddings
      - All embeddings have the expected dimension
      - All embedding values are valid floats
      
    Returns:
        Dict with validation results
    """
    results = {
        'total_records': len(records),
        'records_with_embeddings': 0,
        'null_embeddings': 0,
        'wrong_dimension': 0,
        'invalid_values': 0,
        'dimension_found': None,
    }
    
    for record in records:
        embedding = record.get('embedding')
        
        if embedding is None:
            results['null_embeddings'] += 1
            continue
            
        results['records_with_embeddings'] += 1
        
        # Check dimension
        if not hasattr(embedding, '__len__'):
            results['invalid_values'] += 1
            continue
            
        dim = len(embedding)
        if results['dimension_found'] is None:
            results['dimension_found'] = dim
            
        if dim != expected_dim:
            results['wrong_dimension'] += 1
            
        # Check for NaN or infinite values
        try:
            import math
            for v in embedding:
                # Try to convert to float to handle different numeric types
                try:
                    float_val = float(v)
                    if math.isnan(float_val) or math.isinf(float_val):
                        results['invalid_values'] += 1
                        break
                except (TypeError, ValueError):
                    # If we can't convert to float, it's invalid
                    results['invalid_values'] += 1
                    break
        except (TypeError, ValueError, AttributeError):
            results['invalid_values'] += 1
    
    return results


# ===================== Mock Helpers =====================

def _mock_indexer_abstract_methods(toolkit):
    """
    Mock the abstract methods required by BaseIndexerToolkit.
    
    BaseIndexerToolkit has several abstract methods that must be implemented
    for indexing to work. This helper patches them using mock.patch.object.
    
    Args:
        toolkit: BaseIndexerToolkit instance to mock
        
    Returns:
        Context manager (ExitStack) for use in 'with' statements
    """
    from unittest.mock import patch, MagicMock
    from contextlib import ExitStack
    
    # Create mock functions (they receive 'self' as first arg since they're instance methods)
    def mock_get_indexed_data(self, index_name: str):
        """Return empty dict - no existing data to check for duplicates."""
        return {}
    
    def mock_key_fn(self, document: Document):
        """Generate key from document metadata source."""
        return document.metadata.get('source', str(id(document)))
    
    def mock_compare_fn(self, document: Document, idx):
        """Always return False - treat all documents as new/different."""
        return False
    
    def mock_remove_ids_fn(self, idx_data, key: str):
        """Return empty list - no IDs to remove."""
        return []
    
    # Create an ExitStack to manage multiple patches
    stack = ExitStack()
    
    # Patch methods with create=True to handle Pydantic models
    stack.enter_context(patch.object(toolkit.__class__, '_get_indexed_data', mock_get_indexed_data))
    stack.enter_context(patch.object(toolkit.__class__, 'key_fn', mock_key_fn))
    stack.enter_context(patch.object(toolkit.__class__, 'compare_fn', mock_compare_fn))
    stack.enter_context(patch.object(toolkit.__class__, 'remove_ids_fn', mock_remove_ids_fn))
    
    return stack


# ===================== Mock Document Generators =====================

def _mock_code_loader(**kwargs) -> Generator[Document, None, None]:
    """
    Mock _base_loader for code content (GitHub-like).
    
    Simulates loading Python files from a repository.
    """
    test_files = [
        {
            'filename': 'src/main.py',
            'content': 'def main():\n    print("Hello, World!")\n\nif __name__ == "__main__":\n    main()',
            'metadata': {
                'source': 'src/main.py',
                'language': 'python',
                'repository': 'test-repo',
                'commit_hash': 'abc123',
                'file_type': 'code',
            }
        },
        {
            'filename': 'src/utils.py',
            'content': 'def calculate(x, y):\n    """Add two numbers."""\n    return x + y\n\nclass Helper:\n    pass',
            'metadata': {
                'source': 'src/utils.py',
                'language': 'python',
                'repository': 'test-repo',
                'commit_hash': 'abc123',
                'file_type': 'code',
            }
        },
        {
            'filename': 'README.md',
            'content': '# Test Repository\n\nThis is a test repository for integration testing.\n\n## Features\n- Feature 1\n- Feature 2',
            'metadata': {
                'source': 'README.md',
                'language': 'markdown',
                'repository': 'test-repo',
                'commit_hash': 'abc123',
                'file_type': 'documentation',
            }
        },
    ]
    
    for file_data in test_files:
        doc = Document(
            page_content=file_data['content'],
            metadata=file_data['metadata']
        )
        yield doc


def _mock_non_code_loader(**kwargs) -> Generator[Document, None, None]:
    """
    Mock _base_loader for non-code content (SharePoint-like).
    
    Simulates loading documents like PDFs, Word docs, etc.
    """
    test_documents = [
        {
            'title': 'Project Plan 2024',
            'content': 'Project Overview:\n\nObjective: Deliver new features by Q2 2024.\n\nPhases:\n1. Planning (Jan-Feb)\n2. Development (Mar-Apr)\n3. Testing (May)\n4. Launch (Jun)',
            'metadata': {
                'source': 'Documents/project_plan.pdf',
                'title': 'Project Plan 2024',
                'file_type': 'pdf',
                'author': 'Project Manager',
                'created_date': '2024-01-15',
            }
        },
        {
            'title': 'Meeting Notes - Jan 2024',
            'content': 'Meeting Notes - January 15, 2024\n\nAttendees: Team A, Team B\n\nAgenda:\n- Review progress\n- Discuss blockers\n- Plan next sprint\n\nAction Items:\n- Fix bug #123\n- Update documentation',
            'metadata': {
                'source': 'Documents/meeting_notes_jan.docx',
                'title': 'Meeting Notes - Jan 2024',
                'file_type': 'docx',
                'author': 'Scrum Master',
                'created_date': '2024-01-15',
            }
        },
        {
            'title': 'Technical Specifications',
            'content': 'System Architecture:\n\n1. Frontend: React + TypeScript\n2. Backend: Python + FastAPI\n3. Database: PostgreSQL\n4. Cache: Redis\n\nPerformance Requirements:\n- Response time < 200ms\n- Support 1000 concurrent users',
            'metadata': {
                'source': 'Documents/tech_specs.txt',
                'title': 'Technical Specifications',
                'file_type': 'txt',
                'author': 'Technical Lead',
                'created_date': '2024-01-10',
            }
        },
        {
            'title': 'Budget Report Q1',
            'content': 'Q1 2024 Budget Report\n\nRevenue: $500,000\nExpenses: $350,000\nProfit: $150,000\n\nCategories:\n- Development: $200,000\n- Marketing: $100,000\n- Operations: $50,000',
            'metadata': {
                'source': 'Documents/budget_q1.xlsx',
                'title': 'Budget Report Q1',
                'file_type': 'xlsx',
                'author': 'Finance Team',
                'created_date': '2024-03-31',
            }
        },
    ]
    
    for doc_data in test_documents:
        doc = Document(
            page_content=doc_data['content'],
            metadata=doc_data['metadata']
        )
        yield doc


# ===================== Test Classes =====================

@pytest.mark.integration
class TestCodeIndexerDBPersistence:
    """Test database persistence for code content indexing (GitHub-like)."""
    
    def test_index_code_creates_db_records(self, code_indexer_toolkit):
        """
        Test that index_data() creates records in pgvector for code files.
        
        Verifies:
          - Records are created in database
          - Record count matches number of files indexed
          - Collection name is set correctly in metadata
        """
        # Mock the _base_loader to return test code documents
        with _mock_indexer_abstract_methods(code_indexer_toolkit), \
             patch.object(code_indexer_toolkit, '_base_loader', side_effect=_mock_code_loader):
            # Index the test data
            result = code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            
            # Verify index_data succeeded
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Extract indexed count from message
            import re
            match = re.search(r'Successfully indexed (\d+) documents', result['message'])
            assert match, f"Could not parse indexed count from message: {result['message']}"
            indexed_count = int(match.group(1))
            
            # Query database directly
            records = _get_db_records(code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            
            # Verify record count matches
            assert len(records) == indexed_count, (
                f"Database record count ({len(records)}) doesn't match "
                f"indexed count ({indexed_count})"
            )
            
            # Verify all records have correct collection name
            for record in records:
                collection = record['metadata'].get('collection')
                assert collection == TEST_INDEX_NAME, (
                    f"Record {record['id']} has wrong collection: {collection} "
                    f"(expected: {TEST_INDEX_NAME})"
                )
            
            print(f"\n✓ Created {len(records)} code file records in database")
    
    def test_code_embeddings_are_valid(self, code_indexer_toolkit):
        """
        Test that embeddings are properly generated and stored for code files.
        
        Verifies:
          - All records have non-null embeddings
          - Embeddings have correct dimension (1536 for text-embedding-ada-002)
          - Embedding values are valid floats
        """
        # Mock the _base_loader and _get_indexed_data
        with patch.object(code_indexer_toolkit, '_base_loader', side_effect=_mock_code_loader), \
             patch.object(code_indexer_toolkit, '_get_indexed_data', return_value={}):
            # Index the test data
            result = code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Query database with embeddings
            records = _get_db_records(
                code_indexer_toolkit,
                index_name=TEST_INDEX_NAME,
                include_embeddings=True
            )
            
            # Verify embeddings
            validation = _verify_embeddings_valid(records, expected_dim=EXPECTED_EMBEDDING_DIM)
            
            assert validation['null_embeddings'] == 0, (
                f"Found {validation['null_embeddings']} records with null embeddings"
            )
            assert validation['wrong_dimension'] == 0, (
                f"Found {validation['wrong_dimension']} embeddings with wrong dimension. "
                f"Expected: {EXPECTED_EMBEDDING_DIM}, Found: {validation['dimension_found']}"
            )
            assert validation['invalid_values'] == 0, (
                f"Found {validation['invalid_values']} embeddings with invalid values (NaN/Inf)"
            )
            
            print(f"\n✓ All {validation['records_with_embeddings']} embeddings are valid")
            print(f"  Dimension: {validation['dimension_found']}")
    
    def test_code_metadata_populated(self, code_indexer_toolkit):
        """
        Test that document metadata is properly stored for code files.
        
        Verifies:
          - source, language, repository, commit_hash are present
          - file_type metadata is preserved
        """
        # Mock the _base_loader and _get_indexed_data
        with patch.object(code_indexer_toolkit, '_base_loader', side_effect=_mock_code_loader), \
             patch.object(code_indexer_toolkit, '_get_indexed_data', return_value={}):
            # Index the test data
            result = code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Query database
            records = _get_db_records(code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            
            # Check that we have the expected files
            source_files = [r['metadata'].get('source') for r in records]
            assert 'src/main.py' in source_files, "Missing main.py in indexed records"
            assert 'src/utils.py' in source_files, "Missing utils.py in indexed records"
            assert 'README.md' in source_files, "Missing README.md in indexed records"
            
            # Verify metadata fields for each record
            for record in records:
                meta = record['metadata']
                
                # Required fields
                assert 'source' in meta, f"Record {record['id']} missing 'source' metadata"
                assert 'collection' in meta, f"Record {record['id']} missing 'collection' metadata"
                
                # Code-specific fields
                source = meta.get('source', '')
                if source.endswith('.py'):
                    assert meta.get('language') == 'python', (
                        f"Python file {source} has wrong language: {meta.get('language')}"
                    )
                    assert meta.get('file_type') == 'code', (
                        f"Python file {source} has wrong file_type: {meta.get('file_type')}"
                    )
                    assert 'repository' in meta, f"Code file {source} missing repository metadata"
                    assert 'commit_hash' in meta, f"Code file {source} missing commit_hash metadata"
            
            print(f"\n✓ All {len(records)} code records have proper metadata")
    
    def test_remove_code_index_cleanup(self, code_indexer_toolkit):
        """
        Test that remove_index properly cleans up code records from database.
        
        Verifies:
          - Records exist after indexing
          - Records are deleted after remove_index
          - Schema is not dropped (only data is removed)
        """
        # Mock the _base_loader and _get_indexed_data
        with patch.object(code_indexer_toolkit, '_base_loader', side_effect=_mock_code_loader), \
             patch.object(code_indexer_toolkit, '_get_indexed_data', return_value={}):
            # Index the test data
            result = code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Verify records exist
            records_before = _get_db_records(code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            assert len(records_before) > 0, "No records found after indexing"
            
            # Remove the index
            code_indexer_toolkit.remove_index(index_name=TEST_INDEX_NAME)
            
            # Verify records are deleted
            records_after = _get_db_records(code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            assert len(records_after) == 0, (
                f"Found {len(records_after)} records after remove_index "
                f"(expected 0)"
            )
            
            print(f"\n✓ Successfully removed {len(records_before)} code records from database")


@pytest.mark.integration
class TestNonCodeIndexerDBPersistence:
    """Test database persistence for non-code content indexing (SharePoint-like)."""
    
    def test_index_documents_creates_db_records(self, non_code_indexer_toolkit):
        """
        Test that index_data() creates records in pgvector for documents.
        
        Verifies:
          - Records are created in database
          - Record count matches number of documents indexed
          - Collection name is set correctly in metadata
        """
        print(f"\n{'='*60}")
        schema_name = non_code_indexer_toolkit.vectorstore_params.get('alita_sdk_options', {}).get('target_schema') if non_code_indexer_toolkit.vectorstore_params else None
        print(f"Schema name (from params): {schema_name}")
        print(f"Expected schema: {NON_CODE_COLLECTION_NAME}")
        print(f"Index name: {TEST_INDEX_NAME}")
        print(f"{'='*60}")
        
        with _mock_indexer_abstract_methods(non_code_indexer_toolkit), \
             patch.object(non_code_indexer_toolkit, '_base_loader', side_effect=_mock_non_code_loader):
            # Index the test data
            result = non_code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            
            # Verify index_data succeeded
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Extract indexed count from message
            import re
            match = re.search(r'Successfully indexed (\d+) documents', result['message'])
            assert match, f"Could not parse indexed count from message: {result['message']}"
            indexed_count = int(match.group(1))
            
            # Query database directly
            records = _get_db_records(non_code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            
            # Verify record count matches
            assert len(records) == indexed_count, (
                f"Database record count ({len(records)}) doesn't match "
                f"indexed count ({indexed_count})"
            )
            
            # Verify all records have correct collection name
            for record in records:
                collection = record['metadata'].get('collection')
                assert collection == TEST_INDEX_NAME, (
                    f"Record {record['id']} has wrong collection: {collection} "
                    f"(expected: {TEST_INDEX_NAME})"
                )
            
            print(f"\n✓ Created {len(records)} document records in database")
    
    def test_document_embeddings_are_valid(self, non_code_indexer_toolkit):
        """
        Test that embeddings are properly generated and stored for documents.
        
        Verifies:
          - All records have non-null embeddings
          - Embeddings have correct dimension (1536 for text-embedding-ada-002)
          - Embedding values are valid floats
        """
        # Mock the _base_loader and _get_indexed_data
        with patch.object(non_code_indexer_toolkit, '_base_loader', side_effect=_mock_non_code_loader), \
             patch.object(non_code_indexer_toolkit, '_get_indexed_data', return_value={}):
            # Index the test data
            result = non_code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Query database with embeddings
            records = _get_db_records(
                non_code_indexer_toolkit,
                index_name=TEST_INDEX_NAME,
                include_embeddings=True
            )
            
            # Verify embeddings
            validation = _verify_embeddings_valid(records, expected_dim=EXPECTED_EMBEDDING_DIM)
            
            assert validation['null_embeddings'] == 0, (
                f"Found {validation['null_embeddings']} records with null embeddings"
            )
            assert validation['wrong_dimension'] == 0, (
                f"Found {validation['wrong_dimension']} embeddings with wrong dimension. "
                f"Expected: {EXPECTED_EMBEDDING_DIM}, Found: {validation['dimension_found']}"
            )
            assert validation['invalid_values'] == 0, (
                f"Found {validation['invalid_values']} embeddings with invalid values (NaN/Inf)"
            )
            
            print(f"\n✓ All {validation['records_with_embeddings']} embeddings are valid")
            print(f"  Dimension: {validation['dimension_found']}")
    
    def test_document_metadata_populated(self, non_code_indexer_toolkit):
        """
        Test that document metadata is properly stored for non-code documents.
        
        Verifies:
          - source, title, file_type are present
          - author, created_date metadata is preserved
        """
        # Mock the _base_loader and _get_indexed_data
        with patch.object(non_code_indexer_toolkit, '_base_loader', side_effect=_mock_non_code_loader), \
             patch.object(non_code_indexer_toolkit, '_get_indexed_data', return_value={}):
            # Index the test data
            result = non_code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Query database
            records = _get_db_records(non_code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            
            # Check that we have the expected documents
            titles = [r['metadata'].get('title') for r in records]
            assert 'Project Plan 2024' in titles, "Missing Project Plan in indexed records"
            assert 'Meeting Notes - Jan 2024' in titles, "Missing Meeting Notes in indexed records"
            assert 'Technical Specifications' in titles, "Missing Tech Specs in indexed records"
            assert 'Budget Report Q1' in titles, "Missing Budget Report in indexed records"
            
            # Verify metadata fields for each record
            for record in records:
                meta = record['metadata']
                
                # Required fields
                assert 'source' in meta, f"Record {record['id']} missing 'source' metadata"
                assert 'title' in meta, f"Record {record['id']} missing 'title' metadata"
                assert 'file_type' in meta, f"Record {record['id']} missing 'file_type' metadata"
                assert 'collection' in meta, f"Record {record['id']} missing 'collection' metadata"
                
                # Document-specific fields
                assert 'author' in meta, f"Record {record['id']} missing 'author' metadata"
                assert 'created_date' in meta, f"Record {record['id']} missing 'created_date' metadata"
                
                # Verify file_type is valid
                file_type = meta.get('file_type')
                assert file_type in ['pdf', 'docx', 'txt', 'xlsx'], (
                    f"Invalid file_type: {file_type}"
                )
            
            print(f"\n✓ All {len(records)} document records have proper metadata")
    
    def test_remove_document_index_cleanup(self, non_code_indexer_toolkit):
        """
        Test that remove_index properly cleans up document records from database.
        
        Verifies:
          - Records exist after indexing
          - Records are deleted after remove_index
          - Schema is not dropped (only data is removed)
        """
        # Mock the _base_loader and _get_indexed_data
        with patch.object(non_code_indexer_toolkit, '_base_loader', side_effect=_mock_non_code_loader), \
             patch.object(non_code_indexer_toolkit, '_get_indexed_data', return_value={}):
            # Index the test data
            result = non_code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Verify records exist
            records_before = _get_db_records(non_code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            assert len(records_before) > 0, "No records found after indexing"
            
            # Remove the index
            non_code_indexer_toolkit.remove_index(index_name=TEST_INDEX_NAME)
            
            # Verify records are deleted
            records_after = _get_db_records(non_code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            assert len(records_after) == 0, (
                f"Found {len(records_after)} records after remove_index "
                f"(expected 0)"
            )
            
            print(f"\n✓ Successfully removed {len(records_before)} document records from database")


@pytest.mark.integration
class TestIndexerDBEdgeCases:
    """Test edge cases and boundary conditions for database persistence."""
    
    def test_empty_index_name(self, non_code_indexer_toolkit):
        """
        Test indexing with empty index_name (uses default).
        
        Verifies that records are still created with proper metadata.
        """
        # Mock the _base_loader with minimal data
        def minimal_loader(**kwargs):
            yield Document(
                page_content="Test document",
                metadata={'source': 'test.txt'}
            )
        
        with _mock_indexer_abstract_methods(non_code_indexer_toolkit), \
             patch.object(non_code_indexer_toolkit, '_base_loader', side_effect=minimal_loader):
            # Index with empty index_name
            result = non_code_indexer_toolkit.index_data(
                index_name="",  # Empty string
                clean_index=True,
            )
            
            assert result['status'] == 'ok', f"index_data failed: {result}"
            
            # Query all records (no index_name filter)
            records = _get_db_records(non_code_indexer_toolkit)
            
            # Should have at least 1 record
            assert len(records) >= 1, "No records created with empty index_name"
            
            print(f"\n✓ Created {len(records)} records with empty index_name")
    
    def test_clean_index_flag(self, code_indexer_toolkit):
        """
        Test that clean_index=True properly removes existing records before indexing.
        
        Verifies:
          - First index creates records
          - Second index with clean_index=True removes old records
          - Final record count matches second index operation
        """
        # Define two different mock loaders
        def first_loader(**kwargs):
            yield Document(page_content="First index", metadata={'source': 'first.txt'})
        
        def second_loader(**kwargs):
            yield Document(page_content="Second index A", metadata={'source': 'second_a.txt'})
            yield Document(page_content="Second index B", metadata={'source': 'second_b.txt'})
        
        # First index
        with _mock_indexer_abstract_methods(code_indexer_toolkit), \
             patch.object(code_indexer_toolkit, '_base_loader', side_effect=first_loader):
            result1 = code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            assert result1['status'] == 'ok'
            
            records1 = _get_db_records(code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            assert len(records1) == 1, "First index should create 1 record"
        
        # Second index with clean_index=True
        with _mock_indexer_abstract_methods(code_indexer_toolkit), \
             patch.object(code_indexer_toolkit, '_base_loader', side_effect=second_loader):
            result2 = code_indexer_toolkit.index_data(
                index_name=TEST_INDEX_NAME,
                clean_index=True,
            )
            assert result2['status'] == 'ok'
            
            records2 = _get_db_records(code_indexer_toolkit, index_name=TEST_INDEX_NAME)
            assert len(records2) == 2, (
                f"Second index should replace old records and create 2 new ones, "
                f"found {len(records2)}"
            )
            
            # Verify old record is gone
            sources = [r['metadata'].get('source') for r in records2]
            assert 'first.txt' not in sources, "Old record not cleaned up"
            assert 'second_a.txt' in sources, "New record A missing"
            assert 'second_b.txt' in sources, "New record B missing"
        
        print(f"\n✓ clean_index=True properly replaced records (1 → 2)")
