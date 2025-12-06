"""
Cross-file reference pattern detection module.

This module provides extensible pattern matching for detecting cross-file
relationships in various programming languages and document types.

Pattern categories:
- imports: Code import/include statements
- links: Documentation links (Markdown, Wiki, HTML)
- citations: Text references ("see X", "@see X", etc.)
- mentions: Entity name mentions in content

Supported approaches:
1. Regex patterns - Fast, language-agnostic pattern matching
2. AST parsing - Accurate code analysis using deepwiki parsers (when available)

Each pattern file defines patterns for a specific language or document type.
"""

from .registry import PatternRegistry, Pattern, PatternCategory, RelationType
from .loader import (
    load_all_patterns, 
    get_patterns_for_file, 
    get_patterns_for_content_type,
    extract_references_from_content,
)

# AST adapter - provides integration with deepwiki parsers
from .ast_adapter import (
    is_ast_available,
    get_supported_ast_languages,
    parse_file_ast,
    parse_files_ast,
    extract_ast_cross_file_relations,
    get_symbols_for_entity_matching,
    ASTSymbol,
    ASTRelation,
    ASTParseResult,
)

__all__ = [
    # Pattern system
    'PatternRegistry',
    'Pattern', 
    'PatternCategory',
    'RelationType',
    'load_all_patterns',
    'get_patterns_for_file',
    'get_patterns_for_content_type',
    'extract_references_from_content',
    # AST adapter
    'is_ast_available',
    'get_supported_ast_languages',
    'parse_file_ast',
    'parse_files_ast',
    'extract_ast_cross_file_relations',
    'get_symbols_for_entity_matching',
    'ASTSymbol',
    'ASTRelation',
    'ASTParseResult',
]
