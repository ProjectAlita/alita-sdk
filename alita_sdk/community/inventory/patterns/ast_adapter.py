"""
AST Adapter - Bridge between parsers module and patterns module.

This module provides a unified interface for AST-based code analysis,
integrating with the local parsers module for first-pass extraction.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

# Import from local parsers module (self-contained, no external dependencies)
from ..parsers import (
    parser_registry,
    parse_file,
    parse_files,
    get_parser_for_file,
    ParseResult,
    Symbol,
    Relationship,
    RelationshipType,
    SymbolType,
)

logger = logging.getLogger(__name__)

# Type aliases for compatibility with patterns module
ASTSymbol = Symbol
ASTRelation = Relationship
ASTParseResult = ParseResult


def is_ast_available() -> bool:
    """
    Check if AST parsing is available.
    
    Since we use the local parsers module with Python's built-in ast
    and regex patterns, this is always available.
    
    Returns:
        True - AST parsing is always available
    """
    return True


def get_supported_languages() -> List[str]:
    """
    Get list of supported programming languages.
    
    Returns:
        List of language identifiers
    """
    return parser_registry.get_supported_languages()


def get_supported_ast_languages() -> List[str]:
    """
    Get list of supported programming languages for AST parsing.
    
    Alias for get_supported_languages() for compatibility with patterns module.
    
    Returns:
        List of language identifiers
    """
    return get_supported_languages()


def get_supported_extensions() -> List[str]:
    """
    Get list of supported file extensions.
    
    Returns:
        List of file extensions (with dot prefix)
    """
    return parser_registry.get_supported_extensions()


def parse_file_ast(
    file_path: str,
    content: Optional[str] = None
) -> Optional[ParseResult]:
    """
    Parse a single file and extract symbols and relationships.
    
    Args:
        file_path: Path to the file to parse
        content: Optional file content (if not provided, will read from disk)
        
    Returns:
        ParseResult with symbols and relationships, or None if parsing fails
    """
    try:
        return parse_file(file_path, content)
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return None


def parse_files_ast(
    file_paths: List[str],
    file_contents: Optional[Dict[str, str]] = None,
    resolve_cross_file: bool = True,
    max_workers: int = 4
) -> Dict[str, ParseResult]:
    """
    Parse multiple files with optional cross-file resolution.
    
    Args:
        file_paths: List of file paths to parse
        file_contents: Optional dict mapping file paths to content
        resolve_cross_file: Whether to resolve cross-file references
        max_workers: Maximum number of parallel workers
        
    Returns:
        Dict mapping file paths to ParseResult objects
    """
    results = {}
    
    # Group files by language
    files_by_language: Dict[str, List[Tuple[str, Optional[str]]]] = {}
    
    for file_path in file_paths:
        parser = get_parser_for_file(file_path)
        if parser:
            lang = parser.language
            if lang not in files_by_language:
                files_by_language[lang] = []
            content = file_contents.get(file_path) if file_contents else None
            files_by_language[lang].append((file_path, content))
    
    # Parse each language group
    for lang, files in files_by_language.items():
        parser = parser_registry.get_parser(lang)
        if parser and hasattr(parser, 'parse_multiple_files'):
            try:
                lang_results = parser.parse_multiple_files(
                    files,
                    resolve_cross_file=resolve_cross_file,
                    max_workers=max_workers
                )
                results.update(lang_results)
            except Exception as e:
                logger.warning(f"Failed to parse {lang} files: {e}")
                # Fall back to individual parsing
                for file_path, content in files:
                    result = parse_file_ast(file_path, content)
                    if result:
                        results[file_path] = result
        else:
            # Individual parsing fallback
            for file_path, content in files:
                result = parse_file_ast(file_path, content)
                if result:
                    results[file_path] = result
    
    return results


def extract_ast_cross_file_relations(
    parse_results: Dict[str, ParseResult]
) -> List[Dict[str, Any]]:
    """
    Extract cross-file relationships from parse results.
    
    Args:
        parse_results: Dict mapping file paths to ParseResult objects
        
    Returns:
        List of relationship dictionaries with source_file, target_file, etc.
    """
    cross_file_relations = []
    
    # Build symbol index
    symbol_to_file: Dict[str, str] = {}
    for file_path, result in parse_results.items():
        for symbol in result.symbols:
            symbol_to_file[symbol.name] = file_path
            if symbol.qualified_name:
                symbol_to_file[symbol.qualified_name] = file_path
    
    # Find cross-file relationships
    for file_path, result in parse_results.items():
        for rel in result.relationships:
            target_file = symbol_to_file.get(rel.target)
            if target_file and target_file != file_path:
                cross_file_relations.append({
                    'source_file': file_path,
                    'source': rel.source,
                    'target_file': target_file,
                    'target': rel.target,
                    'relationship_type': rel.relationship_type.value,
                    'metadata': rel.metadata
                })
    
    return cross_file_relations


def extract_first_pass_entities(
    file_path: str,
    content: str
) -> List[Dict[str, Any]]:
    """
    Extract entities (symbols) from a file for first-pass processing.
    
    This is a non-LLM based extraction using AST/regex patterns.
    
    Args:
        file_path: Path to the file
        content: File content
        
    Returns:
        List of entity dictionaries
    """
    result = parse_file_ast(file_path, content)
    if not result:
        return []
    
    entities = []
    for symbol in result.symbols:
        entity = {
            'name': symbol.name,
            'type': symbol.symbol_type.value,
            'file_path': file_path,
            'line_start': symbol.line_start,
            'line_end': symbol.line_end,
            'qualified_name': symbol.qualified_name,
        }
        if symbol.docstring:
            entity['docstring'] = symbol.docstring
        if symbol.metadata:
            entity['metadata'] = symbol.metadata
        entities.append(entity)
    
    return entities


def extract_first_pass_relations(
    file_path: str,
    content: str
) -> List[Dict[str, Any]]:
    """
    Extract relationships from a file for first-pass processing.
    
    This is a non-LLM based extraction using AST/regex patterns.
    
    Args:
        file_path: Path to the file
        content: File content
        
    Returns:
        List of relationship dictionaries
    """
    result = parse_file_ast(file_path, content)
    if not result:
        return []
    
    relations = []
    for rel in result.relationships:
        relation = {
            'source': rel.source,
            'target': rel.target,
            'relationship_type': rel.relationship_type.value,
            'file_path': file_path,
            'line': rel.line,
        }
        if rel.metadata:
            relation['metadata'] = rel.metadata
        relations.append(relation)
    
    return relations


def get_file_summary(
    file_path: str,
    content: str
) -> Dict[str, Any]:
    """
    Get a summary of a file's structure.
    
    Args:
        file_path: Path to the file
        content: File content
        
    Returns:
        Summary dictionary with counts and top-level items
    """
    result = parse_file_ast(file_path, content)
    if not result:
        return {
            'file_path': file_path,
            'language': 'unknown',
            'symbols': [],
            'relationships': [],
            'counts': {}
        }
    
    # Count by type
    symbol_counts: Dict[str, int] = {}
    for symbol in result.symbols:
        type_name = symbol.symbol_type.value
        symbol_counts[type_name] = symbol_counts.get(type_name, 0) + 1
    
    rel_counts: Dict[str, int] = {}
    for rel in result.relationships:
        type_name = rel.relationship_type.value
        rel_counts[type_name] = rel_counts.get(type_name, 0) + 1
    
    return {
        'file_path': file_path,
        'language': result.language,
        'symbols': [s.name for s in result.symbols],
        'relationships': len(result.relationships),
        'counts': {
            'symbols': symbol_counts,
            'relationships': rel_counts
        }
    }


def get_symbols_for_entity_matching(
    parse_results: Dict[str, ParseResult]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get symbols formatted for entity matching.
    
    This function extracts symbols from parse results and formats them
    for use in entity matching algorithms.
    
    Args:
        parse_results: Dict mapping file paths to ParseResult objects
        
    Returns:
        Dict mapping file paths to lists of symbol dictionaries
    """
    result = {}
    for file_path, parse_result in parse_results.items():
        symbols = []
        for symbol in parse_result.symbols:
            symbols.append({
                'name': symbol.name,
                'type': symbol.symbol_type.value,
                'full_name': symbol.full_name or symbol.get_qualified_name(),
                'file_path': symbol.file_path,
                'visibility': symbol.visibility,
                'docstring': symbol.docstring,
                'range': {
                    'start_line': symbol.range.start.line,
                    'end_line': symbol.range.end.line
                } if symbol.range else None,
                'metadata': symbol.metadata
            })
        result[file_path] = symbols
    return result


# Export key functions and types
__all__ = [
    'is_ast_available',
    'get_supported_languages',
    'get_supported_ast_languages',
    'get_supported_extensions',
    'parse_file_ast',
    'parse_files_ast',
    'extract_ast_cross_file_relations',
    'extract_first_pass_entities',
    'extract_first_pass_relations',
    'get_file_summary',
    'get_symbols_for_entity_matching',
    # Type aliases
    'ASTSymbol',
    'ASTRelation',
    'ASTParseResult',
    # Re-export types
    'ParseResult',
    'Symbol',
    'Relationship',
    'RelationshipType',
    'SymbolType',
]
