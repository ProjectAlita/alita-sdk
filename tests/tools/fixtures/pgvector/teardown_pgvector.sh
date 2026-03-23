#!/usr/bin/env bash
#
# Teardown pgvector database for BaseIndexerToolkit tests
#
# This script stops and removes the pgvector Docker container.
#
# Usage:
#   ./tests/tools/fixtures/pgvector/teardown_pgvector.sh
#
# Environment variables:
#   PGVECTOR_CONTAINER_NAME  - Docker container name (default: pgvector-test)

set -euo pipefail

# Configuration
CONTAINER_NAME="${PGVECTOR_CONTAINER_NAME:-pgvector-test}"

echo "============================================"
echo "pgvector Test Database Teardown"
echo "============================================"

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ℹ️  Container '$CONTAINER_NAME' does not exist. Nothing to do."
    exit 0
fi

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "🛑 Stopping container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" >/dev/null
fi

# Remove container
echo "🗑️  Removing container: $CONTAINER_NAME"
docker rm "$CONTAINER_NAME" >/dev/null

echo "✅ pgvector test database removed successfully!"
echo "============================================"
