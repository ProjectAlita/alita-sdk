from typing import List, Tuple, Optional, Any
from pydantic import BaseModel, Field, model_validator


class StatisticalChunkerConfig(BaseModel):
    """Configuration for statistical chunker"""
    embedding: Optional[Any] = Field(default=None, description="Embedding model instance")
    max_doc_size: int = Field(default=300, description="Maximum tokens per document split")
    batch_size: int = Field(default=64, description="Batch size for processing documents")
    window_size: int = Field(default=5, description="Window size for similarity calculation")
    dynamic_threshold: bool = Field(default=True, description="Whether to use dynamic threshold")
    min_split_tokens: int = Field(default=100, description="Minimum tokens per split")
    max_split_tokens: int = Field(default=300, description="Maximum tokens per split")
    split_tokens_tolerance: int = Field(default=10, description="Tolerance for split token counts")
    threshold_adjustment: float = Field(default=0.01, description="Threshold adjustment for binary search")
    score_threshold: float = Field(default=0.5, description="Score threshold when not using dynamic threshold")
    
    @model_validator(mode='after')
    def validate_required_runtime_fields(self):
        if self.embedding is None:
            raise ValueError("embedding field must be set before using the chunker")
        return self


class MarkdownChunkerConfig(BaseModel):
    """Configuration for markdown chunker"""
    strip_header: bool = Field(default=False, description="Whether to strip headers from chunks")
    return_each_line: bool = Field(default=False, description="Whether to return each line separately")
    headers_to_split_on: List[Tuple[str, str]] = Field(
        default_factory=list, 
        description="List of tuples containing header patterns to split on"
    )
    max_tokens: int = Field(default=512, description="Maximum tokens per chunk")
    token_overlap: int = Field(default=10, description="Token overlap between chunks")


class ProposalChunkerConfig(BaseModel):
    """Configuration for proposal chunker"""
    llm: Optional[Any] = Field(default=None, description="LLM model instance for generating proposals")
    max_doc_tokens: int = Field(default=1024, description="Maximum tokens per document before splitting")
    
    @model_validator(mode='after')
    def validate_required_runtime_fields(self):
        if self.llm is None:
            raise ValueError("llm field must be set before using the chunker")
        return self


class CodeChunkerConfig(BaseModel):
    """Configuration for code chunker using parse_code_files_for_db"""
    chunk_size: int = Field(default=1024, description="Maximum characters per chunk for code splitting")
    chunk_overlap: int = Field(default=128, description="Character overlap between chunks")
    token_chunk_size: int = Field(default=256, description="Token chunk size for unknown language files")
    token_overlap: int = Field(default=30, description="Token overlap for unknown language files")
