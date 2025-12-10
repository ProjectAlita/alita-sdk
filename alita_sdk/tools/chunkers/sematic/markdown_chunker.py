from typing import Generator, List
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, ExperimentalMarkdownSyntaxTextSplitter
from langchain.text_splitter import TokenTextSplitter
from ..utils import tiktoken_length
from copy import deepcopy as copy


def markdown_chunker(file_content_generator: Generator[Document, None, None], config: dict, *args, **kwargs) -> Generator[Document, None, None]:
    """
    Chunks markdown documents by headers, with support for:
    - Minimum chunk size to avoid tiny fragments
    - Maximum token limit with overflow splitting
    - Header metadata preservation
    
    Config options:
        strip_header (bool): Remove headers from content. Default: False
        return_each_line (bool): Split on every line. Default: False
        headers_to_split_on (list): Headers to split on, e.g. [('#', 'H1'), ('##', 'H2')]
        max_tokens (int): Maximum tokens per chunk. Default: 512
        token_overlap (int): Token overlap for large chunk splitting. Default: 10
        min_chunk_chars (int): Minimum characters per chunk. Default: 100
            Chunks smaller than this will be merged with the next chunk.
    """
    strip_header = config.get("strip_header", False)
    return_each_line = config.get("return_each_line", False)
    headers_to_split_on = config.get("headers_to_split_on", [])
    max_tokens = config.get("max_tokens", 512)
    tokens_overlapping = config.get("token_overlap", 10)
    min_chunk_chars = config.get("min_chunk_chars", 100)  # Minimum characters per chunk
    
    headers_to_split_on = [tuple(header) for header in headers_to_split_on]
    
    for doc in file_content_generator:
        doc_metadata = doc.metadata
        doc_content = doc.page_content
        chunk_id = 0
        
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on, 
            strip_headers=strip_header,
            return_each_line=return_each_line
        )
        md_header_splits = markdown_splitter.split_text(doc_content)
        
        # Merge small chunks with the next one
        merged_chunks = _merge_small_chunks(md_header_splits, min_chunk_chars)
        
        for chunk in merged_chunks:
            if tiktoken_length(chunk.page_content) > max_tokens:
                # Split large chunks into smaller ones
                for subchunk in TokenTextSplitter(
                    encoding_name="cl100k_base", 
                    chunk_size=max_tokens, 
                    chunk_overlap=tokens_overlapping
                ).split_text(chunk.page_content):
                    chunk_id += 1
                    headers_meta = list(chunk.metadata.values())
                    docmeta = copy(doc_metadata)
                    docmeta.update({"headers": "; ".join(headers_meta)})
                    docmeta['chunk_id'] = chunk_id
                    docmeta['chunk_type'] = "document"
                    docmeta['method_name'] = 'markdown'
                    yield Document(
                        page_content=subchunk,
                        metadata=docmeta
                    )
            else:
                chunk_id += 1
                headers_meta = list(chunk.metadata.values())
                docmeta = copy(doc_metadata)
                docmeta.update({"headers": "; ".join(headers_meta)})
                docmeta['chunk_id'] = chunk_id
                docmeta['chunk_type'] = "document"
                docmeta['method_name'] = 'text'
                yield Document(
                    page_content=chunk.page_content,
                    metadata=docmeta
                )


def _merge_small_chunks(chunks: List[Document], min_chars: int) -> List[Document]:
    """
    Merge chunks that are smaller than min_chars with the next chunk.
    
    This prevents tiny fragments (like standalone headers or short notes)
    from becoming separate chunks.
    
    Args:
        chunks: List of Document chunks from markdown splitter
        min_chars: Minimum character count for a chunk
        
    Returns:
        List of merged Document chunks
    """
    if not chunks:
        return chunks
    
    merged = []
    pending_content = ""
    pending_metadata = {}
    
    for i, chunk in enumerate(chunks):
        content = chunk.page_content.strip()
        
        if pending_content:
            # Merge pending content with current chunk
            combined_content = pending_content + "\n\n" + content
            # Use the pending metadata (from the header) but can be extended
            combined_metadata = {**pending_metadata}
            # Add any new header info from current chunk
            for key, value in chunk.metadata.items():
                if key not in combined_metadata or not combined_metadata[key]:
                    combined_metadata[key] = value
            
            if len(combined_content) >= min_chars:
                # Combined is big enough, emit it
                merged.append(Document(
                    page_content=combined_content,
                    metadata=combined_metadata
                ))
                pending_content = ""
                pending_metadata = {}
            else:
                # Still too small, keep accumulating
                pending_content = combined_content
                pending_metadata = combined_metadata
        elif len(content) < min_chars:
            # Current chunk is too small, start pending
            pending_content = content
            pending_metadata = dict(chunk.metadata)
        else:
            # Current chunk is big enough
            merged.append(chunk)
    
    # Don't forget any remaining pending content
    if pending_content:
        merged.append(Document(
            page_content=pending_content,
            metadata=pending_metadata
        ))
    
    return merged


def markdown_by_headers_chunker(file_content_generator: Generator[Document, None, None], config: dict, *args, **kwargs) -> Generator[Document, None, None]:
    strip_header = config.get("strip_header", False)
    return_each_line = config.get("return_each_line", False)
    headers_to_split_on = config.get("headers_to_split_on", [])
    headers_to_split_on = [header.split(' ', 1) for header in headers_to_split_on]
    for doc in file_content_generator:
        doc_metadata = doc.metadata
        doc_content = doc.page_content
        chunk_id = 0
        markdown_splitter = ExperimentalMarkdownSyntaxTextSplitter(
            headers_to_split_on=headers_to_split_on, 
            strip_headers=strip_header,
            return_each_line=return_each_line
        )
        md_header_splits = markdown_splitter.split_text(doc_content)
        for chunk in md_header_splits:
            chunk_id += 1
            headers_meta = list(chunk.metadata.values())
            docmeta = copy(doc_metadata)
            docmeta.update({"headers": "; ".join(headers_meta)})
            docmeta['chunk_id'] = chunk_id
            docmeta['chunk_type'] = "document"
            yield Document(
                page_content=chunk.page_content,
                metadata=docmeta
            )