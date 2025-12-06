"""
Code and Document Parsers Module for Inventory Graph.

This module provides AST-based and regex-based parsers for extracting
symbols and relationships from source code and document files.

Supported Code Languages:
- Python: Full AST parsing using built-in ast module
- JavaScript/TypeScript: Regex-based parsing
- Java: Regex-based parsing
- Kotlin: Regex-based parsing (data classes, sealed classes, coroutines)
- C#/.NET: Regex-based parsing (records, async/await, LINQ)
- Rust: Regex-based parsing (traits, lifetimes, macros)
- Swift: Regex-based parsing (protocols, actors, property wrappers)
- Go: Regex-based parsing (goroutines, channels, embedding)

Supported Document Types:
- Markdown/RST: Links, wiki links, images, ADR/RFC references
- HTML: Anchors, scripts, stylesheets, media
- YAML/JSON: $ref, !include, Kubernetes, GitHub Actions
- Text: Universal patterns ("See X", "Depends on Y", URLs, Jira tickets, etc.)

The parsers extract:
- Symbols: classes, functions, methods, variables, headings, etc.
- Relationships: imports, calls, inheritance, references, etc.

Usage:
    from alita_sdk.community.inventory.parsers import (
        # Code Parsers
        PythonParser,
        JavaScriptParser,
        JavaParser,
        KotlinParser,
        CSharpParser,
        RustParser,
        SwiftParser,
        GoParser,
        # Document Parsers
        MarkdownParser,
        HTMLParser,
        YAMLParser,
        TextParser,
        # Functions
        get_parser_for_file,
        parse_file,
        parse_files,
    )
    
    # Parse a single file
    result = parse_file("/path/to/file.py")
    
    # Get parser by extension
    parser = get_parser_for_file("example.js")
    
    # Get all supported languages
    languages = parser_registry.get_supported_languages()
"""

from .base import (
    # Enums
    RelationshipType,
    SymbolType,
    Scope,
    # Data classes
    Position,
    Range,
    Symbol,
    Relationship,
    ParseResult,
    # Base class
    BaseParser,
    # Registry
    ParserRegistry,
    parser_registry,
)

# Code language parsers
from .python_parser import PythonParser
from .javascript_parser import JavaScriptParser
from .java_parser import JavaParser
from .kotlin_parser import KotlinParser
from .csharp_parser import CSharpParser
from .rust_parser import RustParser
from .swift_parser import SwiftParser
from .go_parser import GoParser

# Document parsers
from .markdown_parser import MarkdownParser
from .html_parser import HTMLParser
from .yaml_parser import YAMLParser
from .text_parser import TextParser

# Convenience functions
def get_parser_for_file(file_path: str) -> "BaseParser | None":
    """Get appropriate parser for a file based on extension."""
    return parser_registry.get_parser_for_file(file_path)


def parse_file(file_path: str, content: str = None) -> ParseResult:
    """
    Parse a file and extract symbols and relationships.
    
    Args:
        file_path: Path to the file
        content: Optional file content
        
    Returns:
        ParseResult with symbols and relationships
    """
    parser = get_parser_for_file(file_path)
    if parser:
        return parser.parse_file(file_path, content=content)
    
    # Return empty result for unsupported file types
    return ParseResult(
        file_path=file_path,
        language="unknown",
        symbols=[],
        relationships=[]
    )


def parse_files(file_paths: list, file_contents: dict = None, max_workers: int = 4) -> dict:
    """
    Parse multiple files with cross-file resolution.
    
    Groups files by language and uses multi-file parsing when available.
    
    Args:
        file_paths: List of file paths to parse
        file_contents: Optional dict mapping paths to content
        max_workers: Number of parallel workers
        
    Returns:
        Dict mapping file paths to ParseResult
    """
    from pathlib import Path
    from typing import Dict, List
    
    file_contents = file_contents or {}
    results: Dict[str, ParseResult] = {}
    
    # Group files by parser
    files_by_parser: Dict[str, List[str]] = {}
    
    for fp in file_paths:
        parser = get_parser_for_file(fp)
        if parser:
            lang = parser.language
            files_by_parser.setdefault(lang, []).append(fp)
        else:
            results[fp] = ParseResult(
                file_path=fp,
                language="unknown",
                symbols=[],
                relationships=[]
            )
    
    # Parse each language group
    for lang, lang_files in files_by_parser.items():
        parser = parser_registry.get_parser(lang)
        if not parser:
            continue
        
        if hasattr(parser, 'parse_multiple_files'):
            # Use multi-file parsing for cross-file resolution
            try:
                lang_results = parser.parse_multiple_files(lang_files, max_workers=max_workers)
                results.update(lang_results)
            except Exception:
                # Fall back to single file parsing
                for fp in lang_files:
                    content = file_contents.get(fp)
                    results[fp] = parser.parse_file(fp, content=content)
        else:
            # Single file parsing
            for fp in lang_files:
                content = file_contents.get(fp)
                results[fp] = parser.parse_file(fp, content=content)
    
    return results


__all__ = [
    # Enums
    'RelationshipType',
    'SymbolType',
    'Scope',
    # Data classes
    'Position',
    'Range',
    'Symbol',
    'Relationship',
    'ParseResult',
    # Base class
    'BaseParser',
    # Registry
    'ParserRegistry',
    'parser_registry',
    # Code Parsers
    'PythonParser',
    'JavaScriptParser',
    'JavaParser',
    'KotlinParser',
    'CSharpParser',
    'RustParser',
    'SwiftParser',
    'GoParser',
    # Document Parsers
    'MarkdownParser',
    'HTMLParser',
    'YAMLParser',
    'TextParser',
    # Functions
    'get_parser_for_file',
    'parse_file',
    'parse_files',
]
