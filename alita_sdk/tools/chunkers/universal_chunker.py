"""
Universal Chunker - Routes documents to appropriate chunkers based on file type.

This module provides a universal chunking interface that automatically selects
the appropriate chunking strategy based on the file extension:

- .md, .markdown → Markdown chunker (header-based splitting)
- .py, .js, .ts, .java, etc. → TreeSitter code chunker
- .json → JSON chunker  
- other → Default text chunker

Usage:
    from alita_sdk.tools.chunkers.universal_chunker import universal_chunker
    
    # Chunk documents from a loader
    for chunk in universal_chunker(document_generator, config):
        print(chunk.page_content)
"""

import logging
import os
from typing import Generator, Dict, Any, Optional
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from .code.codeparser import parse_code_files_for_db
from .sematic.markdown_chunker import markdown_chunker
from .sematic.json_chunker import json_chunker

logger = logging.getLogger(__name__)


# File extension mappings
MARKDOWN_EXTENSIONS = {'.md', '.markdown', '.mdown', '.mkd', '.mdx'}
JSON_EXTENSIONS = {'.json', '.jsonl', '.jsonc'}
CODE_EXTENSIONS = {
    '.py', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx',
    '.java', '.kt', '.rs', '.go', '.cpp', '.c', '.cs', 
    '.hs', '.rb', '.scala', '.lua'
}


def get_file_extension(file_path: str) -> str:
    """Extract file extension from path."""
    return os.path.splitext(file_path)[-1].lower()


def get_file_type(file_path: str) -> str:
    """
    Determine the file type category for chunking.
    
    Returns:
        'markdown', 'json', 'code', or 'text'
    """
    ext = get_file_extension(file_path)
    
    if ext in MARKDOWN_EXTENSIONS:
        return 'markdown'
    elif ext in JSON_EXTENSIONS:
        return 'json'
    elif ext in CODE_EXTENSIONS:
        return 'code'
    else:
        return 'text'


def _default_text_chunker(
    documents: Generator[Document, None, None], 
    config: Dict[str, Any]
) -> Generator[Document, None, None]:
    """
    Default text chunker for unknown file types.
    Uses recursive character splitting.
    """
    chunk_size = config.get('chunk_size', 1000)
    chunk_overlap = config.get('chunk_overlap', 100)
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    
    for doc in documents:
        chunks = splitter.split_documents([doc])
        for idx, chunk in enumerate(chunks, 1):
            chunk.metadata['chunk_id'] = idx
            chunk.metadata['chunk_type'] = 'text'
            chunk.metadata['method_name'] = 'text'
            yield chunk


def _code_chunker_from_documents(
    documents: Generator[Document, None, None],
    config: Dict[str, Any]
) -> Generator[Document, None, None]:
    """
    Adapter to convert Document generator to code parser format.
    """
    def file_content_generator():
        for doc in documents:
            yield {
                'file_name': doc.metadata.get('file_path', doc.metadata.get('filename', 'unknown')),
                'file_content': doc.page_content,
                'commit_hash': doc.metadata.get('commit_hash', ''),
            }
    
    # parse_code_files_for_db returns chunks with proper metadata
    for chunk in parse_code_files_for_db(file_content_generator()):
        # Ensure file_path is preserved
        if 'file_path' not in chunk.metadata and 'filename' in chunk.metadata:
            chunk.metadata['file_path'] = chunk.metadata['filename']
        yield chunk


def universal_chunker(
    documents: Generator[Document, None, None],
    config: Optional[Dict[str, Any]] = None
) -> Generator[Document, None, None]:
    """
    Universal chunker that routes documents to appropriate chunkers based on file type.
    
    Each document is inspected for its file extension (from metadata.file_path or
    metadata.file_name) and routed to the appropriate chunker:
    
    - Markdown files → markdown_chunker (header-based splitting)
    - JSON files → json_chunker (recursive JSON splitting)
    - Code files → code parser (TreeSitter-based parsing)
    - Other files → default text chunker (recursive character splitting)
    
    Args:
        documents: Generator yielding Document objects with file content
        config: Optional configuration dict with:
            - markdown_config: Config for markdown chunker
            - json_config: Config for JSON chunker
            - code_config: Config for code chunker
            - text_config: Config for default text chunker
            
    Yields:
        Document objects with chunked content and preserved metadata
    """
    if config is None:
        config = {}
    
    # Default configs for each chunker type
    markdown_config = config.get('markdown_config', {
        'strip_header': False,
        'return_each_line': False,
        'headers_to_split_on': [
            ('#', 'Header 1'),
            ('##', 'Header 2'),
            ('###', 'Header 3'),
            ('####', 'Header 4'),
        ],
        'max_tokens': 1024,
        'token_overlap': 50,
        'min_chunk_chars': 100,  # Merge chunks smaller than this
    })
    
    json_config = config.get('json_config', {
        'max_tokens': 512,
    })
    
    code_config = config.get('code_config', {})
    
    text_config = config.get('text_config', {
        'chunk_size': 1000,
        'chunk_overlap': 100,
    })
    
    # Buffer documents by type for batch processing
    # This is more efficient than processing one at a time
    markdown_docs = []
    json_docs = []
    code_docs = []
    text_docs = []
    
    # Buffer size before flushing
    BUFFER_SIZE = 10
    
    def flush_markdown():
        if markdown_docs:
            def gen():
                for d in markdown_docs:
                    yield d
            for chunk in markdown_chunker(gen(), markdown_config):
                yield chunk
            markdown_docs.clear()
    
    def flush_json():
        if json_docs:
            def gen():
                for d in json_docs:
                    yield d
            for chunk in json_chunker(gen(), json_config):
                yield chunk
            json_docs.clear()
    
    def flush_code():
        if code_docs:
            def gen():
                for d in code_docs:
                    yield d
            for chunk in _code_chunker_from_documents(gen(), code_config):
                yield chunk
            code_docs.clear()
    
    def flush_text():
        if text_docs:
            def gen():
                for d in text_docs:
                    yield d
            for chunk in _default_text_chunker(gen(), text_config):
                yield chunk
            text_docs.clear()
    
    for doc in documents:
        # Get file path from metadata
        file_path = (doc.metadata.get('file_path') or 
                    doc.metadata.get('file_name') or 
                    doc.metadata.get('source') or 
                    'unknown')
        
        # Ensure file_path is in metadata for downstream use
        doc.metadata['file_path'] = file_path
        
        file_type = get_file_type(file_path)
        
        if file_type == 'markdown':
            markdown_docs.append(doc)
            if len(markdown_docs) >= BUFFER_SIZE:
                yield from flush_markdown()
        elif file_type == 'json':
            json_docs.append(doc)
            if len(json_docs) >= BUFFER_SIZE:
                yield from flush_json()
        elif file_type == 'code':
            code_docs.append(doc)
            if len(code_docs) >= BUFFER_SIZE:
                yield from flush_code()
        else:
            text_docs.append(doc)
            if len(text_docs) >= BUFFER_SIZE:
                yield from flush_text()
    
    # Flush remaining documents
    yield from flush_markdown()
    yield from flush_json()
    yield from flush_code()
    yield from flush_text()


def chunk_single_document(
    doc: Document,
    config: Optional[Dict[str, Any]] = None
) -> Generator[Document, None, None]:
    """
    Convenience function to chunk a single document.
    
    Args:
        doc: Single Document to chunk
        config: Optional chunker configuration
        
    Yields:
        Chunked Document objects
    """
    def single_doc_gen():
        yield doc
    
    yield from universal_chunker(single_doc_gen(), config)
