-- PostgreSQL + pgvector test database initialization
-- This script creates test data for BaseIndexerToolkit search_index tests
--
-- Usage:
--   psql -h localhost -p 5435 -U postgres -d postgres -f tests/tools/fixtures/pgvector/init_db.sql
--
-- Or via Docker:
--   docker exec -i pgvector-test psql -U postgres -d postgres < tests/tools/fixtures/pgvector/init_db.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop existing test collection if exists
DROP TABLE IF EXISTS langchain_pg_collection CASCADE;
DROP TABLE IF EXISTS langchain_pg_embedding CASCADE;

-- Create collection table (LangChain PGVector schema)
CREATE TABLE langchain_pg_collection (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    cmetadata JSONB
);

-- Create embedding table with vector support
CREATE TABLE langchain_pg_embedding (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID REFERENCES langchain_pg_collection(uuid) ON DELETE CASCADE,
    embedding vector(1536),  -- OpenAI ada-002 embedding dimension
    document TEXT,
    cmetadata JSONB,
    custom_id VARCHAR(255)
);

-- Create indexes for performance
CREATE INDEX idx_embedding_collection_id ON langchain_pg_embedding(collection_id);
CREATE INDEX idx_embedding_vector ON langchain_pg_embedding USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_embedding_metadata ON langchain_pg_embedding USING gin(cmetadata);

-- Insert test collection
INSERT INTO langchain_pg_collection (name, cmetadata)
VALUES 
    ('test_indexer_collection__test_idx', '{"description": "Test collection for search_index tests"}'),
    ('test_indexer_collection__other_idx', '{"description": "Additional test collection"}');

-- Get collection IDs for reference
DO $$
DECLARE
    test_idx_id UUID;
    other_idx_id UUID;
