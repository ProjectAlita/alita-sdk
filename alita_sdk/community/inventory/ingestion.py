"""
Inventory Ingestion Pipeline.

This module provides a workflow/pipeline for building and updating knowledge graphs
from source code repositories. It is NOT a toolkit - it's a defined process that:

1. Connects to source toolkits (GitHub, ADO, LocalGit, etc.)
2. Fetches documents via their loader() methods
3. Extracts entities using LLM
4. Extracts relations between entities
5. Persists the graph to JSON

The result is a graph dump that can be queried by the RetrievalToolkit.

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
from pathlib import Path
from typing import Any, Optional, List, Dict, Generator, Callable, TYPE_CHECKING
from datetime import datetime

from pydantic import BaseModel, Field, PrivateAttr
from langchain_core.documents import Document

from .knowledge_graph import KnowledgeGraph, Citation
from .extractors import (
    DocumentClassifier,
    EntitySchemaDiscoverer, 
    EntityExtractor,
    RelationExtractor,
    ENTITY_TAXONOMY,
    RELATIONSHIP_TAXONOMY,
)

if TYPE_CHECKING:
    from .config import GuardrailsConfig, IngestionConfig

logger = logging.getLogger(__name__)


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
    
    # Processed document tracking (file paths that have been successfully processed)
    processed_files: List[str] = Field(default_factory=list)
    
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
    
    def mark_file_processed(self, file_path: str) -> None:
        """Mark a file as successfully processed."""
        if file_path not in self.processed_files:
            self.processed_files.append(file_path)
    
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
    
    def _generate_entity_id(self, entity_type: str, name: str, file_path: str = None) -> str:
        """
        Generate unique entity ID.
        
        Entity IDs are based on (type, name) only - NOT file_path.
        This enables same-named entities from different files to be merged,
        creating a unified knowledge graph with multiple citations per entity.
        """
        # Normalize name for consistent hashing
        normalized_name = name.lower().strip()
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
    ) -> List[Dict[str, Any]]:
        """Extract entities from a single document."""
        if not self._entity_extractor:
            return []
        
        file_path = (doc.metadata.get('file_path') or 
                    doc.metadata.get('file_name') or 
                    doc.metadata.get('source', 'unknown'))
        
        # Get chunk position info for line number adjustment
        start_line = doc.metadata.get('start_line') or doc.metadata.get('line_start')
        
        # Extract entities - skip_on_error=True allows ingestion to continue if extraction fails
        extracted = self._entity_extractor.extract_batch([doc], schema=schema, skip_on_error=True)
        
        entities = []
        for entity in extracted:
            # Adjust line numbers if this is a chunk with offset
            entity_line_start = entity.get('line_start')
            entity_line_end = entity.get('line_end')
            
            if start_line and entity_line_start:
                entity_line_start = start_line + entity_line_start - 1
                if entity_line_end:
                    entity_line_end = start_line + entity_line_end - 1
            
            entity_id = self._generate_entity_id(
                entity.get('type', 'unknown'),
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
                'type': entity.get('type', 'unknown'),
                'citation': citation,
                'properties': {
                    k: v for k, v in entity.items()
                    if k not in ('id', 'name', 'type', 'content', 'text', 'line_start', 'line_end')
                },
                'source_doc': doc,  # Keep for relation extraction
            })
        
        return entities
    
    def _extract_relations(
        self, 
        entities: List[Dict[str, Any]],
        schema: Optional[Dict] = None,
        all_graph_entities: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract relations between entities.
        
        Args:
            entities: New entities to extract relations from
            schema: Optional schema to guide extraction
            all_graph_entities: All entities in graph (for ID resolution across sources)
        """
        if not self._relation_extractor or len(entities) < 2:
            return []
        
        relations = []
        
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
        
        # Extract relations within each file
        for file_path, file_entities in by_file.items():
            if len(file_entities) < 2:
                continue
            
            # Use first entity's doc for context
            doc = file_entities[0].get('source_doc')
            if not doc:
                doc = Document(page_content="", metadata={'file_path': file_path})
            
            # Convert to format expected by relation extractor
            # Pass file entities for context, but all_graph_entities for ID resolution
            entity_dicts = [
                {'id': e['id'], 'name': e['name'], 'type': e['type'], **e.get('properties', {})}
                for e in file_entities
            ]
            
            # Also pass all graph entities for cross-source ID resolution
            all_entity_dicts = [
                {'id': e.get('id'), 'name': e.get('name'), 'type': e.get('type')}
                for e in all_entities_for_lookup
                if e.get('id')
            ] if all_graph_entities else entity_dicts
            
            file_relations = self._relation_extractor.extract(
                doc, entity_dicts, schema=schema, confidence_threshold=0.5,
                all_entities=all_entity_dicts
            )
            relations.extend(file_relations)
        
        return relations
    
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
        if resume:
            checkpoint = self._load_checkpoint(source)
            if checkpoint and not checkpoint.completed:
                self._log_progress(
                    f"📋 Resuming from checkpoint: {checkpoint.documents_processed} docs already processed",
                    "resume"
                )
                result.resumed_from_checkpoint = True
                # Restore progress from checkpoint
                result.documents_processed = checkpoint.documents_processed
                result.entities_added = checkpoint.entities_added
        
        # Create new checkpoint if not resuming
        if not checkpoint or checkpoint.completed:
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
            # Fetch raw documents (not chunked) for entity extraction
            # Entity extraction works on whole files, not chunks
            self._log_progress(f"📥 Fetching documents from {source}...", "fetch")
            loader_args['chunked'] = False  # Get raw documents
            documents = toolkit.loader(**loader_args)
            
            # Get schema
            schema = self._knowledge_graph.get_schema()
            all_entities = list(checkpoint.pending_entities) if checkpoint.pending_entities else []
            
            checkpoint.phase = "extract"
            self._log_progress("🔍 Extracting entities...", "extract")
            
            docs_in_batch = 0
            
            # Process documents
            for doc in documents:
                # Check document limit (for testing)
                if max_documents and result.documents_processed >= max_documents:
                    self._log_progress(
                        f"⚠️ Reached document limit ({max_documents}), stopping...",
                        "limit"
                    )
                    break
                
                normalized = self._normalize_document(doc, source)
                if not normalized:
                    continue
                
                # Get file path for tracking
                file_path = (normalized.metadata.get('file_path') or 
                            normalized.metadata.get('file_name') or 
                            normalized.metadata.get('source', 'unknown'))
                
                # Skip if already processed (resuming from checkpoint)
                if checkpoint.is_file_processed(file_path):
                    result.documents_skipped += 1
                    continue
                
                result.documents_processed += 1
                docs_in_batch += 1
                
                # Extract entities from this document with error handling
                try:
                    entities = self._extract_entities_from_doc(normalized, source, schema)
                    
                    # Add to graph
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
                    
                    # Mark file as successfully processed
                    checkpoint.mark_file_processed(file_path)
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.warning(f"Failed to process document '{file_path}': {error_msg}")
                    checkpoint.mark_file_failed(file_path, error_msg)
                    result.failed_documents.append(file_path)
                    # Continue with next document
                    continue
                
                # Save checkpoint periodically
                if docs_in_batch % self.checkpoint_interval == 0:
                    checkpoint.documents_processed = result.documents_processed
                    checkpoint.entities_added = result.entities_added
                    self._save_checkpoint(checkpoint)
                    self._auto_save()  # Also save graph
                    
                    self._log_progress(
                        f"📄 Processed {result.documents_processed} docs | "
                        f"📊 {result.entities_added} entities | 💾 Checkpoint saved",
                        "progress"
                    )
                elif result.documents_processed % 10 == 0:
                    self._log_progress(
                        f"📄 Processed {result.documents_processed} docs | "
                        f"📊 {result.entities_added} entities",
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
                
                # Get ALL entities from graph (existing + new) for relation resolution
                # This enables cross-source relations (e.g., github entities referencing confluence entities)
                graph_entities = self._knowledge_graph.get_all_entities()
                
                self._log_progress(
                    f"🔗 Extracting relations from {len(all_entities)} new entities "
                    f"(graph has {len(graph_entities)} total)...",
                    "relations"
                )
                
                # Pass all graph entities for ID resolution, but only extract from new docs
                relations = self._extract_relations(all_entities, schema, all_graph_entities=graph_entities)
                
                for rel in relations:
                    success = self._knowledge_graph.add_relation(
                        source_id=rel.get('source_id'),
                        target_id=rel.get('target_id'),
                        relation_type=rel.get('relation_type', 'RELATED_TO'),
                        properties=rel.get('properties', {})
                    )
                    if success:
                        result.relations_added += 1
            
            # Save final graph
            self._auto_save()
            
            # Mark checkpoint as complete and clear it
            checkpoint.completed = True
            checkpoint.phase = "complete"
            checkpoint.relations_added = result.relations_added
            self._save_checkpoint(checkpoint)
            self._clear_checkpoint(source)  # Remove checkpoint file on success
            
            result.graph_stats = self._knowledge_graph.get_stats()
            result.duration_seconds = time.time() - start_time
            
            # Report any failed documents
            if result.failed_documents:
                self._log_progress(
                    f"⚠️ {len(result.failed_documents)} documents failed to process",
                    "warning"
                )
            
            self._log_progress(
                f"✅ Ingestion complete! {result.entities_added} entities, "
                f"{result.relations_added} relations in {result.duration_seconds:.1f}s",
                "complete"
            )
            
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
                entities = self._extract_entities_from_doc(normalized, source, schema)
                
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
                self._log_progress(f"🔗 Extracting relations...", "relations")
                relations = self._extract_relations(all_entities, schema)
                
                for rel in relations:
                    if self._knowledge_graph.add_relation(
                        source_id=rel.get('source_id'),
                        target_id=rel.get('target_id'),
                        relation_type=rel.get('relation_type', 'RELATED_TO'),
                        properties=rel.get('properties', {})
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
