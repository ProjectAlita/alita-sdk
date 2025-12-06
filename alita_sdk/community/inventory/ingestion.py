"""
Inventory Ingestion Pipeline.

This module provides a workflow/pipeline for building and updating knowledge graphs
from source code repositories. It is NOT a toolkit - it's a defined process that:

1. Connects to source toolkits (GitHub, ADO, LocalGit, etc.)
2. Fetches documents via their loader() methods
3. Extracts entities using LLM
4. Extracts relations between entities
5. Tracks source information for both entities (via citations) and relations
6. Persists the graph to JSON

The result is a graph dump that can be queried by the RetrievalToolkit.

Multi-Source Support:
- Entities from different sources are merged when they have the same (type, name)
- Each entity maintains citations from all sources that reference it
- Relations are tagged with source_toolkit to track which source created them
- Cross-source relations are automatically tracked (e.g., Jira ticket -> GitHub PR)
- Query relations by source: graph.get_relations_by_source('github')
- Find cross-source relations: graph.get_cross_source_relations()

Usage:
    # With full configuration
    from alita_sdk.community.inventory import IngestionConfig, IngestionPipeline
    
    config = IngestionConfig.from_env()  # or .from_yaml("config.yml")
    pipeline = IngestionPipeline.from_config(config)
    pipeline.register_toolkit('github', github_toolkit)
    result = pipeline.run(source='github', branch='main')
    
    # Or simpler approach
    pipeline = IngestionPipeline(
        llm=llm,
        graph_path="/path/to/graph.json",
        source_toolkits={'github': github_toolkit}
    )
    result = pipeline.run(source='github')
    
    # Or delta update for changed files
    result = pipeline.delta_update(
        source='github',
        file_paths=['src/app.py', 'src/utils.py']
    )
"""

import logging
import hashlib
import re
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional, List, Dict, Generator, Callable, TYPE_CHECKING, Tuple
from datetime import datetime

from pydantic import BaseModel, Field, PrivateAttr
from langchain_core.documents import Document

from .knowledge_graph import KnowledgeGraph, Citation
from .extractors import (
    DocumentClassifier,
    EntitySchemaDiscoverer, 
    EntityExtractor,
    RelationExtractor,
    FactExtractor,
    ENTITY_TAXONOMY,
    RELATIONSHIP_TAXONOMY,
)
from .parsers import (
    parse_file as parser_parse_file,
    get_parser_for_file,
    ParseResult,
    Symbol,
    Relationship as ParserRelationship,
    SymbolType,
    RelationshipType as ParserRelationshipType,
)

if TYPE_CHECKING:
    from .config import GuardrailsConfig, IngestionConfig

logger = logging.getLogger(__name__)

# ============================================================================
# PARSER-BASED EXTRACTION (AST/Regex - No LLM)
# ============================================================================

# Symbol types that parsers extract (skip LLM for these)
PARSER_EXTRACTED_TYPES = {
    SymbolType.CLASS, SymbolType.FUNCTION, SymbolType.METHOD,
    SymbolType.MODULE, SymbolType.INTERFACE, SymbolType.CONSTANT,
    SymbolType.VARIABLE, SymbolType.IMPORT, SymbolType.PROPERTY,
    SymbolType.FIELD, SymbolType.ENUM, SymbolType.TYPE_ALIAS,
    SymbolType.DECORATOR, SymbolType.NAMESPACE, SymbolType.PARAMETER,
}

# Map parser SymbolType to entity type strings
SYMBOL_TYPE_TO_ENTITY_TYPE = {
    SymbolType.CLASS: "class",
    SymbolType.FUNCTION: "function",
    SymbolType.METHOD: "method",
    SymbolType.MODULE: "module",
    SymbolType.INTERFACE: "interface",
    SymbolType.CONSTANT: "constant",
    SymbolType.VARIABLE: "variable",
    SymbolType.IMPORT: "import",
    SymbolType.PROPERTY: "property",
    SymbolType.FIELD: "field",
    SymbolType.ENUM: "enum",
    SymbolType.TYPE_ALIAS: "type_alias",
    SymbolType.DECORATOR: "decorator",
    SymbolType.NAMESPACE: "namespace",
    SymbolType.PARAMETER: "parameter",
}

# Map parser RelationshipType to relation type strings  
PARSER_REL_TYPE_TO_STRING = {
    ParserRelationshipType.IMPORTS: "imports",
    ParserRelationshipType.EXPORTS: "exports",
    ParserRelationshipType.CALLS: "calls",
    ParserRelationshipType.RETURNS: "returns",
    ParserRelationshipType.INHERITANCE: "extends",
    ParserRelationshipType.IMPLEMENTATION: "implements",
    ParserRelationshipType.COMPOSITION: "contains",
    ParserRelationshipType.AGGREGATION: "uses",
    ParserRelationshipType.DEFINES: "defines",
    ParserRelationshipType.CONTAINS: "contains",
    ParserRelationshipType.DECORATES: "decorates",
    ParserRelationshipType.ANNOTATES: "annotates",
    ParserRelationshipType.REFERENCES: "references",
    ParserRelationshipType.USES: "uses",
}


def _is_code_file(file_path: str) -> bool:
    """Check if file is a code file that parsers can handle."""
    code_extensions = {
        '.py', '.pyx', '.pyi',  # Python
        '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',  # JavaScript/TypeScript
        '.java',  # Java
        '.kt', '.kts',  # Kotlin
        '.cs',  # C#
        '.rs',  # Rust
        '.swift',  # Swift
        '.go',  # Go
    }
    ext = Path(file_path).suffix.lower()
    return ext in code_extensions


def _is_code_like_file(file_path: str) -> bool:
    """
    Check if file looks like code but may not have a specific parser.
    
    This includes:
    - Supported code files (with parsers)
    - Unsupported code files (no parser - use hybrid fallback)
    - Script files that contain code structure
    """
    # All supported code files
    supported_extensions = {
        '.py', '.pyx', '.pyi',  # Python
        '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',  # JavaScript/TypeScript
        '.java',  # Java
        '.kt', '.kts',  # Kotlin
        '.cs',  # C#
        '.rs',  # Rust
        '.swift',  # Swift
        '.go',  # Go
    }
    
    # Additional code-like files that need hybrid fallback
    unsupported_code_extensions = {
        # Scripting languages
        '.lua', '.pl', '.pm', '.perl', '.rb', '.php',
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
        # Other programming languages
        '.scala', '.clj', '.cljs', '.ex', '.exs', '.erl', '.hrl',
        '.hs', '.ml', '.fs', '.fsx', '.r', '.R', '.jl',
        '.dart', '.nim', '.v', '.zig', '.cr', '.d',
        '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',
        '.m', '.mm',  # Objective-C
        '.groovy', '.gradle',
        # Data/Config that may contain code
        '.cmake', '.makefile', '.mk',
    }
    
    ext = Path(file_path).suffix.lower()
    
    # Also check for Makefile without extension
    file_name = Path(file_path).name.lower()
    if file_name in {'makefile', 'gnumakefile'}:
        return True
    
    return ext in supported_extensions or ext in unsupported_code_extensions


def _symbol_to_entity(
    symbol: Symbol,
    source_toolkit: str,
    generate_id_func: Callable[[str, str, str], str]
) -> Dict[str, Any]:
    """
    Convert a parser Symbol to an entity dict.
    
    Args:
        symbol: Parsed symbol from code parser
        source_toolkit: Source toolkit name
        generate_id_func: Function to generate entity ID
        
    Returns:
        Entity dictionary compatible with graph
    """
    entity_type = SYMBOL_TYPE_TO_ENTITY_TYPE.get(symbol.symbol_type, "unknown")
    
    # Generate entity ID
    entity_id = generate_id_func(entity_type, symbol.name, symbol.file_path)
    
    # Build properties from symbol metadata
    properties = {
        'description': symbol.docstring or '',
        'parent_symbol': symbol.parent_symbol,
        'full_name': symbol.full_name or symbol.get_qualified_name(),
        'visibility': symbol.visibility,
        'is_static': symbol.is_static,
        'is_async': symbol.is_async,
        'is_exported': symbol.is_exported,
        'signature': symbol.signature,
        'return_type': symbol.return_type,
    }
    # Add any extra metadata
    properties.update(symbol.metadata)
    # Remove None values
    properties = {k: v for k, v in properties.items() if v is not None}
    
    # Create citation with line range
    line_start = symbol.range.start.line if symbol.range else 1
    line_end = symbol.range.end.line if symbol.range else line_start
    
    citation = Citation(
        file_path=symbol.file_path,
        line_start=line_start,
        line_end=line_end,
        source_toolkit=source_toolkit,
        doc_id=f"{source_toolkit}://{symbol.file_path}",
    )
    
    return {
        'id': entity_id,
        'name': symbol.name,
        'type': entity_type,
        'citation': citation,
        'properties': properties,
        'source': 'parser',  # Mark as parser-extracted
    }


def _parser_relationship_to_dict(
    rel: ParserRelationship,
    source_toolkit: str,
) -> Dict[str, Any]:
    """
    Convert a parser Relationship to a relation dict.
    
    Args:
        rel: Parsed relationship from code parser
        source_toolkit: Source toolkit name
        
    Returns:
        Relation dictionary compatible with graph
    """
    rel_type = PARSER_REL_TYPE_TO_STRING.get(rel.relationship_type, "references")
    
    return {
        'source_symbol': rel.source_symbol,
        'target_symbol': rel.target_symbol,
        'relation_type': rel_type,
        'source_file': rel.source_file,
        'target_file': rel.target_file,
        'confidence': rel.confidence,
        'is_cross_file': rel.is_cross_file,
        'source': 'parser',  # Mark as parser-extracted
        'source_toolkit': source_toolkit,
    }

# ============================================================================
# ENTITY TYPE NORMALIZATION
# ============================================================================

# Types that should never be deduplicated (context-dependent)
CONTEXT_DEPENDENT_TYPES = {
    "tool", "property", "properties", "parameter", "argument",
    "field", "column", "attribute", "option", "setting",
    "step", "test_step", "ui_field", "endpoint", "method",
    "mcp_tool", "mcp_resource",
    # File-level nodes are unique per file path
    "file", "source_file", "document_file", "config_file", "web_file",
}

# Build canonical type set from ENTITY_TAXONOMY
_CANONICAL_TYPES = set()
for layer_data in ENTITY_TAXONOMY.values():
    for type_def in layer_data["types"]:
        _CANONICAL_TYPES.add(type_def["name"].lower())

# Map common variations to canonical forms
TYPE_NORMALIZATION_MAP = {
    # Tool/Toolkit variations
    "tools": "tool",
    "Tool": "tool", 
    "Tools": "tool",
    "Toolkit": "toolkit",
    "toolkits": "toolkit",
    # MCP variations
    "MCP Server": "mcp_server",
    "MCP Tool": "mcp_tool",
    "MCP Resource": "mcp_resource",
    # Common variations  
    "Feature": "feature",
    "Features": "feature",
    "API": "api",
    "APIs": "api",
    "Service": "service",
    "Services": "service",
    "Endpoint": "endpoint",
    "Endpoints": "endpoint",
    "Configuration": "configuration",
    "Config": "configuration",
    "Test Case": "test_case",
    "Test Cases": "test_case",
    "test case": "test_case",
    "User Story": "user_story",
    "User Stories": "user_story",
    "user story": "user_story",
    "Business Rule": "business_rule",
    "business rule": "business_rule",
    "UI Component": "ui_component",
    "ui component": "ui_component",
    "UI Field": "ui_field",
    "ui field": "ui_field",
    "Test Suite": "test_suite",
    "test suite": "test_suite",
    "Test Step": "test_step",
    "test step": "test_step",
    "Glossary Term": "glossary_term",
    "glossary term": "glossary_term",
    "Domain Entity": "domain_entity",
    "domain entity": "domain_entity",
    "Pull Request": "pull_request",
    "pull request": "pull_request",
}

def normalize_entity_type(entity_type: str) -> str:
    """
    Normalize entity type to canonical lowercase form.
    
    Args:
        entity_type: Raw entity type from LLM extraction
        
    Returns:
        Canonical lowercase entity type
    """
    if not entity_type:
        return "unknown"
    
    # Check explicit mapping first
    if entity_type in TYPE_NORMALIZATION_MAP:
        return TYPE_NORMALIZATION_MAP[entity_type]
    
    # Normalize: lowercase, replace spaces with underscores
    normalized = entity_type.lower().strip().replace(" ", "_").replace("-", "_")
    
    # If it's already canonical, return it
    if normalized in _CANONICAL_TYPES:
        return normalized
    
    # Handle plural forms by removing trailing 's' (but not 'ss' like 'class')
    if normalized.endswith('s') and not normalized.endswith('ss') and len(normalized) > 3:
        singular = normalized[:-1]
        if singular in _CANONICAL_TYPES:
            return singular
    
    # Return the normalized form even if not in taxonomy
    # (allows for custom types while maintaining consistency)
    return normalized


