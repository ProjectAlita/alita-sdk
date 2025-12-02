"""
Configuration for Inventory Ingestion Pipeline.

Since the ingestion runs within Alita, the LLM and embeddings are provided
by the Alita client. Configuration only needs model names, not providers.

Usage:
    # From YAML config file
    config = IngestionConfig.from_yaml("./ingestion-config.yml")
    
    # Programmatic
    config = IngestionConfig(
        llm_model="gpt-4o-mini",
        embedding_model="text-embedding-3-small",
        guardrails=GuardrailsConfig(
            max_tokens_per_doc=8000,
            max_entities_per_doc=50,
        )
    )
    
    # Use in pipeline (Alita client provides LLM/embeddings)
    pipeline = IngestionPipeline(
        llm=alita.get_langchain_llm(config.llm_model),
        embedding=alita.get_embeddings(config.embedding_model),
        graph_path=config.graph_path,
        guardrails=config.guardrails,
    )
"""

import os
import logging
from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GuardrailsConfig(BaseModel):
    """Guardrails configuration for safe and controlled extraction."""
    
    # Token/content limits
    max_tokens_per_doc: int = Field(
        default=8000, 
        description="Maximum tokens per document before chunking"
    )
    max_entities_per_doc: int = Field(
        default=50, 
        description="Maximum entities to extract from a single document"
    )
    max_relations_per_doc: int = Field(
        default=100,
        description="Maximum relations to extract per document"
    )
    
    # Content filtering
    content_filter_enabled: bool = Field(
        default=True,
        description="Enable content filtering for PII/secrets"
    )
    filter_patterns: List[str] = Field(
        default_factory=lambda: [
            r'(?i)(password|secret|api[_-]?key|token)\s*[=:]\s*["\'][^"\']+["\']',
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'-----BEGIN [A-Z]+ PRIVATE KEY-----',
        ],
        description="Regex patterns to filter from content before LLM processing"
    )
    
    # Rate limiting
    rate_limit_requests_per_minute: Optional[int] = Field(
        default=None,
        description="Max LLM requests per minute (None = unlimited)"
    )
    rate_limit_tokens_per_minute: Optional[int] = Field(
        default=None,
        description="Max tokens per minute (None = unlimited)"
    )
    
    # Error handling
    max_retries: int = Field(default=3, description="Max retries on LLM errors")
    retry_delay_seconds: float = Field(default=1.0, description="Delay between retries")
    skip_on_error: bool = Field(
        default=True, 
        description="Skip document on extraction error vs fail pipeline"
    )
    
    # Validation
    validate_entity_types: bool = Field(
        default=True,
        description="Validate extracted entities against taxonomy"
    )
    validate_relation_types: bool = Field(
        default=True,
        description="Validate extracted relations against taxonomy"
    )
    
    # Deduplication
    deduplicate_entities: bool = Field(
        default=True,
        description="Merge duplicate entities by name+type+file"
    )
    
    # Confidence thresholds
    entity_confidence_threshold: float = Field(
        default=0.5,
        description="Minimum confidence for entity extraction"
    )
    relation_confidence_threshold: float = Field(
        default=0.5,
        description="Minimum confidence for relation extraction"
    )


class IngestionConfig(BaseModel):
    """
    Configuration for the ingestion pipeline.
    
    Since ingestion runs within Alita, only model names are needed.
    The Alita client handles provider details, API keys, etc.
    """
    
    # Model names (Alita provides the actual LLM/embedding instances)
    llm_model: str = Field(
        default="gpt-4o-mini", 
        description="LLM model name (e.g., gpt-4o-mini, claude-3-sonnet)"
    )
    embedding_model: Optional[str] = Field(
        default=None, 
        description="Embedding model name (optional, for semantic search)"
    )
    
    # Model parameters
    temperature: float = Field(default=0.0, description="LLM temperature")
    
    # Guardrails configuration
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)
    
    # Graph configuration
    graph_path: str = Field(default="./knowledge_graph.json", description="Path to persist graph")
    auto_save: bool = Field(default=True, description="Auto-save after mutations")
    
    # Extraction settings
    extract_relations: bool = Field(default=True, description="Extract relations between entities")
    chunk_size: int = Field(default=4000, description="Document chunk size for processing")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")
    
    # Concurrency
    max_concurrent_extractions: int = Field(
        default=1, 
        description="Max parallel extraction tasks (1 = sequential)"
    )
    
    @classmethod
    def from_yaml(cls, path: str) -> "IngestionConfig":
        """Load configuration from YAML file."""
        import yaml
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, path: str) -> "IngestionConfig":
        """Load configuration from JSON file."""
        import json
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> "IngestionConfig":
        """
        Create configuration from environment variables.
        
        Environment variables:
            LLM_MODEL: Model name (default: gpt-4o-mini)
            EMBEDDING_MODEL: Embedding model name (optional)
            LLM_TEMPERATURE: Temperature (default: 0.0)
            GRAPH_PATH: Path to save graph (default: ./knowledge_graph.json)
            MAX_TOKENS_PER_DOC: Max tokens per doc (default: 8000)
            MAX_ENTITIES_PER_DOC: Max entities per doc (default: 50)
            CONTENT_FILTER_ENABLED: true/false (default: true)
            EXTRACT_RELATIONS: true/false (default: true)
        """
        guardrails = GuardrailsConfig(
            max_tokens_per_doc=int(os.environ.get('MAX_TOKENS_PER_DOC', '8000')),
            max_entities_per_doc=int(os.environ.get('MAX_ENTITIES_PER_DOC', '50')),
            content_filter_enabled=os.environ.get('CONTENT_FILTER_ENABLED', 'true').lower() == 'true',
            max_retries=int(os.environ.get('MAX_RETRIES', '3')),
        )
        
        return cls(
            llm_model=os.environ.get('LLM_MODEL', 'gpt-4o-mini'),
            embedding_model=os.environ.get('EMBEDDING_MODEL'),
            temperature=float(os.environ.get('LLM_TEMPERATURE', '0.0')),
            guardrails=guardrails,
            graph_path=os.environ.get('GRAPH_PATH', './knowledge_graph.json'),
            extract_relations=os.environ.get('EXTRACT_RELATIONS', 'true').lower() == 'true',
        )
    
    def to_yaml(self, path: str) -> None:
        """Save configuration to YAML file."""
        import yaml
        
        with open(path, 'w') as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()


# Example YAML configuration template
EXAMPLE_CONFIG_YAML = """# Inventory Ingestion Configuration
# Model names only - Alita provides the actual LLM/embedding instances

# LLM model name (required)
llm_model: gpt-4o-mini
temperature: 0.0

# Embedding model (optional, for semantic search)
embedding_model: text-embedding-3-small

# Guardrails - safety and control
guardrails:
  max_tokens_per_doc: 8000
  max_entities_per_doc: 50
  max_relations_per_doc: 100
  content_filter_enabled: true
  max_retries: 3
  retry_delay_seconds: 1.0
  skip_on_error: true
  entity_confidence_threshold: 0.5
  relation_confidence_threshold: 0.5
  deduplicate_entities: true
  # rate_limit_requests_per_minute: 60  # Uncomment to rate limit

# Graph persistence
graph_path: ./knowledge_graph.json
auto_save: true

# Extraction settings
extract_relations: true
chunk_size: 4000
chunk_overlap: 200
max_concurrent_extractions: 1
"""


def generate_config_template(output_path: str = "./ingestion-config.yml") -> str:
    """Generate a configuration template file."""
    with open(output_path, 'w') as f:
        f.write(EXAMPLE_CONFIG_YAML)
    return output_path
