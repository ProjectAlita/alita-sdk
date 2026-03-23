#!/usr/bin/env bash
#
# Setup pgvector database for BaseIndexerToolkit tests
#
# This script:
# 1. Starts a pgvector Docker container
# 2. Waits for PostgreSQL to be ready
# 3. Loads test data from SQL dump
#
# Usage:
#   ./tests/tools/fixtures/pgvector/setup_pgvector.sh
#
# Environment variables:
#   PGVECTOR_CONTAINER_NAME  - Docker container name (default: pgvector-test)
#   PGVECTOR_PORT            - Host port to expose (default: 5435)
#   PGVECTOR_TIMEOUT         - Seconds to wait for DB ready (default: 30)

set -euo pipefail

# Configuration
CONTAINER_NAME="${PGVECTOR_CONTAINER_NAME:-pgvector-test}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-yourpassword}"
POSTGRES_DB="${POSTGRES_DB:-postgres}"
HOST_PORT="${PGVECTOR_PORT:-5435}"
CONTAINER_PORT="5432"
TIMEOUT="${PGVECTOR_TIMEOUT:-30}"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
SQL_DUMP="$SCRIPT_DIR/init_db.sql"

echo "============================================"
echo "pgvector Test Database Setup"
echo "============================================"
echo "Container: $CONTAINER_NAME"
echo "Port: $HOST_PORT"
echo "Database: $POSTGRES_DB"
echo "============================================"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Stop and remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "🗑️  Removing existing container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

# Start pgvector container
echo "🚀 Starting pgvector container..."
docker run --name "$CONTAINER_NAME" \
    -e POSTGRES_USER="$POSTGRES_USER" \
    -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    -e POSTGRES_DB="$POSTGRES_DB" \
    -p "${HOST_PORT}:${CONTAINER_PORT}" \
    -d ankane/pgvector

echo "⏳ Waiting for PostgreSQL to be ready..."

# Wait for PostgreSQL to accept connections
elapsed=0
while [ $elapsed -lt $TIMEOUT ]; do
    if docker exec "$CONTAINER_NAME" pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    
    sleep 1
    elapsed=$((elapsed + 1))
    
    if [ $((elapsed % 5)) -eq 0 ]; then
        echo "   Still waiting... ($elapsed/${TIMEOUT}s)"
    fi
done

if [ $elapsed -ge $TIMEOUT ]; then
    echo "❌ Error: PostgreSQL did not become ready within ${TIMEOUT} seconds"
    echo "   Check container logs: docker logs $CONTAINER_NAME"
    exit 1
fi

# Additional wait for full initialization
sleep 2

# Load test data
echo "📊 Loading test data from SQL dump..."
if [ ! -f "$SQL_DUMP" ]; then
    echo "❌ Error: SQL dump not found at $SQL_DUMP"
    exit 1
fi

if docker exec -i "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$SQL_DUMP" 2>&1; then
    echo "✅ Test data loaded successfully!"
else
    echo "❌ Error: Failed to load test data"
    exit 1
fi

# Verify connection from host
echo "🔍 Verifying connection from host..."
CONNECTION_STRING="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${HOST_PORT}/${POSTGRES_DB}"

# Try to connect using psql if available
if command -v psql >/dev/null 2>&1; then
    if psql "$CONNECTION_STRING" -c "SELECT 1" >/dev/null 2>&1; then
        echo "✅ Connection verified from host!"
    else
        echo "⚠️  Warning: Could not connect from host using psql"
        echo "   This might be OK if psql is not installed locally"
    fi
else
    echo "ℹ️  psql not found on host, skipping connection verification"
fi

# Display connection info
echo ""
echo "============================================"
echo "✅ pgvector test database is ready!"
echo "============================================"
echo "Connection string:"
echo "  postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${HOST_PORT}/${POSTGRES_DB}"
echo ""
echo "Container management:"
echo "  Stop:    docker stop $CONTAINER_NAME"
echo "  Start:   docker start $CONTAINER_NAME"
echo "  Remove:  docker rm -f $CONTAINER_NAME"
echo "  Logs:    docker logs $CONTAINER_NAME"
echo ""
echo "Run tests:"
echo "  pytest tests/tools/test_base_indexer_toolkit.py -v"
echo "============================================"