class IngestionResult(BaseModel):
    """Result of an ingestion run."""
    success: bool = True
    source: str = "unknown"
    documents_processed: int = 0
    documents_skipped: int = 0
    entities_added: int = 0
    entities_removed: int = 0
    relations_added: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = Field(default_factory=list)
    failed_documents: List[str] = Field(default_factory=list)
    graph_stats: Dict[str, Any] = Field(default_factory=dict)
    resumed_from_checkpoint: bool = False
    
    def __str__(self) -> str:
        status = "✅ Success" if self.success else "❌ Failed"
        resumed = " (resumed)" if self.resumed_from_checkpoint else ""
        skipped_info = f"\n  Documents skipped: {self.documents_skipped}" if self.documents_skipped else ""
        failed_info = f"\n  Failed documents: {len(self.failed_documents)}" if self.failed_documents else ""
        return (
            f"{status}: Ingestion from {self.source}{resumed}\n"
            f"  Documents processed: {self.documents_processed}{skipped_info}{failed_info}\n"
            f"  Entities added: {self.entities_added}\n"
            f"  Relations added: {self.relations_added}\n"
            f"  Duration: {self.duration_seconds:.1f}s\n"
            f"  Graph: {self.graph_stats.get('node_count', 0)} entities, "
            f"{self.graph_stats.get('edge_count', 0)} relations"
        )


