"""
Inventory Module for Knowledge Graph Construction and Retrieval.

This module provides two distinct capabilities:

1. **Ingestion Pipeline** - A workflow for building/updating knowledge graphs
   from source code repositories. NOT a toolkit - it's a defined process.
   
   Usage:
       from alita_sdk.community.inventory import (
           IngestionPipeline, 
           ingest_repository,
           PYTHON_PRESET,
           TYPESCRIPT_PRESET,
           get_preset
       )
       
       # Full pipeline with config
       pipeline = IngestionPipeline(
           llm=llm,
           graph_path="./graph.json",
           source_toolkits={'github': github_toolkit}
       )
       result = pipeline.run(source='github', branch='main')
       
       # Or one-shot convenience function
       result = ingest_repository(
           llm=llm,
           graph_path="./graph.json",
           source_toolkit=github_toolkit,
           source_name="github"
       )

2. **Retrieval Toolkit** - A pure query toolkit for retrieving context from 
   a pre-built knowledge graph. Can be added to any agent.
   
   Usage:
       from alita_sdk.community.inventory import InventoryRetrievalToolkit
       
       # As a toolkit for agents
       toolkit = InventoryRetrievalToolkit.get_toolkit(
           graph_path="./graph.json",
           base_directory="/path/to/source"  # For local content retrieval
       )
       tools = toolkit.get_tools()

Entity Taxonomy (8 layers, 49 types):
- Product Layer: feature, product, user_story, requirement, epic
- Domain Layer: domain, subdomain, business_capability, value_stream, process
- Service Layer: service, microservice, api, api_endpoint, message_queue, event
- Code Layer: module, package, class, function, method, interface, trait, enum, type, variable, constant
- Data Layer: database, table, collection, schema, model, entity, field, index, query, migration
- Testing Layer: test_suite, test_case, test_fixture, mock, stub, assertion
- Delivery Layer: pipeline, job, stage, environment, deployment, artifact, container
- Organization Layer: team, repository, project, workspace, organization

Relationship Taxonomy (8 categories, 34 types):
- Structural: CONTAINS, IMPORTS, EXTENDS, IMPLEMENTS, USES, DEPENDS_ON, INSTANTIATES, COMPOSED_OF
- Behavioral: CALLS, INVOKES, TRIGGERS, HANDLES, SUBSCRIBES_TO, PUBLISHES_TO, RETURNS
- Data Lineage: READS_FROM, WRITES_TO, TRANSFORMS, QUERIES, STORES_IN, REFERENCES
- UI/Product: RENDERS, ROUTES_TO, NAVIGATES_TO, DISPLAYS
- Testing: TESTS, MOCKS, COVERS, ASSERTS
- Ownership: OWNED_BY, MAINTAINED_BY, CREATED_BY
- Temporal: PRECEDES, FOLLOWS, SCHEDULED_BY
- Semantic: RELATED_TO, SIMILAR_TO, ALIAS_OF
"""

import logging
from typing import List, Optional, Dict, Any

# Configuration
from .config import (
    IngestionConfig,
    GuardrailsConfig,
    generate_config_template,
)

# Ingestion Pipeline - workflow for graph building
from .ingestion import (
    IngestionPipeline,
    IngestionResult,
    ingest_repository,
)

# Retrieval Toolkit - for querying graphs
from .retrieval import InventoryRetrievalApiWrapper

# Toolkit utilities - for configuration and instantiation
from .toolkit_utils import (
    load_toolkit_config,
    get_llm_for_config,
    get_source_toolkit,
)

# Core graph types
from .knowledge_graph import KnowledgeGraph, Citation

# Extractors (for advanced use)
from .extractors import (
    ENTITY_TAXONOMY,
    RELATIONSHIP_TAXONOMY,
    EntityExtractor,
    RelationExtractor,
    FactExtractor,
    DocumentClassifier,
    EntitySchemaDiscoverer,
)

# Toolkit wrapper for agent integration
from .toolkit import InventoryRetrievalToolkit

# Ingestion presets
from .presets import (
    PYTHON_PRESET,
    PYTHON_PRESET_WITH_TESTS,
    JAVASCRIPT_PRESET,
    TYPESCRIPT_PRESET,
    REACT_PRESET,
    NEXTJS_PRESET,
    JAVA_PRESET,
    SPRING_BOOT_PRESET,
    MAVEN_PRESET,
    GRADLE_PRESET,
    DOTNET_PRESET,
    CSHARP_PRESET,
    ASPNET_PRESET,
    FULLSTACK_JS_PRESET,
    MONOREPO_PRESET,
    DOCUMENTATION_PRESET,
    PRESETS,
    get_preset,
    list_presets,
    combine_presets,
)

logger = logging.getLogger(__name__)

name = "inventory"


def get_tools(tool: dict, tools_list: Optional[List[dict]] = None):
    """
    Get inventory retrieval tools for agent integration.
    
    This function is called by the toolkit loader to get the
    retrieval tools for querying a pre-built knowledge graph.
    
    NOTE: For ingestion, use the IngestionPipeline directly, not through
    the agent toolkit system. Ingestion is a workflow, not an agent task.
    
    Args:
        tool: The inventory toolkit configuration dict
        tools_list: Optional list of all toolkit configs in the agent
    
    Returns:
        List of BaseTool instances for knowledge graph retrieval
    """
    settings = tool.get('settings', {})
    
    # For retrieval, we need the graph path
    graph_path = settings.get('graph_path')
    if not graph_path:
        logger.warning("Inventory toolkit requires graph_path setting for retrieval")
    
    toolkit = InventoryRetrievalToolkit.get_toolkit(
        selected_tools=settings.get('selected_tools', []),
        toolkit_name=tool.get('toolkit_name'),
        # Graph location
        graph_path=graph_path,
        # For local content retrieval
        base_directory=settings.get('base_directory'),
        # Source toolkits for remote content retrieval (optional)
        source_toolkits=settings.get('source_toolkits', {}),
    )
    return toolkit.get_tools()


__all__ = [
    # Module name
    'name',
    'get_tools',
    
    # Configuration
    'IngestionConfig',
    'GuardrailsConfig',
    'generate_config_template',
    
    # Ingestion (workflow)
    'IngestionPipeline',
    'IngestionResult',
    'ingest_repository',
    
    # Retrieval (toolkit)
    'InventoryRetrievalToolkit',
    'InventoryRetrievalApiWrapper',
    
    # Toolkit utilities
    'load_toolkit_config',
    'get_llm_for_config',
    'get_source_toolkit',
    
    # Core types
    'KnowledgeGraph',
    'Citation',
    
    # Extractors
    'ENTITY_TAXONOMY',
    'RELATIONSHIP_TAXONOMY',
    'EntityExtractor',
    'RelationExtractor',
    'FactExtractor',
    'DocumentClassifier',
    'EntitySchemaDiscoverer',
    
    # Presets
    'PYTHON_PRESET',
    'PYTHON_PRESET_WITH_TESTS',
    'JAVASCRIPT_PRESET',
    'TYPESCRIPT_PRESET',
    'REACT_PRESET',
    'NEXTJS_PRESET',
    'JAVA_PRESET',
    'SPRING_BOOT_PRESET',
    'MAVEN_PRESET',
    'GRADLE_PRESET',
    'DOTNET_PRESET',
    'CSHARP_PRESET',
    'ASPNET_PRESET',
    'FULLSTACK_JS_PRESET',
    'MONOREPO_PRESET',
    'DOCUMENTATION_PRESET',
    'PRESETS',
    'get_preset',
    'list_presets',
    'combine_presets',
]