BEGIN
    SELECT uuid INTO test_idx_id FROM langchain_pg_collection WHERE name = 'test_indexer_collection__test_idx';
    SELECT uuid INTO other_idx_id FROM langchain_pg_collection WHERE name = 'test_indexer_collection__other_idx';
    
    -- Insert test documents with embeddings and metadata
    -- Note: Using random embeddings for testing (in production these would be real embeddings)
    
    -- Document 1: Active documentation about Python testing
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Comprehensive guide to Python testing frameworks including pytest, unittest, and doctest. Best practices for writing maintainable test suites.',
        '{"status": "active", "category": "documentation", "priority": 8, "tags": ["python", "testing", "pytest"], "author": "test_author_1", "created_at": "2024-01-15"}'::jsonb,
        'doc_001'
    );
    
    -- Document 2: Active tutorial about Python testing
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Python testing tutorial: Learn how to write effective unit tests, integration tests, and end-to-end tests for your Python applications.',
        '{"status": "active", "category": "tutorial", "priority": 7, "tags": ["python", "testing", "tutorial"], "author": "test_author_2", "created_at": "2024-01-20"}'::jsonb,
        'doc_002'
    );
    
    -- Document 3: Archived documentation
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Legacy testing approaches in Python: unittest from Python standard library and traditional test methodologies.',
        '{"status": "archived", "category": "documentation", "priority": 3, "tags": ["python", "unittest", "legacy"], "author": "test_author_1", "created_at": "2023-06-10"}'::jsonb,
        'doc_003'
    );
    
    -- Document 4: Active code examples (high priority)
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Python testing code examples: Fixtures, parametrization, mocking, and test organization patterns for professional projects.',
        '{"status": "active", "category": "code", "priority": 9, "tags": ["python", "testing", "examples", "fixtures"], "author": "test_author_3", "created_at": "2024-02-01"}'::jsonb,
        'doc_004'
    );
    
    -- Document 5: Draft documentation
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Draft: Advanced Python testing strategies including property-based testing with Hypothesis and mutation testing.',
        '{"status": "draft", "category": "documentation", "priority": 6, "tags": ["python", "testing", "advanced"], "author": "test_author_2", "created_at": "2024-02-15"}'::jsonb,
        'doc_005'
    );
    
    -- Document 6: Active urgent category
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Urgent: Critical Python testing vulnerabilities and security best practices for test environments.',
        '{"status": "active", "category": "urgent", "priority": 10, "tags": ["python", "testing", "security"], "author": "test_author_3", "created_at": "2024-02-20"}'::jsonb,
        'doc_006'
    );
    
    -- Document 7: Active documentation (low priority)
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Introduction to software testing: Basic concepts and terminology for beginners learning Python programming.',
        '{"status": "active", "category": "documentation", "priority": 4, "tags": ["python", "basics", "introduction"], "author": "test_author_1", "created_at": "2024-01-05"}'::jsonb,
        'doc_007'
    );
    
    -- Document 8: Inactive documentation
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Deprecated Python testing tools and frameworks that are no longer maintained or recommended.',
        '{"status": "inactive", "category": "documentation", "priority": 2, "tags": ["python", "deprecated"], "author": "test_author_2", "created_at": "2023-03-15"}'::jsonb,
        'doc_008'
    );
    
    -- Document 9: Active tutorial (medium priority)
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Continuous Integration with Python testing: Setting up pytest in CI/CD pipelines with GitHub Actions and GitLab CI.',
        '{"status": "active", "category": "tutorial", "priority": 5, "tags": ["python", "testing", "ci-cd", "automation"], "author": "test_author_3", "created_at": "2024-01-25"}'::jsonb,
        'doc_009'
    );
    
    -- Document 10: Active reference material
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        test_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Python testing reference: Comprehensive API documentation for pytest plugins, fixtures, and configuration options.',
        '{"status": "active", "category": "reference", "priority": 7, "tags": ["python", "testing", "pytest", "api"], "author": "test_author_1", "created_at": "2024-02-05"}'::jsonb,
        'doc_010'
    );
    
    -- Insert documents into second collection for cross-collection testing
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        other_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'JavaScript testing frameworks: Jest, Mocha, and testing best practices for modern web applications.',
        '{"status": "active", "category": "documentation", "priority": 8, "tags": ["javascript", "testing", "jest"], "author": "test_author_4", "created_at": "2024-01-18"}'::jsonb,
        'doc_other_001'
    );
    
    INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id)
    VALUES (
        other_idx_id,
        (SELECT ARRAY(SELECT random() FROM generate_series(1, 1536)))::vector,
        'Go testing patterns: Table-driven tests, benchmarking, and the testing package in Go standard library.',
        '{"status": "active", "category": "documentation", "priority": 6, "tags": ["go", "testing"], "author": "test_author_4", "created_at": "2024-01-22"}'::jsonb,
        'doc_other_002'
    );
    
END $$;

-- Verify data insertion
SELECT 
    c.name AS collection_name,
    COUNT(e.id) AS document_count
FROM langchain_pg_collection c
LEFT JOIN langchain_pg_embedding e ON c.uuid = e.collection_id
GROUP BY c.name
ORDER BY c.name;

-- Show sample metadata to verify structure
SELECT 
    custom_id,
    document,
    cmetadata->>'status' AS status,
    cmetadata->>'category' AS category,
    cmetadata->>'priority' AS priority
FROM langchain_pg_embedding
WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'test_indexer_collection__test_idx')
ORDER BY custom_id
LIMIT 5;

-- Display summary statistics
SELECT 
    cmetadata->>'status' AS status,
    COUNT(*) AS count
FROM langchain_pg_embedding
WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'test_indexer_collection__test_idx')
GROUP BY cmetadata->>'status'
ORDER BY count DESC;

RAISE NOTICE 'Test database initialized successfully!';
RAISE NOTICE 'Collection: test_indexer_collection__test_idx with % documents', (SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'test_indexer_collection__test_idx'));
RAISE NOTICE 'Collection: test_indexer_collection__other_idx with % documents', (SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'test_indexer_collection__other_idx'));