class IngestionCheckpoint(BaseModel):
    """
    Checkpoint for resumable ingestion.
    
    Saved periodically during ingestion to allow recovery from failures.
    """
    # Run identification
    run_id: str = Field(description="Unique identifier for this ingestion run")
    source: str = Field(description="Source toolkit name")
    started_at: str = Field(description="ISO timestamp when ingestion started")
    updated_at: str = Field(description="ISO timestamp of last checkpoint update")
    
    # Configuration
    branch: Optional[str] = None
    whitelist: Optional[List[str]] = None
    blacklist: Optional[List[str]] = None
    extract_relations: bool = True
    
    # Progress tracking
    phase: str = Field(default="fetch", description="Current phase: fetch, extract, relations, complete")
    documents_processed: int = 0
    entities_added: int = 0
    relations_added: int = 0
    
    # Processed document tracking with content hashes for incremental updates
    # Maps file_path -> content_hash (allows detecting changed files)
    processed_files: List[str] = Field(default_factory=list)  # Legacy: just paths
    file_hashes: Dict[str, str] = Field(default_factory=dict)  # New: path -> content_hash
    
    # Failed document tracking for retry
    failed_files: List[Dict[str, Any]] = Field(default_factory=list)  # [{file_path, error, attempts}]
    
    # Collected entities for relation extraction (stored if phase changes)
    pending_entities: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Status
    completed: bool = False
    errors: List[str] = Field(default_factory=list)
    
    @classmethod
    def create(cls, source: str, branch: Optional[str] = None, 
               whitelist: Optional[List[str]] = None,
               blacklist: Optional[List[str]] = None,
               extract_relations: bool = True) -> 'IngestionCheckpoint':
        """Create a new checkpoint for a fresh ingestion run."""
        import uuid
        now = datetime.utcnow().isoformat()
        return cls(
            run_id=str(uuid.uuid4())[:8],
            source=source,
            started_at=now,
            updated_at=now,
            branch=branch,
            whitelist=whitelist,
            blacklist=blacklist,
            extract_relations=extract_relations,
        )
    
    def save(self, checkpoint_path: str) -> None:
        """Save checkpoint to disk."""
        import json
        self.updated_at = datetime.utcnow().isoformat()
        path = Path(checkpoint_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file first, then rename for atomicity
        temp_path = path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(self.model_dump(), f, indent=2, default=str)
        temp_path.rename(path)
        
        logger.debug(f"Checkpoint saved: {self.documents_processed} docs, {self.entities_added} entities")
    
    @classmethod
    def load(cls, checkpoint_path: str) -> Optional['IngestionCheckpoint']:
        """Load checkpoint from disk. Returns None if not found."""
        import json
        path = Path(checkpoint_path)
        if not path.exists():
            return None
        
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(**data)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return None
    
    def mark_file_processed(self, file_path: str, content_hash: Optional[str] = None) -> None:
        """Mark a file as successfully processed with optional content hash."""
        if file_path not in self.processed_files:
            self.processed_files.append(file_path)
        if content_hash:
            self.file_hashes[file_path] = content_hash
    
    def mark_file_failed(self, file_path: str, error: str) -> None:
        """Mark a file as failed with error details."""
        # Check if already in failed list
        for failed in self.failed_files:
            if failed['file_path'] == file_path:
                failed['attempts'] = failed.get('attempts', 1) + 1
                failed['last_error'] = error
                return
        
        self.failed_files.append({
            'file_path': file_path,
            'error': error,
            'attempts': 1
        })
    
    def is_file_processed(self, file_path: str) -> bool:
        """Check if a file has already been processed."""
        return file_path in self.processed_files
    
    def has_file_changed(self, file_path: str, content_hash: str) -> bool:
        """
        Check if a file has changed since last processing.
        
        Returns True if:
        - File was never processed before
        - File was processed but we don't have its hash (legacy)
        - File content hash differs from stored hash
        """
        if file_path not in self.file_hashes:
            return True  # Never seen or no hash stored
        return self.file_hashes.get(file_path) != content_hash
    
    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Get stored content hash for a file."""
        return self.file_hashes.get(file_path)
    
    def get_retry_files(self, max_attempts: int = 3) -> List[str]:
        """Get files that should be retried (under max attempts)."""
        return [
            f['file_path'] for f in self.failed_files 
            if f.get('attempts', 1) < max_attempts
        ]


class IngestionPipeline(BaseModel):
    """
    Pipeline for ingesting source code into a knowledge graph.
    
    This is a workflow, not a toolkit. It processes sources and produces
    a graph dump that can be queried by the RetrievalToolkit.
    
    The pipeline:
    1. Connects to source toolkits (GitHub, ADO, LocalGit, etc.)
    2. Fetches documents via their loader() methods
    3. Uses LLM to extract entities based on ENTITY_TAXONOMY
    4. Uses LLM to extract relations based on RELATIONSHIP_TAXONOMY
    5. Persists graph to JSON (auto-save after mutations)
    
    Configuration can be provided directly or via IngestionConfig:
    
        # Direct configuration
        pipeline = IngestionPipeline(
            llm=llm,
            graph_path="./graph.json",
            guardrails=GuardrailsConfig(max_tokens_per_doc=4000),
        )
        
        # From config file
        config = IngestionConfig.from_yaml("config.yml")
        pipeline = IngestionPipeline.from_config(config)
    """
    
    # Core dependencies
    llm: Any = None
    alita: Any = None
    
    # Graph persistence path
    graph_path: str = Field(description="Path to persist the knowledge graph JSON")
    
    # Source toolkits (injected by runtime)
    # Maps toolkit name -> toolkit instance (e.g., {'github': GitHubApiWrapper})
    source_toolkits: Dict[str, Any] = Field(default_factory=dict)
    
    # Optional embedding for semantic search
    embedding: Optional[Any] = Field(default=None, description="Embedding model instance")
    embedding_model: Optional[str] = Field(default=None, description="Embedding model name (for Alita)")
    
    # Guardrails configuration
    guardrails: Optional[Any] = Field(
        default=None, 
        description="GuardrailsConfig for rate limiting, content filtering, etc."
    )
    
    # Checkpoint configuration for resumable ingestion
    checkpoint_dir: Optional[str] = Field(
        default=None,
        description="Directory to store checkpoints. If None, uses graph_path directory."
    )
    checkpoint_interval: int = Field(
        default=10,
        description="Save checkpoint every N documents processed"
    )
    
    # Parallel processing configuration
    max_parallel_extractions: int = Field(
        default=10,
        description="Maximum number of parallel entity extraction requests (default: 10)"
    )
    batch_size: int = Field(
        default=10,
        description="Number of documents to process in each parallel batch (default: 10)"
    )
    
    # Skip trivial files configuration
    min_file_lines: int = Field(
        default=20,
        description="Minimum number of lines for LLM extraction (smaller files only use parser)"
    )
    min_file_chars: int = Field(
        default=300,
        description="Minimum number of characters for LLM extraction (smaller files only use parser)"
    )
    
    # Progress callback (optional)
    # Signature: callback(message: str, phase: str) -> None
    progress_callback: Optional[Callable[[str, str], None]] = None
    
    # Private attributes
    _embedding: Optional[Any] = PrivateAttr(default=None)
    _knowledge_graph: Optional[KnowledgeGraph] = PrivateAttr(default=None)
    _document_classifier: Optional[DocumentClassifier] = PrivateAttr(default=None)
    _schema_discoverer: Optional[EntitySchemaDiscoverer] = PrivateAttr(default=None)
    _entity_extractor: Optional[EntityExtractor] = PrivateAttr(default=None)
    _relation_extractor: Optional[RelationExtractor] = PrivateAttr(default=None)
    _initialized: bool = PrivateAttr(default=False)
    _last_request_time: float = PrivateAttr(default=0.0)
    _request_count: int = PrivateAttr(default=0)
    _current_checkpoint: Optional[IngestionCheckpoint] = PrivateAttr(default=None)
    
    class Config:
        arbitrary_types_allowed = True
    
    def model_post_init(self, __context) -> None:
        """Initialize after model construction."""
        # Initialize knowledge graph
        self._knowledge_graph = KnowledgeGraph()
        
        # Handle model_construct case where graph_path may not be set
        graph_path = getattr(self, 'graph_path', None)
        if graph_path:
            try:
                path = Path(graph_path)
                if path.exists():
                    self._knowledge_graph.load_from_json(graph_path)
                    stats = self._knowledge_graph.get_stats()
                    logger.info(f"Loaded existing graph: {stats['node_count']} entities, {stats['edge_count']} relations")
            except Exception as e:
                logger.warning(f"Could not load existing graph: {e}")
        
        self._init_extractors()
    
    def _init_extractors(self) -> bool:
        """Initialize LLM-based extractors."""
        if self._initialized:
            return True
        
        if not self.llm:
            logger.warning("LLM not configured - extraction will fail")
            return False
        
        # Initialize embedding if configured (either directly or via Alita)
        if self.embedding:
            self._embedding = self.embedding
        elif self.alita and self.embedding_model:
            try:
                self._embedding = self.alita.get_embeddings(self.embedding_model)
            except Exception as e:
                logger.warning(f"Could not initialize embeddings: {e}")
        
        # Initialize extractors
        self._document_classifier = DocumentClassifier(llm=self.llm)
        self._schema_discoverer = EntitySchemaDiscoverer(llm=self.llm)
        self._entity_extractor = EntityExtractor(llm=self.llm, embedding=self._embedding)
        self._relation_extractor = RelationExtractor(llm=self.llm)
        self._initialized = True
        
        logger.info("Ingestion extractors initialized")
        return True
    
    def _apply_rate_limit(self) -> None:
        """Apply rate limiting if configured in guardrails."""
        if not self.guardrails:
            return
        
        rpm = getattr(self.guardrails, 'rate_limit_requests_per_minute', None)
        if not rpm:
            return
        
        # Calculate minimum interval between requests
        min_interval = 60.0 / rpm
        elapsed = time.time() - self._last_request_time
        
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
        self._request_count += 1
    
    def _filter_content(self, content: str) -> str:
        """Apply content filtering based on guardrails."""
        if not self.guardrails:
            return content
        
        if not getattr(self.guardrails, 'content_filter_enabled', False):
            return content
        
        filtered = content
        patterns = getattr(self.guardrails, 'filter_patterns', [])
        
        for pattern in patterns:
            try:
                filtered = re.sub(pattern, '[FILTERED]', filtered, flags=re.IGNORECASE)
            except re.error as e:
                logger.warning(f"Invalid filter pattern '{pattern}': {e}")
        
        if filtered != content:
            logger.debug("Content filtered for PII/secrets")
        
        return filtered
    
    def _get_max_entities(self) -> int:
        """Get max entities per doc from guardrails."""
        if self.guardrails:
            return getattr(self.guardrails, 'max_entities_per_doc', 50)
        return 50
    
    def _get_max_relations(self) -> int:
        """Get max relations per doc from guardrails."""
        if self.guardrails:
            return getattr(self.guardrails, 'max_relations_per_doc', 100)
        return 100
    
    def _get_confidence_threshold(self, for_relations: bool = False) -> float:
        """Get confidence threshold from guardrails."""
        if not self.guardrails:
            return 0.5
        
        if for_relations:
            return getattr(self.guardrails, 'relation_confidence_threshold', 0.5)
        return getattr(self.guardrails, 'entity_confidence_threshold', 0.5)
    
    def _log_progress(self, message: str, phase: str = "ingestion") -> None:
        """Log progress and call callback if set."""
        logger.info(f"[{phase}] {message}")
        if self.progress_callback:
            try:
                self.progress_callback(message, phase)
            except Exception as e:
                logger.debug(f"Progress callback failed: {e}")
    
    def _auto_save(self) -> None:
        """Auto-save graph after mutations."""
        if self.graph_path:
            try:
                self._knowledge_graph.dump_to_json(self.graph_path)
                logger.debug(f"Auto-saved graph to {self.graph_path}")
            except Exception as e:
                logger.warning(f"Failed to auto-save: {e}")
    
    def _get_checkpoint_path(self, source: str) -> str:
        """Get checkpoint file path for a source."""
        if self.checkpoint_dir:
            base_dir = Path(self.checkpoint_dir)
        else:
            base_dir = Path(self.graph_path).parent
        
        return str(base_dir / f".ingestion-checkpoint-{source}.json")
    
    def _save_checkpoint(self, checkpoint: IngestionCheckpoint) -> None:
        """Save checkpoint to disk."""
        try:
            checkpoint_path = self._get_checkpoint_path(checkpoint.source)
            checkpoint.save(checkpoint_path)
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
    
    def _load_checkpoint(self, source: str) -> Optional[IngestionCheckpoint]:
        """Load checkpoint from disk if exists."""
        checkpoint_path = self._get_checkpoint_path(source)
        return IngestionCheckpoint.load(checkpoint_path)
    
    def _clear_checkpoint(self, source: str) -> None:
        """Clear checkpoint file after successful completion."""
        try:
            checkpoint_path = Path(self._get_checkpoint_path(source))
            if checkpoint_path.exists():
                checkpoint_path.unlink()
                logger.debug(f"Cleared checkpoint for {source}")
        except Exception as e:
            logger.warning(f"Failed to clear checkpoint: {e}")
    
    def clear_checkpoint(self, source: str) -> bool:
        """
        Clear checkpoint for a source to force fresh ingestion.
        
        Use this when you want to re-ingest everything from scratch,
        ignoring previous file hashes and processing state.
        
        Args:
            source: Name of source toolkit
            
        Returns:
            True if checkpoint was cleared, False if no checkpoint existed
        """
        checkpoint_path = Path(self._get_checkpoint_path(source))
        if checkpoint_path.exists():
            self._clear_checkpoint(source)
            self._log_progress(f"🗑️ Cleared checkpoint for {source}", "reset")
            return True
        return False
    
    def get_checkpoint_info(self, source: str) -> Optional[Dict[str, Any]]:
        """
        Get information about existing checkpoint for a source.
        
        Useful for checking if incremental update is available and
        how many files are being tracked.
        
        Args:
            source: Name of source toolkit
            
        Returns:
            Dict with checkpoint info or None if no checkpoint exists
        """
        checkpoint = self._load_checkpoint(source)
        if not checkpoint:
            return None
        
        return {
            'run_id': checkpoint.run_id,
            'completed': checkpoint.completed,
            'phase': checkpoint.phase,
            'started_at': checkpoint.started_at,
            'updated_at': checkpoint.updated_at,
            'documents_processed': checkpoint.documents_processed,
            'entities_added': checkpoint.entities_added,
            'relations_added': checkpoint.relations_added,
            'files_tracked': len(checkpoint.file_hashes),
            'files_processed': len(checkpoint.processed_files),
            'files_failed': len(checkpoint.failed_files),
        }
    
    def _generate_entity_id(self, entity_type: str, name: str, file_path: str = None) -> str:
        """
        Generate unique entity ID.
        
        For most entity types, IDs are based on (type, name) only - NOT file_path.
        This enables same-named entities from different files to be merged,
        creating a unified knowledge graph with multiple citations per entity.
        
        HOWEVER, for context-dependent types (tools, properties, etc.), the file_path
        IS included because the same name in different files means different things:
        - "Get Tests" tool in Xray toolkit != "Get Tests" tool in Zephyr toolkit
        - "name" property in User entity != "name" property in Project entity
        """
        # Types that are context-dependent - same name in different files = different entities
        CONTEXT_DEPENDENT_TYPES = {
            "tool", "property", "properties", "parameter", "argument",
            "field", "column", "attribute", "option", "setting",
            "step", "test_step", "ui_field", "endpoint", "method",
            # File-level nodes are unique per file path
            "file", "source_file", "document_file", "config_file", "web_file",
        }
        
        # Normalize name for consistent hashing
        normalized_name = name.lower().strip()
        normalized_type = entity_type.lower().strip()
        
        # Include file_path for context-dependent types
        if normalized_type in CONTEXT_DEPENDENT_TYPES and file_path:
            # Use file path to differentiate same-named entities from different contexts
            content = f"{entity_type}:{normalized_name}:{file_path}"
        else:
            # Standard: merge same-named entities across files
            content = f"{entity_type}:{normalized_name}"
        
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _normalize_document(self, doc: Any, source_toolkit: str) -> Optional[Document]:
        """Normalize various document formats to LangChain Document."""
        if isinstance(doc, Document):
            # Already a Document, ensure metadata has source_toolkit
            doc.metadata['source_toolkit'] = source_toolkit
            return doc
        
        if isinstance(doc, dict):
            # Dict from loader generator
            content = doc.get('file_content') or doc.get('page_content', '')
            if not content:
                return None
            
            metadata = {
                'file_path': doc.get('file_name') or doc.get('source', 'unknown'),
                'commit_hash': doc.get('commit_hash'),
                'source_toolkit': source_toolkit,
            }
            # Merge additional metadata
            for k, v in doc.items():
                if k not in ('file_content', 'page_content', 'file_name', 'source', 'commit_hash'):
                    metadata[k] = v
            
            return Document(page_content=content, metadata=metadata)
        
        logger.warning(f"Unknown document type: {type(doc)}")
        return None
    
    def _extract_entities_from_doc(
        self, 
        doc: Document, 
        source_toolkit: str,
        schema: Optional[Dict] = None
    ) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
        """Extract entities from a single document.
        
        Uses parser-first approach:
        1. For code files with parser: Use AST/regex parsers to extract symbols (no LLM)
        2. For code files without parser: HYBRID FALLBACK - TextParser + full LLM
        3. For non-code files: LLM extracts semantic entities
        4. For all files with parser: Also run LLM for semantic entities not in code structure
        
        Returns:
            Tuple of (entities, failed_file_paths, parser_relationships) where:
            - entities: List of extracted entity dicts
            - failed_file_paths: File path if extraction failed, empty list otherwise
            - parser_relationships: List of relationships from parser (for code files)
        """
        file_path = (doc.metadata.get('file_path') or 
                    doc.metadata.get('file_name') or 
                    doc.metadata.get('source', 'unknown'))
        
        entities = []
        parser_relationships = []
        failed_docs = []
        
        # Get chunk position info for line number adjustment
        start_line = doc.metadata.get('start_line') or doc.metadata.get('line_start')
        
        # ========== PARSER-FIRST EXTRACTION ==========
        # Try to use parser for code files (AST/regex - no LLM needed)
        parser = get_parser_for_file(file_path)
        parser_extracted_names = set()  # Track what parser extracted to avoid LLM duplication
        use_full_llm_extraction = False  # Flag for hybrid fallback
        
        if parser and _is_code_file(file_path):
            try:
                # Parse file content with language-specific parser
                parse_result = parser_parse_file(file_path, content=doc.page_content)
                
                # Build symbol name to entity ID mapping for containment edges
                symbol_name_to_entity_id = {}
                
                # Convert symbols to entities
                for symbol in parse_result.symbols:
                    entity = _symbol_to_entity(
                        symbol, 
                        source_toolkit,
                        self._generate_entity_id
                    )
                    # Update citation with commit hash if available
                    if doc.metadata.get('commit_hash'):
                        entity['citation'].content_hash = doc.metadata.get('commit_hash')
                    
                    entities.append(entity)
                    parser_extracted_names.add(symbol.name.lower())
                    
                    # Track symbol full name to entity ID for containment edges
                    full_name = symbol.full_name or symbol.get_qualified_name() or symbol.name
                    symbol_name_to_entity_id[full_name] = entity['id']
                    # Also track by simple name for fallback matching
                    symbol_name_to_entity_id[symbol.name] = entity['id']
                
                # Convert relationships from parser
                for rel in parse_result.relationships:
                    parser_relationships.append(
                        _parser_relationship_to_dict(rel, source_toolkit)
                    )
                
                # ========== INTRA-FILE CONTAINMENT EDGES ==========
                # Create containment relationships based on Symbol.parent_symbol
                containment_count = 0
                for symbol in parse_result.symbols:
                    if symbol.parent_symbol:
                        # Find parent entity ID
                        child_full_name = symbol.full_name or symbol.get_qualified_name() or symbol.name
                        child_id = symbol_name_to_entity_id.get(child_full_name) or symbol_name_to_entity_id.get(symbol.name)
                        
                        # Try to find parent by full name or simple name
                        parent_id = symbol_name_to_entity_id.get(symbol.parent_symbol)
                        
                        if child_id and parent_id and child_id != parent_id:
                            parser_relationships.append({
                                'source_symbol': symbol.parent_symbol,
                                'target_symbol': child_full_name,
                                'relation_type': 'contains',
                                'source_file': file_path,
                                'target_file': file_path,
                                'confidence': 1.0,  # High confidence - structural
                                'is_cross_file': False,
                                'source': 'parser',
                                'source_toolkit': source_toolkit,
                                # Pre-resolved IDs for graph insertion
                                '_resolved_source_id': parent_id,
                                '_resolved_target_id': child_id,
                            })
                            containment_count += 1
                
                logger.debug(f"Parser extracted {len(entities)} entities, {len(parser_relationships)} relationships ({containment_count} containment) from {file_path}")
                
            except Exception as e:
                logger.warning(f"Parser failed for {file_path}: {e}, using hybrid fallback")
                use_full_llm_extraction = True  # Enable full LLM extraction
                
        elif _is_code_like_file(file_path) and not parser:
            # ========== HYBRID FALLBACK ==========
            # File looks like code but no parser available (e.g., .lua, .perl, .sh)
            # Use TextParser to extract textual references + full LLM extraction
            logger.info(f"Hybrid fallback for unsupported code file: {file_path}")
            use_full_llm_extraction = True
            
            try:
                # Use TextParser to extract textual references
                from .parsers import TextParser
                text_parser = TextParser()
                parse_result = text_parser.parse_file(file_path, content=doc.page_content)
                
                # Extract any textual relationships (See X, Depends on Y, etc.)
                for rel in parse_result.relationships:
                    parser_relationships.append(
                        _parser_relationship_to_dict(rel, source_toolkit)
                    )
                
                logger.debug(f"TextParser extracted {len(parse_result.relationships)} textual references from {file_path}")
                
            except Exception as e:
                logger.warning(f"TextParser failed for {file_path}: {e}")
        
        # ========== LLM EXTRACTION (semantic entities) ==========
        # For code files with parser: LLM extracts only semantic entities (features, requirements, etc.)
        # For hybrid fallback: LLM does full extraction including code structure
        # For non-code files: LLM does full extraction
        
        if self._entity_extractor:
            try:
                # Extract entities - skip_on_error=True returns (entities, failed_docs)
                extracted, llm_failed_docs = self._entity_extractor.extract_batch(
                    [doc], schema=schema, skip_on_error=True
                )
                failed_docs.extend(llm_failed_docs)
                
                for entity in extracted:
                    entity_name = entity.get('name', '').lower()
                    raw_type = entity.get('type', 'unknown')
                    normalized_type = normalize_entity_type(raw_type)
                    
                    # Skip if parser already extracted this (avoid duplicates for code entities)
                    # Only skip for code_layer types that parsers handle, and only if not hybrid fallback
                    code_layer_types = {'class', 'function', 'method', 'module', 'interface', 
                                       'constant', 'variable', 'import', 'property', 'field'}
                    if (not use_full_llm_extraction and 
                        entity_name in parser_extracted_names and 
                        normalized_type in code_layer_types):
                        continue
                    
                    # Adjust line numbers if this is a chunk with offset
                    entity_line_start = entity.get('line_start')
                    entity_line_end = entity.get('line_end')
                    
                    if start_line and entity_line_start:
                        entity_line_start = start_line + entity_line_start - 1
                        if entity_line_end:
                            entity_line_end = start_line + entity_line_end - 1
                    
                    entity_id = self._generate_entity_id(
                        normalized_type,
                        entity.get('name', 'unnamed'),
                        file_path
                    )
                    
                    # Create citation
                    citation = Citation(
                        file_path=file_path,
                        line_start=entity_line_start or entity.get('line_start'),
                        line_end=entity_line_end or entity.get('line_end'),
                        source_toolkit=source_toolkit,
                        doc_id=f"{source_toolkit}://{file_path}",
                        content_hash=doc.metadata.get('commit_hash'),
                    )
                    
                    entities.append({
                        'id': entity_id,
                        'name': entity.get('name', 'unnamed'),
                        'type': normalized_type,
                        'citation': citation,
                        'properties': {
                            k: v for k, v in entity.items()
                            if k not in ('id', 'name', 'type', 'content', 'text', 'line_start', 'line_end')
                        },
                        'source_doc': doc,
                        'source': 'llm_hybrid' if use_full_llm_extraction else 'llm',
                    })
                    
            except Exception as e:
                logger.error(f"LLM extraction failed for {file_path}: {e}")
                failed_docs.append(file_path)
        
        # =====================================================================
        # FACT EXTRACTION - Lightweight LLM for semantic insights
        # Code files: extract algorithms, behaviors, validations, dependencies
        # Text files: extract decisions, requirements, definitions, dates
        # =====================================================================
        if self.llm:
            try:
                fact_extractor = FactExtractor(self.llm)
                is_code = _is_code_file(file_path) or _is_code_like_file(file_path)
                
                # Use appropriate extraction method based on file type
                if is_code:
                    facts = fact_extractor.extract_code(doc)
                else:
                    facts = fact_extractor.extract(doc)
                
                for fact in facts:
                    fact_id = self._generate_entity_id(
                        'fact',
                        f"{fact.get('fact_type', 'unknown')}_{fact.get('subject', 'unknown')[:30]}",
                        file_path
                    )
                    
                    # Create citation for the fact
                    citation = Citation(
                        file_path=file_path,
                        line_start=fact.get('line_start'),
                        line_end=fact.get('line_end'),
                        source_toolkit=source_toolkit,
                        doc_id=f"{source_toolkit}://{file_path}",
                        content_hash=doc.metadata.get('commit_hash'),
                    )
                    
                    entities.append({
                        'id': fact_id,
                        'name': fact.get('subject', 'unknown fact'),
                        'type': 'fact',
                        'citation': citation,
                        'properties': {
                            'fact_type': fact.get('fact_type'),
                            'subject': fact.get('subject'),
                            'predicate': fact.get('predicate'),
                            'object': fact.get('object'),
                            'confidence': fact.get('confidence', 0.8),
                        },
                        'source_doc': doc,
                        'source': 'llm_fact',
                    })
                
                logger.debug(f"Extracted {len(facts)} facts from {file_path}")
            except Exception as e:
                logger.warning(f"Fact extraction failed for {file_path}: {e}")
        
        return entities, failed_docs, parser_relationships
    
    def _process_documents_batch(
        self,
        documents: List[Document],
        source_toolkit: str,
        schema: Optional[Dict] = None
    ) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, str], List[Dict[str, Any]]]:
        """
        Process a batch of documents in parallel for entity extraction.
        
        Args:
            documents: List of documents to process
            source_toolkit: Source toolkit name
            schema: Optional schema for extraction
            
        Returns:
            Tuple of (all_entities, failed_files, file_hashes, parser_relationships) where:
            - all_entities: Combined list of entities from all documents
            - failed_files: List of file paths that failed extraction
            - file_hashes: Dict mapping file_path to content_hash
            - parser_relationships: List of relationships from parsers (AST/regex extracted)
        """
        all_entities = []
        failed_files = []
        file_hashes = {}
        all_parser_relationships = []
        
        # Use ThreadPoolExecutor for parallel extraction
        with ThreadPoolExecutor(max_workers=self.max_parallel_extractions) as executor:
            # Submit all extraction tasks
            future_to_doc = {
                executor.submit(self._extract_entities_from_doc, doc, source_toolkit, schema): doc
                for doc in documents
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                file_path = (doc.metadata.get('file_path') or 
                            doc.metadata.get('file_name') or 
                            doc.metadata.get('source', 'unknown'))
                
                try:
                    entities, extraction_failures, parser_relationships = future.result()
                    
                    # Track content hash
                    content_hash = hashlib.sha256(doc.page_content.encode()).hexdigest()
                    file_hashes[file_path] = content_hash
                    
                    # Add entities to batch results
                    all_entities.extend(entities)
                    
                    # Collect parser relationships
                    all_parser_relationships.extend(parser_relationships)
                    
                    # Track failures
                    if extraction_failures:
                        failed_files.extend(extraction_failures)
                        
                except Exception as e:
                    logger.warning(f"Failed to process document '{file_path}': {e}")
                    failed_files.append(file_path)
        
        return all_entities, failed_files, file_hashes, all_parser_relationships
    
    def _process_batch_and_update_graph(
        self,
        doc_batch: List[Document],
        source: str,
        schema: Optional[Dict],
        checkpoint: IngestionCheckpoint,
        result: IngestionResult,
        all_entities: List[Dict[str, Any]],
        all_parser_relationships: List[Dict[str, Any]],
        is_incremental_update: bool
    ) -> None:
        """
        Process a batch of documents in parallel and update the graph.
        
        This method extracts entities from all documents in the batch concurrently,
        then adds them to the graph sequentially (graph operations are not thread-safe).
        
        Args:
            doc_batch: List of documents to process
            source: Source toolkit name
            schema: Optional schema for extraction
            checkpoint: Checkpoint for progress tracking
            result: IngestionResult to update
            all_entities: List to accumulate all entities
            all_parser_relationships: List to accumulate parser-extracted relationships
            is_incremental_update: Whether this is an incremental update
        """
        # Extract entities from all docs in parallel
        batch_entities, failed_files, file_hashes, parser_rels = self._process_documents_batch(
            doc_batch, source, schema
        )
        
        # Update graph with batch results (sequential - graph is not thread-safe)
        for entity in batch_entities:
            self._knowledge_graph.add_entity(
                entity_id=entity['id'],
                name=entity['name'],
                entity_type=entity['type'],
                citation=entity['citation'],
                properties=entity['properties']
            )
            result.entities_added += 1
            all_entities.append(entity)
        
        # Collect parser relationships for later processing
        all_parser_relationships.extend(parser_rels)
        
        # Update checkpoint with processed files and hashes
        for file_path, content_hash in file_hashes.items():
            if file_path not in failed_files:
                checkpoint.mark_file_processed(file_path, content_hash)
            result.documents_processed += 1
        
        # Track failed files
        for failed_file in failed_files:
            checkpoint.mark_file_failed(failed_file, "Entity extraction failed")
            if failed_file not in result.failed_documents:
                result.failed_documents.append(failed_file)
    
    def _process_file_batch_and_update_graph(
        self,
        file_batch: List[Tuple[str, List[Document], Document]],
        _raw_doc_by_file: Dict[str, Document],  # Deprecated, kept for compatibility
        source: str,
        schema: Optional[Dict],
        checkpoint: IngestionCheckpoint,
        result: IngestionResult,
        all_entities: List[Dict[str, Any]],
        all_parser_relationships: List[Dict[str, Any]],
        is_incremental_update: bool
    ) -> None:
        """
        Process a batch of files with their chunks and update the graph.
        
        For each file:
        1. Run parser on whole file (AST/regex extraction - no LLM)
        2. Run LLM on each chunk (facts + entities)
        3. Deduplicate facts/entities at file level
        4. Add to graph
        
        Args:
            file_batch: List of (file_path, chunks, raw_doc) tuples
            _raw_doc_by_file: DEPRECATED - raw_doc is now passed in file_batch tuple
            source: Source toolkit name
            schema: Optional schema for extraction
            checkpoint: Checkpoint for progress tracking
            result: IngestionResult to update
            all_entities: List to accumulate all entities
            all_parser_relationships: List to accumulate parser-extracted relationships
            is_incremental_update: Whether this is an incremental update
        """
        # Process files in parallel
        batch_start_time = time.time()
        logger.info(f"⏱️ [TIMING] Batch start: {len(file_batch)} files")
        
        with ThreadPoolExecutor(max_workers=self.max_parallel_extractions) as executor:
            future_to_file = {
                executor.submit(
                    self._process_file_with_chunks, 
                    file_path, chunks, raw_doc, source, schema
                ): file_path
                for file_path, chunks, raw_doc in file_batch
            }
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                
                try:
                    file_entities, parser_rels, content_hash = future.result()
                    
                    # Update graph with file results (sequential - graph is not thread-safe)
                    for entity in file_entities:
                        self._knowledge_graph.add_entity(
                            entity_id=entity['id'],
                            name=entity['name'],
                            entity_type=entity['type'],
                            citation=entity['citation'],
                            properties=entity['properties']
                        )
                        result.entities_added += 1
                        all_entities.append(entity)
                    
                    # Collect parser relationships
                    all_parser_relationships.extend(parser_rels)
                    
                    # Mark file as processed
                    checkpoint.mark_file_processed(file_path, content_hash)
                    result.documents_processed += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to process file '{file_path}': {e}")
                    checkpoint.mark_file_failed(file_path, str(e))
                    if file_path not in result.failed_documents:
                        result.failed_documents.append(file_path)
                    result.documents_processed += 1
        
        batch_duration = time.time() - batch_start_time
        logger.info(f"⏱️ [TIMING] Batch complete: {len(file_batch)} files in {batch_duration:.3f}s ({batch_duration/len(file_batch):.3f}s/file avg)")
    
    def _process_file_with_chunks(
        self,
        file_path: str,
        chunks: List[Document],
        raw_doc: Document,
        source_toolkit: str,
        schema: Optional[Dict] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
        """
        Process a single file: parser on whole file, LLM on chunks, dedupe at file level.
        
        Args:
            file_path: Path to the file
            chunks: List of chunk Documents for this file
            raw_doc: Raw (whole file) Document for parser
            source_toolkit: Source toolkit name
            schema: Optional schema for extraction
            
        Returns:
            Tuple of (deduplicated_entities, parser_relationships, content_hash)
        """
        all_entities = []
        parser_relationships = []
        content_hash = hashlib.sha256(raw_doc.page_content.encode()).hexdigest()
        
        # Check if file is too small or trivial for LLM extraction
        file_content = raw_doc.page_content
        line_count = file_content.count('\n') + 1
        char_count = len(file_content)
        
        # Detect trivial/boilerplate content
        skip_llm = False
        skip_reason = ""
        
        # 1. Too small
        if line_count < self.min_file_lines or char_count < self.min_file_chars:
            skip_llm = True
            skip_reason = f"small ({line_count} lines, {char_count} chars)"
        
        # 2. License-only files or files starting with license header that's most of the content
        if not skip_llm:
            content_lower = file_content.lower()
            license_indicators = [
                'apache license', 'mit license', 'bsd license', 'gpl license',
                'licensed under the', 'permission is hereby granted',
                'copyright (c)', 'copyright 20', 'all rights reserved',
                'without warranties or conditions', 'provided "as is"',
            ]
            license_matches = sum(1 for ind in license_indicators if ind in content_lower)
            
            # If 3+ license indicators and file is mostly comments/license text
            if license_matches >= 3:
                # Count actual code lines (non-empty, non-comment)
                code_lines = 0
                for line in file_content.split('\n'):
                    stripped = line.strip()
                    if stripped and not stripped.startswith(('#', '//', '/*', '*', '<!--', '"""', "'''")):
                        code_lines += 1
                
                # If less than 20% is actual code, it's mostly license/boilerplate
                if code_lines < line_count * 0.2:
                    skip_llm = True
                    skip_reason = f"license/boilerplate ({code_lines} code lines of {line_count})"
        
        # 3. Re-export / barrel files (e.g., index.js with only exports)
        if not skip_llm:
            content_stripped = file_content.strip()
            lines = [l.strip() for l in content_stripped.split('\n') if l.strip()]
            
            # Check if file is mostly import/export statements
            export_import_lines = sum(1 for l in lines if 
                l.startswith(('export ', 'import ', 'from ', 'module.exports', 'exports.'))
                or l.startswith('export {') or l.startswith('export default')
                or 'require(' in l)
            
            if len(lines) > 0 and export_import_lines / len(lines) > 0.8:
                skip_llm = True
                skip_reason = f"barrel/re-export file ({export_import_lines}/{len(lines)} export lines)"
        
        if skip_llm:
            logger.debug(f"Skipping LLM for {Path(file_path).name}: {skip_reason}")
        
        # ========== PARSER EXTRACTION (whole file, no LLM) ==========
        parser_start = time.time()
        parser = get_parser_for_file(file_path)
        parser_extracted_names = set()
        
        if parser and _is_code_file(file_path):
            try:
                parse_result = parser_parse_file(file_path, content=raw_doc.page_content)
                
                # Build symbol name to entity ID mapping for containment edges
                symbol_name_to_entity_id = {}
                
                # Convert symbols to entities
                for symbol in parse_result.symbols:
                    entity = _symbol_to_entity(
                        symbol, 
                        source_toolkit,
                        self._generate_entity_id
                    )
                    if raw_doc.metadata.get('commit_hash'):
                        entity['citation'].content_hash = raw_doc.metadata.get('commit_hash')
                    
                    all_entities.append(entity)
                    parser_extracted_names.add(symbol.name.lower())
                    
                    full_name = symbol.full_name or symbol.get_qualified_name()
                    if full_name:
                        symbol_name_to_entity_id[full_name] = entity['id']
                
                # Convert relationships
                for rel in parse_result.relationships:
                    parser_relationships.append(
                        _parser_relationship_to_dict(rel, source_toolkit)
                    )
                
                # Add containment edges from parent_symbol
                containment_count = 0
                for symbol in parse_result.symbols:
                    if symbol.parent_symbol:
                        child_name = symbol.full_name or symbol.get_qualified_name()
                        parent_name = symbol.parent_symbol
                        
                        child_id = symbol_name_to_entity_id.get(child_name)
                        parent_id = symbol_name_to_entity_id.get(parent_name)
                        
                        if child_id and parent_id:
                            parser_relationships.append({
                                'source_id': parent_id,
                                'target_id': child_id,
                                'relation_type': 'contains',
                                'properties': {
                                    'source': 'parser',
                                    'source_toolkit': source_toolkit,
                                    'file_path': file_path,
                                },
                                'source': 'parser',
                            })
                            containment_count += 1
                
                logger.debug(f"Parser extracted {len(all_entities)} symbols, {len(parser_relationships)} relationships from {file_path}")
                
            except Exception as e:
                logger.warning(f"Parser failed for {file_path}: {e}")
        
        parser_duration = time.time() - parser_start
        if parser_duration > 0.1:  # Only log if > 100ms
            logger.info(f"⏱️ [TIMING] Parser: {parser_duration:.3f}s for {file_path}")
        
        # ========== PARALLEL LLM EXTRACTION (Entity + Fact in parallel) ==========
        chunk_entities = []
        chunk_facts = []
        entity_llm_duration = 0.0
        fact_llm_duration = 0.0
        
        # Build chunk metadata for line number adjustment
        chunk_offsets = []
        for chunk in chunks:
            start_line = chunk.metadata.get('start_line') or chunk.metadata.get('line_start') or 1
            chunk_offsets.append(start_line)
        
        # Helper functions for parallel execution
        def extract_entities():
            """Extract entities from chunks - runs in parallel thread."""
            entities = []
            if not self._entity_extractor or not chunks:
                return entities, 0.0
            
            start = time.time()
            try:
                extracted, _ = self._entity_extractor.extract_batch(
                    chunks, schema=schema, skip_on_error=True
                )
                
                for entity in extracted:
                    entity_name = entity.get('name', '').lower()
                    raw_type = entity.get('type', 'unknown')
                    normalized_type = normalize_entity_type(raw_type)
                    
                    # Skip if parser already extracted this
                    code_layer_types = {'class', 'function', 'method', 'module', 'interface', 
                                       'constant', 'variable', 'import', 'property', 'field'}
                    if (entity_name in parser_extracted_names and 
                        normalized_type in code_layer_types):
                        continue
                    
                    entity_id = self._generate_entity_id(
                        normalized_type,
                        entity.get('name', 'unnamed'),
                        file_path
                    )
                    
                    citation = Citation(
                        file_path=file_path,
                        line_start=entity.get('line_start'),
                        line_end=entity.get('line_end'),
                        source_toolkit=source_toolkit,
                        doc_id=f"{source_toolkit}://{file_path}",
                        content_hash=raw_doc.metadata.get('commit_hash'),
                    )
                    
                    entities.append({
                        'id': entity_id,
                        'name': entity.get('name', 'unnamed'),
                        'type': normalized_type,
                        'citation': citation,
                        'properties': {
                            k: v for k, v in entity.items()
                            if k not in ('id', 'name', 'type', 'content', 'text', 'line_start', 'line_end')
                        },
                        'source_doc': chunks[0] if chunks else None,
                        'source': 'llm',
                    })
            except Exception as e:
                logger.warning(f"Batched entity extraction failed for {file_path}: {e}")
            
            return entities, time.time() - start
        
        def extract_facts():
            """Extract facts from chunks - runs in parallel thread."""
            facts = []
            if not self.llm or not chunks:
                return facts, 0.0
            
            start = time.time()
            try:
                fact_extractor = FactExtractor(self.llm)
                is_code = _is_code_file(file_path) or _is_code_like_file(file_path)
                
                if is_code:
                    all_facts = fact_extractor.extract_batch_code(chunks)
                else:
                    all_facts = fact_extractor.extract_batch(chunks)
                
                for fact in all_facts:
                    fact_id = self._generate_entity_id(
                        'fact',
                        f"{fact.get('fact_type', 'unknown')}_{fact.get('subject', 'unknown')[:30]}",
                        file_path
                    )
                    
                    citation = Citation(
                        file_path=file_path,
                        line_start=fact.get('line_start'),
                        line_end=fact.get('line_end'),
                        source_toolkit=source_toolkit,
                        doc_id=f"{source_toolkit}://{file_path}",
                        content_hash=raw_doc.metadata.get('commit_hash'),
                    )
                    
                    facts.append({
                        'id': fact_id,
                        'name': fact.get('subject', 'unknown fact'),
                        'type': 'fact',
                        'citation': citation,
                        'properties': {
                            'fact_type': fact.get('fact_type'),
                            'subject': fact.get('subject'),
                            'predicate': fact.get('predicate'),
                            'object': fact.get('object'),
                            'confidence': fact.get('confidence', 0.8),
                        },
                        'source_doc': chunks[0] if chunks else None,
                        'source': 'llm_fact',
                    })
            except Exception as e:
                logger.warning(f"Batched fact extraction failed for {file_path}: {e}")
            
            return facts, time.time() - start
        
        # Run entity and fact extraction in PARALLEL (skip for trivial files)
        llm_start = time.time()
        if chunks and not skip_llm:
            with ThreadPoolExecutor(max_workers=2) as executor:
                entity_future = executor.submit(extract_entities)
                fact_future = executor.submit(extract_facts)
                
                chunk_entities, entity_llm_duration = entity_future.result()
                chunk_facts, fact_llm_duration = fact_future.result()
            
            llm_total = time.time() - llm_start
            logger.info(f"⏱️ [TIMING] LLM parallel: {llm_total:.3f}s (entity: {entity_llm_duration:.3f}s, fact: {fact_llm_duration:.3f}s, {len(chunks)} chunks) for {Path(file_path).name}")
        elif skip_llm:
            logger.info(f"⏱️ [TIMING] LLM skipped ({skip_reason}) for {Path(file_path).name}")
        
        # ========== FILE-LEVEL DEDUPLICATION ==========
        # Deduplicate entities by (type, name)
        seen_entities = {}
        for entity in chunk_entities:
            key = (entity['type'], entity['name'].lower())
            if key not in seen_entities:
                seen_entities[key] = entity
            else:
                # Merge properties, keep first citation
                existing = seen_entities[key]
                for prop_key, prop_value in entity.get('properties', {}).items():
                    if prop_key not in existing.get('properties', {}):
                        existing.setdefault('properties', {})[prop_key] = prop_value
        
        # Deduplicate facts by (fact_type, subject)
        seen_facts = {}
        for fact in chunk_facts:
            key = (fact['properties'].get('fact_type'), fact['name'].lower())
            if key not in seen_facts:
                seen_facts[key] = fact
            else:
                # Keep higher confidence
                existing = seen_facts[key]
                if fact['properties'].get('confidence', 0) > existing['properties'].get('confidence', 0):
                    seen_facts[key] = fact
        
        # Combine: parser entities + deduplicated chunk entities + deduplicated facts
        all_entities.extend(seen_entities.values())
        all_entities.extend(seen_facts.values())
        
        # ========== CREATE FILE-LEVEL NODE ==========
        # File node acts as a container for all entities/facts from this file
        file_name = Path(file_path).name
        file_ext = Path(file_path).suffix.lower()
        
        # Determine file type based on extension
        file_type = 'file'
        if file_ext in {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.kt', '.swift', '.cs', '.c', '.cpp', '.h'}:
            file_type = 'source_file'
        elif file_ext in {'.md', '.rst', '.txt'}:
            file_type = 'document_file'
        elif file_ext in {'.yml', '.yaml', '.json', '.toml', '.ini', '.cfg'}:
            file_type = 'config_file'
        elif file_ext in {'.html', '.css', '.scss', '.less'}:
            file_type = 'web_file'
        
        file_entity_id = self._generate_entity_id('file', file_path, file_path)
        
        file_citation = Citation(
            file_path=file_path,
            line_start=1,
            line_end=raw_doc.page_content.count('\n') + 1,
            source_toolkit=source_toolkit,
            doc_id=f"{source_toolkit}://{file_path}",
            content_hash=content_hash,
        )
        
        # Count entities by category for file properties
        code_entity_count = sum(1 for e in all_entities if e['type'] in {'class', 'function', 'method', 'module', 'interface'})
        fact_count = sum(1 for e in all_entities if e['type'] == 'fact')
        other_entity_count = len(all_entities) - code_entity_count - fact_count
        
        file_entity = {
            'id': file_entity_id,
            'name': file_name,
            'type': file_type,
            'citation': file_citation,
            'properties': {
                'full_path': file_path,
                'extension': file_ext,
                'line_count': raw_doc.page_content.count('\n') + 1,
                'size_bytes': len(raw_doc.page_content.encode('utf-8')),
                'content_hash': content_hash,
                'entity_count': len(all_entities),
                'code_entity_count': code_entity_count,
                'fact_count': fact_count,
                'other_entity_count': other_entity_count,
            },
            'source': 'parser',
        }
        
        # Add file entity to the beginning (it's the container)
        all_entities.insert(0, file_entity)
        
        # Create DEFINED_IN relationships from all entities to file
        for entity in all_entities[1:]:  # Skip the file entity itself
            parser_relationships.append({
                'source_id': entity['id'],
                'target_id': file_entity_id,
                'relation_type': 'defined_in',
                'properties': {
                    'source': 'parser',
                    'source_toolkit': source_toolkit,
                },
            })
        
        file_total_time = (time.time() - parser_start)
        logger.info(f"⏱️ [TIMING] File total: {file_total_time:.3f}s (parser: {parser_duration:.3f}s, llm_max: {max(entity_llm_duration, fact_llm_duration):.3f}s) for {Path(file_path).name}")
        logger.debug(f"File {file_path}: {len(all_entities)} total entities ({len(seen_entities)} from LLM, {len(seen_facts)} facts)")
        
        return all_entities, parser_relationships, content_hash

    def _extract_relations_from_file(
        self,
        file_path: str,
        file_entities: List[Dict[str, Any]],
        all_entity_dicts: List[Dict[str, Any]],
        schema: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Extract relations from entities in a single file with retry logic.
        
        Args:
            file_path: Path to the file being processed
            file_entities: Entities from this file
            all_entity_dicts: All graph entities for ID resolution
            schema: Optional schema to guide extraction
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            Tuple of (relations_list, error_message)
            error_message is None on success
        """
        # Use first entity's doc for context
        doc = file_entities[0].get('source_doc')
        if not doc or not doc.page_content:
            # Try to reload content from file if source_doc is missing
            # This happens when resuming from checkpoint (source_doc isn't serialized)
            try:
                if file_path and Path(file_path).exists():
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    doc = Document(page_content=content, metadata={'file_path': file_path})
                    logger.debug(f"Reloaded content from file: {file_path} ({len(content)} chars)")
                else:
                    # Can't reload - return empty (no relations can be extracted without content)
                    logger.debug(f"Cannot reload content for relation extraction: {file_path}")
                    return [], None  # Return empty but not an error
            except Exception as e:
                logger.warning(f"Failed to reload content from {file_path}: {e}")
                return [], None  # Return empty but not an error
        
        # Convert to format expected by relation extractor
        entity_dicts = [
            {'id': e['id'], 'name': e['name'], 'type': e['type'], **e.get('properties', {})}
            for e in file_entities
        ]
        
        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(max_retries):
            try:
                file_relations = self._relation_extractor.extract(
                    doc, entity_dicts, schema=schema, confidence_threshold=0.5,
                    all_entities=all_entity_dicts
                )
                
                # Add source tracking to each relation
                source_toolkit = file_entities[0].get('source_toolkit') if file_entities else None
                for rel in file_relations:
                    if source_toolkit:
                        if 'properties' not in rel:
                            rel['properties'] = {}
                        rel['properties']['source_toolkit'] = source_toolkit
                        rel['properties']['discovered_in_file'] = file_path
                
                return file_relations, None
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Relation extraction failed for '{file_path}' "
                    f"(attempt {attempt + 1}/{max_retries}): {e}"
                )
                
                # Exponential backoff: 1s, 2s, 4s
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
        
        # All retries failed
        logger.error(f"Failed to extract relations from '{file_path}' after {max_retries} attempts: {last_error}")
        return [], f"Failed after {max_retries} attempts: {last_error}"
    
    def _extract_relations(
        self, 
        entities: List[Dict[str, Any]],
        schema: Optional[Dict] = None,
        all_graph_entities: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract relations between entities in parallel with robust error handling.
        
        Uses ThreadPoolExecutor to process multiple files concurrently, with automatic
        retry logic for failed extractions. Progress is reported as tasks complete.
        
        Args:
            entities: New entities to extract relations from
            schema: Optional schema to guide extraction
            all_graph_entities: All entities in graph (for ID resolution across sources)
            
        Returns:
            List of extracted relations
        """
        if not self._relation_extractor or len(entities) < 2:
            return []
        
        extract_rel_start = time.time()
        relations = []
        failed_files = []
        
        # Build ID lookup from ALL graph entities (enables cross-source relations)
        all_entities_for_lookup = all_graph_entities or entities
        
        # Group entities by file for relation extraction
        by_file: Dict[str, List] = {}
        for ent in entities:
            citation = ent.get('citation')
            if isinstance(citation, dict):
                fpath = citation.get('file_path', '')
            elif hasattr(citation, 'file_path'):
                fpath = citation.file_path
            else:
                fpath = ent.get('file_path', '')
            
            if not fpath:
                continue
                
            if fpath not in by_file:
                by_file[fpath] = []
            by_file[fpath].append(ent)
        
        # Filter files with enough entities for relation extraction
        files_to_process = [(fp, ents) for fp, ents in by_file.items() if len(ents) >= 2]
        total_files = len(files_to_process)
        
        if total_files == 0:
            return []
        
        # Prepare all_entity_dicts for cross-source ID resolution
        # Use all_graph_entities if provided, otherwise use the entities we're processing
        all_entity_dicts = [
            {'id': e.get('id'), 'name': e.get('name'), 'type': e.get('type')}
            for e in all_entities_for_lookup
            if e.get('id')
        ]
        
        # Use ThreadPoolExecutor for parallel relation extraction
        completed_files = 0
        
        with ThreadPoolExecutor(max_workers=self.max_parallel_extractions) as executor:
            # Submit all extraction tasks
            future_to_file = {
                executor.submit(
                    self._extract_relations_from_file,
                    file_path,
                    file_entities,
                    all_entity_dicts,
                    schema
                ): (file_path, file_entities)
                for file_path, file_entities in files_to_process
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_file):
                file_path, file_entities = future_to_file[future]
                completed_files += 1
                
                try:
                    file_relations, error = future.result()
                    
                    if error:
                        # Log failed file but continue processing
                        failed_files.append({
                            'file_path': file_path,
                            'error': error,
                            'entity_count': len(file_entities)
                        })
                    else:
                        relations.extend(file_relations)
                    
                except Exception as e:
                    # Unexpected error (shouldn't happen since we catch in _extract_relations_from_file)
                    logger.error(f"Unexpected error processing '{file_path}': {e}")
                    failed_files.append({
                        'file_path': file_path,
                        'error': f"Unexpected error: {str(e)}",
                        'entity_count': len(file_entities)
                    })
                
                # Log progress periodically
                if completed_files % 10 == 0 or completed_files == total_files or completed_files == 1:
                    pct = (completed_files / total_files) * 100
                    status_msg = f"🔗 Relations: {completed_files}/{total_files} files ({pct:.0f}%) | Found {len(relations)} relations"
                    if failed_files:
                        status_msg += f" | {len(failed_files)} files failed"
                    self._log_progress(status_msg, "relations")
        
        # Log summary of failures if any
        if failed_files:
            self._log_progress(
                f"⚠️ Relation extraction failed for {len(failed_files)}/{total_files} files. "
                f"Successfully extracted {len(relations)} relations from {total_files - len(failed_files)} files.",
                "relations"
            )
            # Log first few failures for debugging
            for failed in failed_files[:3]:
                logger.warning(
                    f"Failed to extract relations from '{failed['file_path']}' "
                    f"({failed['entity_count']} entities): {failed['error']}"
                )
        
        file_rel_duration = time.time() - extract_rel_start
        logger.info(f"⏱️ [TIMING] Per-file relation extraction: {file_rel_duration:.3f}s for {total_files} files")
        
        # Phase 2: Extract cross-file relations (imports, dependencies between modules)
        cross_file_start = time.time()
        cross_file_relations = self._extract_cross_file_relations(entities, all_entity_dicts, by_file)
        if cross_file_relations:
            relations.extend(cross_file_relations)
            self._log_progress(
                f"🔗 Cross-file: Found {len(cross_file_relations)} inter-module relations",
                "relations"
            )
        cross_file_duration = time.time() - cross_file_start
        logger.info(f"⏱️ [TIMING] Cross-file relation extraction: {cross_file_duration:.3f}s")
        
        total_rel_duration = time.time() - extract_rel_start
        logger.info(f"⏱️ [TIMING] _extract_relations total: {total_rel_duration:.3f}s ({len(relations)} relations)")
        
        return relations
    
    def _extract_cross_file_relations(
        self,
        entities: List[Dict[str, Any]],
        all_entity_dicts: List[Dict[str, Any]],
        by_file: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Extract cross-file relationships by analyzing imports, references, and dependencies.
        
        Uses the patterns module for extensible, language-specific pattern matching.
        Patterns cover:
        - Import statements (JS/TS, Python, Java, C#, Go, Ruby, Rust, PHP, etc.)
        - Documentation links (Markdown, Wiki, HTML, RST)
        - Text citations and references ("see X", "@see X", etc.)
        - Inheritance patterns
        - Entity name mentions in content
        
        Args:
            entities: All entities to analyze
            all_entity_dicts: Entity dictionaries for lookup
            by_file: Entities grouped by file path
            
        Returns:
            List of cross-file relations
        """
        from .patterns import get_patterns_for_file, PatternCategory
        import re
        
        cross_relations = []
        
        # Build lookup tables
        entity_by_name: Dict[str, Dict] = {}
        entity_by_id: Dict[str, Dict] = {}
        file_to_entities: Dict[str, List[Dict]] = {}
        module_to_file: Dict[str, str] = {}
        
        # For entity mention matching
        significant_entities: List[Tuple[str, Dict]] = []
        
        for ent in entities:
            name = ent.get('name', '')
            ent_id = ent.get('id', '')
            
            if name:
                name_lower = name.lower()
                entity_by_name[name_lower] = ent
                entity_by_name[name] = ent
                
                # Track significant entities for mention detection
                ent_type = ent.get('type', '').lower()
                if ent_type in ('class', 'component', 'service', 'module', 'api', 'endpoint',
                               'feature', 'epic', 'requirement', 'interface', 'schema', 'table'):
                    if len(name) >= 3:  # Min 3 chars to reduce noise
                        significant_entities.append((name_lower, ent))
                        
            if ent_id:
                entity_by_id[ent_id] = ent
            
            # Build file -> entities and module -> file mappings
            citation = ent.get('citation')
            if citation:
                file_path = citation.get('file_path', '') if isinstance(citation, dict) else getattr(citation, 'file_path', '')
                if file_path:
                    if file_path not in file_to_entities:
                        file_to_entities[file_path] = []
                    file_to_entities[file_path].append(ent)
                    
                    p = Path(file_path)
                    stem = p.stem
                    module_to_file[stem.lower()] = file_path
                    if stem.lower() == 'index':
                        module_to_file[p.parent.name.lower()] = file_path
        
        # Sort significant entities by length for greedy matching
        significant_entities.sort(key=lambda x: len(x[0]), reverse=True)
        
        # ========================================================================
        # PHASE 1: Pattern-based extraction from file content
        # ========================================================================
        
        for file_path, file_ents in by_file.items():
            if not file_ents:
                continue
            
            # Read file content
            file_content = ""
            try:
                for ent in file_ents:
                    doc = ent.get('source_doc')
                    if doc and hasattr(doc, 'page_content') and doc.page_content:
                        file_content = doc.page_content
                        break
                
                if not file_content and Path(file_path).exists():
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        file_content = f.read()
            except Exception:
                pass
            
            if not file_content:
                continue
            
            # Get source entity for this file
            source_ent = next(
                (e for e in file_ents if e.get('type', '').lower() in 
                 ('module', 'component', 'class', 'file', 'page', 'document')),
                file_ents[0] if file_ents else None
            )
            if not source_ent:
                continue
            
            source_id = source_ent.get('id')
            
            # Get patterns for this file type
            patterns = get_patterns_for_file(file_path)
            
            # Apply each pattern
            for pattern in patterns:
                matches = pattern.match(file_content)
                
                for match_value in matches:
                    if not match_value or len(match_value) < 2:
                        continue
                    
                    # Try to resolve match to an entity
                    target_ent = None
                    match_lower = match_value.lower()
                    
                    # For imports, try module-to-file mapping
                    if pattern.category == PatternCategory.IMPORT:
                        target_file = module_to_file.get(match_lower)
                        if target_file and target_file != file_path:
                            target_ents = file_to_entities.get(target_file, [])
                            target_ent = next(
                                (e for e in target_ents if e.get('type', '').lower() in 
                                 ('module', 'component', 'class', 'file')),
                                target_ents[0] if target_ents else None
                            )
                    
                    # For links/citations, try entity name lookup
                    if pattern.category in (PatternCategory.LINK, PatternCategory.CITATION,
                                           PatternCategory.INHERITANCE, PatternCategory.TYPE_REF):
                        # Skip external URLs
                        if match_value.startswith(('http://', 'https://', '#')):
                            continue
                        
                        # Try direct name match
                        target_ent = entity_by_name.get(match_lower) or entity_by_name.get(match_value)
                        
                        # Try as file path
                        if not target_ent:
                            target_file = module_to_file.get(Path(match_value).stem.lower())
                            if target_file:
                                target_ents = file_to_entities.get(target_file, [])
                                target_ent = target_ents[0] if target_ents else None
                    
                    if target_ent and source_id != target_ent.get('id'):
                        target_citation = target_ent.get('citation')
                        target_file = ''
                        if target_citation:
                            target_file = (target_citation.get('file_path', '') 
                                         if isinstance(target_citation, dict) 
                                         else getattr(target_citation, 'file_path', ''))
                        
                        if target_file != file_path:
                            cross_relations.append({
                                'source_id': source_id,
                                'target_id': target_ent.get('id'),
                                'type': pattern.relation_type.value,
                                'properties': {
                                    'source_file': file_path,
                                    'target_file': target_file,
                                    'discovered_by': f'pattern:{pattern.name}',
                                    'matched_value': match_value
                                },
                                'confidence': pattern.confidence
                            })
            
            # --- Entity mention detection ---
            content_lower = file_content.lower()
            for name_lower, target_ent in significant_entities:
                if target_ent.get('id') == source_id:
                    continue
                
                if name_lower in content_lower:
                    # Verify word boundary
                    if re.search(r'\b' + re.escape(name_lower) + r'\b', content_lower):
                        target_citation = target_ent.get('citation')
                        target_file = ''
                        if target_citation:
                            target_file = (target_citation.get('file_path', '') 
                                         if isinstance(target_citation, dict) 
                                         else getattr(target_citation, 'file_path', ''))
                        
                        if target_file and target_file != file_path:
                            cross_relations.append({
                                'source_id': source_id,
                                'target_id': target_ent.get('id'),
                                'type': 'MENTIONS',
                                'properties': {
                                    'source_file': file_path,
                                    'target_file': target_file,
                                    'discovered_by': 'content_mention',
                                    'mentioned_name': target_ent.get('name', '')
                                },
                                'confidence': 0.7
                            })
        
        # ========================================================================
        # PHASE 1.5: AST-based analysis (when available)
        # ========================================================================
        # Uses deepwiki parsers for more accurate code analysis
        
        try:
            from .patterns import is_ast_available, extract_ast_cross_file_relations
            
            if is_ast_available():
                # Collect file contents for AST analysis
                ast_file_contents: Dict[str, str] = {}
                ast_file_paths = []
                
                for file_path, file_ents in by_file.items():
                    # Only process code files that benefit from AST
                    ext = Path(file_path).suffix.lower()
                    if ext in ('.py', '.js', '.jsx', '.ts', '.tsx', '.java'):
                        # Get content from entity or file
                        file_content = ""
                        try:
                            for ent in file_ents:
                                doc = ent.get('source_doc')
                                if doc and hasattr(doc, 'page_content') and doc.page_content:
                                    file_content = doc.page_content
                                    break
                            
                            if not file_content and Path(file_path).exists():
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    file_content = f.read()
                        except Exception:
                            pass
                        
                        if file_content:
                            ast_file_contents[file_path] = file_content
                            ast_file_paths.append(file_path)
                
                if ast_file_paths:
                    # Extract AST-based relations
                    ast_relations = extract_ast_cross_file_relations(
                        ast_file_paths,
                        ast_file_contents,
                        entities
                    )
                    
                    # Convert to standard format and add
                    for ast_rel in ast_relations:
                        source_name = ast_rel.get('source_entity', '')
                        target_name = ast_rel.get('target_entity', '')
                        
                        # Resolve to entity IDs
                        source_ent = entity_by_name.get(source_name.lower()) or entity_by_name.get(source_name)
                        target_ent = entity_by_name.get(target_name.lower()) or entity_by_name.get(target_name)
                        
                        if source_ent and target_ent and source_ent.get('id') != target_ent.get('id'):
                            cross_relations.append({
                                'source_id': source_ent.get('id'),
                                'target_id': target_ent.get('id'),
                                'type': ast_rel.get('relationship_type', 'REFERENCES').upper(),
                                'properties': {
                                    'source_file': ast_rel.get('metadata', {}).get('source_file', ''),
                                    'target_file': ast_rel.get('metadata', {}).get('target_file', ''),
                                    'discovered_by': 'ast_analysis',
                                    'line': ast_rel.get('metadata', {}).get('line', 0)
                                },
                                'confidence': ast_rel.get('relationship_strength', 0.95)
                            })
                    
                    if ast_relations:
                        self._log_progress(
                            f"🌳 AST analysis found {len(ast_relations)} relations",
                            "relations"
                        )
        except ImportError:
            pass  # AST adapter not available
        except Exception as e:
            import traceback
            self._log_progress(f"AST analysis failed: {e}", "debug")
        
        # ========================================================================
        # PHASE 2: Entity property analysis
        # ========================================================================
        
        def to_list(val):
            if isinstance(val, str):
                return [val] if val else []
            if isinstance(val, list):
                return val
            return []
        
        for ent in entities:
            props = ent.get('properties', {})
            ent_id = ent.get('id', '')
            
            citation = ent.get('citation')
            source_file = ''
            if citation:
                source_file = (citation.get('file_path', '') 
                             if isinstance(citation, dict) 
                             else getattr(citation, 'file_path', ''))
            
            # Property-based references
            all_refs = [
                (to_list(props.get('imports', [])), 'IMPORTS'),
                (to_list(props.get('dependencies', [])), 'DEPENDS_ON'),
                (to_list(props.get('extends', props.get('parent_class', ''))), 'EXTENDS'),
                (to_list(props.get('implements', [])), 'IMPLEMENTS'),
                (to_list(props.get('uses', props.get('calls', []))), 'USES'),
                (to_list(props.get('references', props.get('links', []))), 'REFERENCES'),
            ]
            
            for ref_list, rel_type in all_refs:
                for ref in ref_list:
                    if not ref:
                        continue
                    
                    ref_lower = ref.lower() if isinstance(ref, str) else str(ref).lower()
                    target_ent = entity_by_name.get(ref_lower) or entity_by_name.get(ref)
                    
                    if not target_ent and ('/' in ref_lower or '.' in ref_lower):
                        clean_ref = ref_lower.split('/')[-1].split('.')[-1]
                        target_ent = entity_by_name.get(clean_ref)
                    
                    if target_ent and target_ent.get('id') != ent_id:
                        target_citation = target_ent.get('citation')
                        target_file = ''
                        if target_citation:
                            target_file = (target_citation.get('file_path', '') 
                                         if isinstance(target_citation, dict) 
                                         else getattr(target_citation, 'file_path', ''))
                        
                        if target_file and source_file and target_file != source_file:
                            cross_relations.append({
                                'source_id': ent_id,
                                'target_id': target_ent.get('id'),
                                'type': rel_type,
                                'properties': {
                                    'source_file': source_file,
                                    'target_file': target_file,
                                    'discovered_by': 'property_analysis',
                                    'reference_name': ref
                                },
                                'confidence': 0.9
                            })
        
        # Deduplicate
        seen = set()
        unique_relations = []
        for rel in cross_relations:
            key = (rel['source_id'], rel['target_id'], rel['type'])
            if key not in seen:
                seen.add(key)
                unique_relations.append(rel)
        
        return unique_relations
    
    def run(
        self,
        source: str,
        branch: Optional[str] = None,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
        extract_relations: bool = True,
        resume: bool = True,
        max_documents: Optional[int] = None,
        **loader_kwargs
    ) -> IngestionResult:
        """
        Run the full ingestion pipeline with checkpoint support for resumability.
        
        Args:
            source: Name of source toolkit (must be in source_toolkits)
            branch: Branch to analyze (optional, uses default if not specified)
            whitelist: File patterns to include (e.g., ['*.py', '*.js'])
            blacklist: File patterns to exclude (e.g., ['*test*', '*vendor*'])
            extract_relations: Whether to extract relations between entities
            resume: If True, try to resume from last checkpoint
            max_documents: Maximum number of documents to process (for testing)
            **loader_kwargs: Additional arguments for the toolkit's loader
            
        Returns:
            IngestionResult with statistics and any errors
        """
        import time
        start_time = time.time()
        result = IngestionResult(source=source)
        
        # Validate source toolkit
        if source not in self.source_toolkits:
            available = list(self.source_toolkits.keys()) if self.source_toolkits else ['none']
            result.success = False
            result.errors.append(f"Toolkit '{source}' not found. Available: {', '.join(available)}")
            return result
        
        toolkit = self.source_toolkits[source]
        
        # Check for loader method
        if not hasattr(toolkit, 'loader'):
            result.success = False
            result.errors.append(f"Toolkit '{source}' does not have a loader method")
            return result
        
        # Ensure extractors are initialized
        if not self._init_extractors():
            result.success = False
            result.errors.append("LLM not configured - cannot extract entities")
            return result
        
        # Try to load existing checkpoint if resume is enabled
        checkpoint = None
        is_incremental_update = False
        if resume:
            checkpoint = self._load_checkpoint(source)
            if checkpoint:
                if checkpoint.completed:
                    # Completed checkpoint - use for incremental update
                    is_incremental_update = True
                    num_tracked = len(checkpoint.file_hashes)
                    self._log_progress(
                        f"📋 Incremental update: tracking {num_tracked} files for changes",
                        "incremental"
                    )
                    # Reset counters for new run but keep file hashes
                    checkpoint.completed = False
                    checkpoint.phase = "extract"
                    checkpoint.pending_entities = []
                    checkpoint.errors = []
                else:
                    # Incomplete checkpoint - resume from failure
                    self._log_progress(
                        f"📋 Resuming from checkpoint: {checkpoint.documents_processed} docs already processed",
                        "resume"
                    )
                    result.resumed_from_checkpoint = True
                    # Restore progress from checkpoint
                    result.documents_processed = checkpoint.documents_processed
                    result.entities_added = checkpoint.entities_added
        
        # Create new checkpoint if no existing one
        if not checkpoint:
            checkpoint = IngestionCheckpoint.create(
                source=source,
                branch=branch,
                whitelist=whitelist,
                blacklist=blacklist,
                extract_relations=extract_relations,
            )
        
        self._current_checkpoint = checkpoint
        
        self._log_progress(f"🚀 Starting ingestion from {source}", "start")
        
        # Build loader kwargs
        loader_args = {**loader_kwargs}
        if branch:
            loader_args['branch'] = branch
        if whitelist:
            loader_args['whitelist'] = whitelist
        if blacklist:
            loader_args['blacklist'] = blacklist
        
        if loader_args:
            params_str = ", ".join(f"{k}={v}" for k, v in loader_args.items() if v is not None)
            self._log_progress(f"📋 Loader params: {params_str}", "config")
        
        try:
            # ========== STREAMING APPROACH ==========
            # Read files once, create raw doc + chunks on the fly
            # Process in batches to limit memory usage
            
            self._log_progress(f"📥 Fetching documents from {source}...", "fetch")
            
            # Note: We don't pre-count files to avoid iterating twice
            # The toolkit's loader() will log progress as it goes
            
            # Import chunker for on-the-fly chunking
            try:
                from alita_sdk.tools.chunkers.universal_chunker import chunk_single_document
                from alita_sdk.tools.chunkers.code.codeparser import parse_code_files_for_db
                from langchain.text_splitter import RecursiveCharacterTextSplitter
                has_chunker = True
                
                # Create text splitter for non-code files
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=100,
                    length_function=len,
                )
                
                # Code extensions that use tree-sitter
                CODE_EXTENSIONS = {
                    '.py', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx',
                    '.java', '.kt', '.rs', '.go', '.cpp', '.c', '.cs', 
                    '.hs', '.rb', '.scala', '.lua'
                }
                
                def chunk_document_direct(doc: Document) -> List[Document]:
                    """Chunk a single document directly without buffering."""
                    file_path = doc.metadata.get('file_path', '')
                    ext = Path(file_path).suffix.lower()
                    
                    if ext in CODE_EXTENSIONS:
                        # Use code parser directly
                        try:
                            chunks = list(parse_code_files_for_db([{
                                'file_name': file_path,
                                'file_content': doc.page_content,
                                'commit_hash': doc.metadata.get('commit_hash', ''),
                            }]))
                            # Ensure file_path is preserved
                            for chunk in chunks:
                                if 'file_path' not in chunk.metadata:
                                    chunk.metadata['file_path'] = file_path
                            return chunks if chunks else [doc]
                        except Exception as e:
                            logger.debug(f"Code chunking failed for {file_path}: {e}")
                            return [doc]
                    else:
                        # Use text splitter
                        try:
                            chunks = text_splitter.split_documents([doc])
                            for idx, chunk in enumerate(chunks, 1):
                                chunk.metadata['chunk_id'] = idx
                            return chunks if chunks else [doc]
                        except Exception:
                            return [doc]
                
            except ImportError:
                has_chunker = False
                chunk_document_direct = None
                logger.warning("Chunkers not available, using raw documents")
            
            # Get schema
            schema = self._knowledge_graph.get_schema()
            all_entities = list(checkpoint.pending_entities) if checkpoint.pending_entities else []
            all_parser_relationships = []  # Collect parser-extracted relationships
            
            checkpoint.phase = "extract"
            self._log_progress(
                f"🔍 Extracting entities (parallel batches of {self.batch_size}, "
                f"max {self.max_parallel_extractions} concurrent)...",
                "extract"
            )
            
            # ========== STREAMING FILE PROCESSING ==========
            # Process files one at a time, creating chunks on-the-fly
            file_batch = []
            total_batches_processed = 0
            files_seen = 0
            streaming_start = time.time()
            total_chunk_time = 0.0
            
            # Stream raw documents (read once)
            loader_args['chunked'] = False
            for raw_doc in toolkit.loader(**loader_args):
                file_path = (raw_doc.metadata.get('file_path') or 
                            raw_doc.metadata.get('file_name') or 
                            raw_doc.metadata.get('source', 'unknown'))
                files_seen += 1
                
                # Check document limit (for testing)
                if max_documents and result.documents_processed >= max_documents:
                    # Process remaining batch if any
                    if file_batch:
                        self._process_file_batch_and_update_graph(
                            file_batch, {}, source, schema, checkpoint, result, 
                            all_entities, all_parser_relationships, is_incremental_update
                        )
                    self._log_progress(
                        f"⚠️ Reached document limit ({max_documents}), stopping...",
                        "limit"
                    )
                    break
                
                # Normalize document
                normalized = self._normalize_document(raw_doc, source)
                if not normalized:
                    continue
                
                # For incremental updates, check if file changed
                if is_incremental_update:
                    content_hash = hashlib.sha256(normalized.page_content.encode()).hexdigest()
                    if not checkpoint.has_file_changed(file_path, content_hash):
                        result.documents_skipped += 1
                        continue
                    else:
                        # File has changed - remove old entities before reprocessing
                        removed = self._knowledge_graph.remove_entities_by_file(file_path)
                        if removed > 0:
                            result.entities_removed += removed
                            logger.debug(f"Removed {removed} stale entities from {file_path}")
                
                # Skip if already processed in current run (resuming from checkpoint)
                if not is_incremental_update and checkpoint.is_file_processed(file_path):
                    result.documents_skipped += 1
                    continue
                
                # Create chunks on-the-fly from this single document
                chunk_start = time.time()
                if has_chunker and chunk_document_direct:
                    # Direct chunking - no buffering overhead
                    chunks = chunk_document_direct(normalized)
                else:
                    # No chunker - use raw doc as single chunk
                    chunks = [normalized]
                chunk_time = time.time() - chunk_start
                total_chunk_time += chunk_time
                if chunk_time > 0.1:  # Log if chunking takes > 100ms
                    logger.info(f"⏱️ [TIMING] Chunking: {chunk_time:.3f}s ({len(chunks)} chunks) for {Path(file_path).name}")
                
                # Add to current batch: (file_path, chunks, raw_doc)
                file_batch.append((file_path, chunks, normalized))
                
                # Process batch when it reaches batch_size
                if len(file_batch) >= self.batch_size:
                    batch_num = total_batches_processed + 1
                    self._log_progress(
                        f"⚡ Processing batch {batch_num} ({len(file_batch)} files, file #{files_seen})...",
                        "batch"
                    )
                    
                    self._process_file_batch_and_update_graph(
                        file_batch, {}, source, schema, checkpoint, result, 
                        all_entities, all_parser_relationships, is_incremental_update
                    )
                    
                    total_batches_processed += 1
                    file_batch = []  # Reset batch
                    
                    # Save checkpoint after each batch
                    checkpoint.documents_processed = result.documents_processed
                    checkpoint.entities_added = result.entities_added
                    self._save_checkpoint(checkpoint)
                    self._auto_save()
                    
                    self._log_progress(
                        f"📄 Processed {result.documents_processed} files | "
                        f"📊 {result.entities_added} entities | 💾 Checkpoint saved",
                        "progress"
                    )
            
            # Process remaining files in final batch
            if file_batch:
                batch_num = total_batches_processed + 1
                self._log_progress(
                    f"⚡ Processing final batch {batch_num} ({len(file_batch)} files)...",
                    "batch"
                )
                self._process_file_batch_and_update_graph(
                    file_batch, {}, source, schema, checkpoint, result, 
                    all_entities, all_parser_relationships, is_incremental_update
                )
            
            streaming_duration = time.time() - streaming_start
            logger.info(f"⏱️ [TIMING] Streaming phase complete: {streaming_duration:.3f}s total, {total_chunk_time:.3f}s chunking, {total_batches_processed + 1} batches")
            
            # Report skipped files before relation extraction
            if result.documents_skipped > 0:
                self._log_progress(
                    f"⏭️ Skipped {result.documents_skipped} unchanged files",
                    "progress"
                )
            
            # Update checkpoint before relation extraction
            checkpoint.documents_processed = result.documents_processed
            checkpoint.entities_added = result.entities_added
            checkpoint.pending_entities = [
                {'id': e['id'], 'name': e['name'], 'type': e['type'], 
                 'file_path': (e['citation'].file_path if hasattr(e.get('citation'), 'file_path') 
                              else e.get('citation', {}).get('file_path', e.get('file_path', ''))),
                 'properties': e.get('properties', {})}
                for e in all_entities
            ]
            self._save_checkpoint(checkpoint)
            
            # Extract relations
            if extract_relations and all_entities:
                checkpoint.phase = "relations"
                self._save_checkpoint(checkpoint)
                relations_phase_start = time.time()
                
                # Get ALL entities from graph (existing + new) for relation resolution
                # This enables cross-source relations (e.g., github entities referencing confluence entities)
                graph_entities = self._knowledge_graph.get_all_entities()
                
                # ========== PARSER RELATIONSHIPS (no LLM) ==========
                # Add parser-extracted relationships directly to graph
                parser_rel_start = time.time()
                if all_parser_relationships:
                    self._log_progress(
                        f"🔗 Adding {len(all_parser_relationships)} parser-extracted relationships...",
                        "relations"
                    )
                    
                    # Build entity lookup for ID resolution
                    entity_by_name = {}
                    for e in graph_entities:
                        name_lower = e.get('name', '').lower()
                        entity_by_name[name_lower] = e.get('id')
                        # Also map full qualified names
                        full_name = e.get('properties', {}).get('full_name', '')
                        if full_name:
                            entity_by_name[full_name.lower()] = e.get('id')
                    
                    for rel in all_parser_relationships:
                        # Check for pre-resolved IDs (used for containment edges)
                        source_id = rel.get('_resolved_source_id')
                        target_id = rel.get('_resolved_target_id')
                        
                        # Fall back to name-based resolution if not pre-resolved
                        if not source_id or not target_id:
                            source_name = rel.get('source_symbol', '').lower()
                            target_name = rel.get('target_symbol', '').lower()
                            
                            source_id = source_id or entity_by_name.get(source_name)
                            target_id = target_id or entity_by_name.get(target_name)
                        
                        if source_id and target_id:
                            properties = {
                                'source_toolkit': rel.get('source_toolkit', source),
                                'confidence': rel.get('confidence', 1.0),
                                'source': 'parser',
                                'discovered_in_file': rel.get('source_file'),
                            }
                            if rel.get('is_cross_file'):
                                properties['is_cross_file'] = True
                            
                            success = self._knowledge_graph.add_relation(
                                source_id=source_id,
                                target_id=target_id,
                                relation_type=rel.get('relation_type', 'references'),
                                properties=properties
                            )
                            if success:
                                result.relations_added += 1
                
                parser_rel_duration = time.time() - parser_rel_start
                logger.info(f"⏱️ [TIMING] Parser relations: {parser_rel_duration:.3f}s for {len(all_parser_relationships)} relationships")
                
                # ========== LLM RELATIONSHIPS (semantic) ==========
                llm_rel_start = time.time()
                self._log_progress(
                    f"🔗 Extracting semantic relations from {len(all_entities)} new entities "
                    f"(graph has {len(graph_entities)} total)...",
                    "relations"
                )
                
                # Pass all graph entities for ID resolution, but only extract from new docs
                relations = self._extract_relations(all_entities, schema, all_graph_entities=graph_entities)
                
                for rel in relations:
                    # Merge source information into properties
                    properties = rel.get('properties', {})
                    if 'source_toolkit' not in properties:
                        # Fallback: add current source if not already set
                        properties['source_toolkit'] = source
                    properties['source'] = 'llm'  # Mark as LLM-extracted
                    
                    success = self._knowledge_graph.add_relation(
                        source_id=rel.get('source_id'),
                        target_id=rel.get('target_id'),
                        relation_type=rel.get('relation_type', 'RELATED_TO'),
                        properties=properties
                    )
                    if success:
                        result.relations_added += 1
                
                llm_rel_duration = time.time() - llm_rel_start
                relations_phase_duration = time.time() - relations_phase_start
                logger.info(f"⏱️ [TIMING] LLM relations: {llm_rel_duration:.3f}s")
                logger.info(f"⏱️ [TIMING] Relations phase total: {relations_phase_duration:.3f}s")
            
            # Save final graph
            self._auto_save()
            
            # Mark checkpoint as complete - keep it for incremental updates
            checkpoint.completed = True
            checkpoint.phase = "complete"
            checkpoint.relations_added = result.relations_added
            checkpoint.pending_entities = []  # Clear pending entities to save space
            self._save_checkpoint(checkpoint)
            # Note: We keep the checkpoint for incremental updates (file hash tracking)
            
            result.graph_stats = self._knowledge_graph.get_stats()
            result.duration_seconds = time.time() - start_time
            
            # Report any failed documents
            if result.failed_documents:
                self._log_progress(
                    f"⚠️ {len(result.failed_documents)} documents failed to process",
                    "warning"
                )
            
            # Build completion message
            completion_msg = (
                f"✅ Ingestion complete! {result.entities_added} entities, "
                f"{result.relations_added} relations in {result.duration_seconds:.1f}s"
            )
            if result.documents_skipped > 0:
                completion_msg += f" ({result.documents_skipped} unchanged files skipped)"
            
            self._log_progress(completion_msg, "complete")
            
        except Exception as e:
            logger.exception(f"Ingestion failed: {e}")
            result.success = False
            result.errors.append(str(e))
            result.duration_seconds = time.time() - start_time
            
            # Save checkpoint on failure for resume
            checkpoint.errors.append(str(e))
            checkpoint.documents_processed = result.documents_processed
            checkpoint.entities_added = result.entities_added
            self._save_checkpoint(checkpoint)
            self._auto_save()  # Save graph progress
            
            self._log_progress(
                f"❌ Ingestion failed. Checkpoint saved for resume. "
                f"Processed {result.documents_processed} docs before failure.",
                "error"
            )
        
        return result
    
    def run_from_generator(
        self,
        documents: Generator[Document, None, None],
        source: str = "custom",
        extract_relations: bool = True
    ) -> IngestionResult:
        """
        Run ingestion from a pre-built document generator.
        
        Use this when you have your own document source that's not
        a standard toolkit (e.g., custom loader, S3 files, etc.).
        
        Args:
            documents: Generator yielding LangChain Documents
            source: Name to identify the source in citations
            extract_relations: Whether to extract relations
            
        Returns:
            IngestionResult with statistics
        """
        import time
        start_time = time.time()
        result = IngestionResult(source=source)
        
        if not self._init_extractors():
            result.success = False
            result.errors.append("LLM not configured")
            return result
        
        self._log_progress(f"🚀 Starting ingestion from {source} generator", "start")
        
        schema = self._knowledge_graph.get_schema()
        all_entities = []
        
        try:
            for doc in documents:
                normalized = self._normalize_document(doc, source)
                if not normalized:
                    continue
                
                result.documents_processed += 1
                entities, extraction_failures = self._extract_entities_from_doc(normalized, source, schema)
                
                # Track extraction failures
                if extraction_failures:
                    for failed_path in extraction_failures:
                        if failed_path not in result.failed_documents:
                            result.failed_documents.append(failed_path)
                
                for entity in entities:
                    self._knowledge_graph.add_entity(
                        entity_id=entity['id'],
                        name=entity['name'],
                        entity_type=entity['type'],
                        citation=entity['citation'],
                        properties=entity['properties']
                    )
                    result.entities_added += 1
                    all_entities.append(entity)
                
                if result.documents_processed % 10 == 0:
                    self._log_progress(
                        f"📄 {result.documents_processed} docs | 📊 {result.entities_added} entities",
                        "progress"
                    )
            
            if extract_relations and all_entities:
                graph_entities = self._knowledge_graph.get_all_entities()
                self._log_progress(
                    f"🔗 Extracting relations from {len(all_entities)} new entities "
                    f"(graph has {len(graph_entities)} total)...",
                    "relations"
                )
                relations = self._extract_relations(all_entities, schema, all_graph_entities=graph_entities)
                
                for rel in relations:
                    # Merge source information into properties
                    properties = rel.get('properties', {})
                    if 'source_toolkit' not in properties:
                        # Add current source if not already set
                        properties['source_toolkit'] = source
                    
                    if self._knowledge_graph.add_relation(
                        source_id=rel.get('source_id'),
                        target_id=rel.get('target_id'),
                        relation_type=rel.get('relation_type', 'RELATED_TO'),
                        properties=properties
                    ):
                        result.relations_added += 1
            
            self._auto_save()
            result.graph_stats = self._knowledge_graph.get_stats()
            result.duration_seconds = time.time() - start_time
            
            self._log_progress(f"✅ Complete! {result}", "complete")
            
        except Exception as e:
            logger.exception(f"Ingestion failed: {e}")
            result.success = False
            result.errors.append(str(e))
            result.duration_seconds = time.time() - start_time
        
        return result
    
    def delta_update(
        self,
        source: str,
        file_paths: List[str],
        extract_relations: bool = True
    ) -> IngestionResult:
        """
        Perform delta update for changed files.
        
        1. Removes existing entities from the specified files
        2. Re-fetches and re-analyzes those files
        3. Adds new entities with fresh citations
        
        Args:
            source: Name of source toolkit
            file_paths: List of file paths that have changed
            extract_relations: Whether to extract relations
            
        Returns:
            IngestionResult with statistics including entities removed
        """
        import time
        start_time = time.time()
        result = IngestionResult(source=source)
        
        self._log_progress(f"🔄 Delta update for {len(file_paths)} files from {source}", "start")
        
        # Remove stale entities
        for file_path in file_paths:
            removed = self._knowledge_graph.remove_entities_by_file(file_path)
            result.entities_removed += removed
        
        self._log_progress(f"🗑️ Removed {result.entities_removed} stale entities", "cleanup")
        
        # Re-ingest the changed files
        if source not in self.source_toolkits:
            # Fall back to local file read if toolkit not available
            self._log_progress("📁 Reading files locally (toolkit not available)", "local")
            
            from pathlib import Path
            
            def local_loader():
                for file_path in file_paths:
                    try:
                        content = Path(file_path).read_text(encoding='utf-8')
                        yield Document(
                            page_content=content,
                            metadata={'file_path': file_path, 'source_toolkit': 'filesystem'}
                        )
                    except Exception as e:
                        logger.warning(f"Could not read {file_path}: {e}")
            
            ingest_result = self.run_from_generator(
                documents=local_loader(),
                source='filesystem',
                extract_relations=extract_relations
            )
        else:
            # Use toolkit to fetch specific files
            toolkit = self.source_toolkits[source]
            
            # Try to use toolkit's file-specific loader if available
            if hasattr(toolkit, 'get_files_content'):
                def file_loader():
                    for file_path in file_paths:
                        try:
                            content = toolkit.get_files_content(file_path)
                            if content:
                                yield Document(
                                    page_content=content,
                                    metadata={'file_path': file_path, 'source_toolkit': source}
                                )
                        except Exception as e:
                            logger.warning(f"Could not fetch {file_path}: {e}")
                
                ingest_result = self.run_from_generator(
                    documents=file_loader(),
                    source=source,
                    extract_relations=extract_relations
                )
            else:
                # Run full ingestion with whitelist
                ingest_result = self.run(
                    source=source,
                    whitelist=file_paths,
                    extract_relations=extract_relations
                )
        
        # Merge results
        result.documents_processed = ingest_result.documents_processed
        result.entities_added = ingest_result.entities_added
        result.relations_added = ingest_result.relations_added
        result.errors.extend(ingest_result.errors)
        result.success = ingest_result.success
        result.graph_stats = ingest_result.graph_stats
        result.duration_seconds = time.time() - start_time
        
        self._log_progress(
            f"✅ Delta update complete: -{result.entities_removed} +{result.entities_added}",
            "complete"
        )
        
        return result
    
    def discover_schema(self, sample_file_paths: List[str]) -> Dict[str, Any]:
        """
        Discover entity types from sample files using LLM.
        
        Useful for customizing extraction for domain-specific codebases.
        
        Args:
            sample_file_paths: Paths to sample files for schema discovery
            
        Returns:
            Discovered schema with entity_types and relation_types
        """
        if not self._init_extractors():
            return {'error': 'LLM not configured'}
        
        self._log_progress(f"🔍 Discovering schema from {len(sample_file_paths)} samples", "schema")
        
        from pathlib import Path
        docs = []
        
        for file_path in sample_file_paths[:10]:
            try:
                content = Path(file_path).read_text(encoding='utf-8')
                docs.append(Document(
                    page_content=content[:5000],
                    metadata={'file_path': file_path}
                ))
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")
        
        if not docs:
            return {'error': 'Could not read any sample files'}
        
        schema = self._schema_discoverer.discover(docs)
        self._knowledge_graph.set_schema(schema)
        self._auto_save()
        
        self._log_progress(
            f"✅ Discovered {len(schema.get('entity_types', []))} entity types, "
            f"{len(schema.get('relation_types', []))} relation types",
            "schema"
        )
        
        return schema
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current graph statistics."""
        return self._knowledge_graph.get_stats()
    
    def export(self, path: Optional[str] = None) -> str:
        """Export graph to JSON."""
        export_path = path or self.graph_path
        self._knowledge_graph.dump_to_json(export_path)
        return export_path
    
    def register_toolkit(self, name: str, toolkit: Any) -> None:
        """Register a source toolkit for ingestion."""
        self.source_toolkits[name] = toolkit
        logger.info(f"Registered toolkit: {name}")


# Convenience function for one-shot ingestion
def ingest_repository(
    llm: Any,
    graph_path: str,
    source_toolkit: Any,
    source_name: str = "repository",
    branch: Optional[str] = None,
    whitelist: Optional[List[str]] = None,
    blacklist: Optional[List[str]] = None,
    extract_relations: bool = True,
    progress_callback: Optional[Callable] = None,
) -> IngestionResult:
    """
    Convenience function for one-shot repository ingestion.
    
    Args:
        llm: LangChain LLM instance
        graph_path: Where to save the graph JSON
        source_toolkit: Toolkit instance with loader() method
        source_name: Name for the source in citations
        branch: Branch to analyze
        whitelist: File patterns to include
        blacklist: File patterns to exclude
        extract_relations: Whether to extract relations
        progress_callback: Optional callback for progress updates
        
    Returns:
        IngestionResult with statistics
        
    Example:
        from alita_sdk.community.github.api_wrapper import GitHubApiWrapper
        
        github = GitHubApiWrapper(
            api_base="...",
            api_key="...",
            repository="owner/repo"
        )
        
        result = ingest_repository(
            llm=llm,
            graph_path="./graph.json",
            source_toolkit=github,
            source_name="github",
            branch="main",
            whitelist=["*.py"],
            progress_callback=lambda msg, phase: print(f"[{phase}] {msg}")
        )
    """
    pipeline = IngestionPipeline(
        llm=llm,
        graph_path=graph_path,
        source_toolkits={source_name: source_toolkit},
        progress_callback=progress_callback,
    )
    
    return pipeline.run(
        source=source_name,
        branch=branch,
        whitelist=whitelist,
        blacklist=blacklist,
        extract_relations=extract_relations,
    )
