"""
DEPRECATED: This module has been split into separate modules.

The Inventory module now has two distinct capabilities:

1. **Ingestion Pipeline** (ingestion.py)
   - Workflow for building/updating knowledge graphs
   - Use: `from alita_sdk.community.inventory import IngestionPipeline`
   
2. **Retrieval Toolkit** (retrieval.py)
   - Pure query toolkit for agents
   - Use: `from alita_sdk.community.inventory import InventoryRetrievalApiWrapper`

This file is kept for backward compatibility only.
"""

import warnings

# Re-export from new modules for backward compatibility
from .retrieval import InventoryRetrievalApiWrapper
from .ingestion import IngestionPipeline, IngestionResult, ingest_repository

# Backward compatibility alias
InventoryApiWrapper = InventoryRetrievalApiWrapper

__all__ = [
    'InventoryApiWrapper',  # Deprecated alias
    'InventoryRetrievalApiWrapper',
    'IngestionPipeline',
    'IngestionResult',
    'ingest_repository',
]
