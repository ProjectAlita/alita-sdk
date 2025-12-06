"""
Base Parser Interface and Data Structures.

This module defines the core interfaces and data classes for language-specific
AST parsers that extract symbols, relationships, and context from source code.

Simplified from deepwiki_plugin for self-contained use in inventory graph.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class RelationshipType(Enum):
    """Types of relationships between code elements."""
    # Module relationships
    IMPORTS = "imports"                    # import statements
    EXPORTS = "exports"                    # module exports
    
    # Function/method relationships
    CALLS = "calls"                       # function/method calls
    RETURNS = "returns"                   # return value relationships
    
    # Object-oriented relationships
    INHERITANCE = "inheritance"           # class inheritance (extends)
    IMPLEMENTATION = "implementation"     # interface implementation
    COMPOSITION = "composition"          # has-a relationships (strong ownership)
    AGGREGATION = "aggregation"          # has-a relationships (weak ownership)
    
    # Structural relationships
    DEFINES = "defines"                  # contains definition
    CONTAINS = "contains"                # structural containment
    DECORATES = "decorates"              # decorator relationships
    ANNOTATES = "annotates"              # type annotations
    
    # References
    REFERENCES = "references"            # general symbol references
    USES = "uses"                        # uses a type/symbol


class SymbolType(Enum):
    """Types of symbols that can be extracted from code."""
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    VARIABLE = "variable"
    CONSTANT = "constant"
    PROPERTY = "property"
    FIELD = "field"
    PARAMETER = "parameter"
    MODULE = "module"
    NAMESPACE = "namespace"
    ENUM = "enum"
    TYPE_ALIAS = "type_alias"
    DECORATOR = "decorator"
    IMPORT = "import"


class Scope(Enum):
    """Unified scoping model across languages."""
    GLOBAL = "global"                    # Global/module scope
    CLASS = "class"                      # Class scope
    FUNCTION = "function"                # Function/method scope
    BLOCK = "block"                      # Block scope
    LOCAL = "local"                      # Local variable scope


@dataclass
class Position:
    """Source code position information."""
    line: int
    column: int
    
    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


@dataclass
class Range:
    """Source code range information."""
    start: Position
    end: Position
    
    def __str__(self) -> str:
        return f"{self.start}-{self.end}"


@dataclass
class Symbol:
    """Extracted symbol information."""
    name: str
    symbol_type: SymbolType
    scope: Scope
    range: Range
    file_path: str
    
    # Hierarchical context
    parent_symbol: Optional[str] = None
    full_name: Optional[str] = None
    
    # Metadata
    visibility: Optional[str] = None
    is_static: bool = False
    is_async: bool = False
    is_exported: bool = False
    
    # Documentation
    docstring: Optional[str] = None
    
    # Type information
    return_type: Optional[str] = None
    parameter_types: List[str] = field(default_factory=list)
    
    # Source
    source_text: Optional[str] = None
    signature: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_qualified_name(self) -> str:
        """Get the fully qualified name of the symbol."""
        if self.full_name:
            return self.full_name
        if self.parent_symbol:
            return f"{self.parent_symbol}.{self.name}"
        return self.name


@dataclass
class Relationship:
    """Extracted relationship between symbols."""
    source_symbol: str
    target_symbol: str
    relationship_type: RelationshipType
    source_file: str
    
    target_file: Optional[str] = None
    source_range: Optional[Range] = None
    
    confidence: float = 1.0
    is_cross_file: bool = False
    
    context: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_key(self) -> str:
        """Get unique key for this relationship."""
        loc = f"{self.source_range.start.line}" if self.source_range else "0"
        return f"{self.source_symbol}->{self.target_symbol}:{self.relationship_type.value}@{loc}"


@dataclass
class ParseResult:
    """Result of parsing a source file."""
    file_path: str
    language: str
    symbols: List[Symbol]
    relationships: List[Relationship]
    
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)
    
    module_docstring: Optional[str] = None
    parse_time: Optional[float] = None
    
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def get_symbols_by_type(self, symbol_type: SymbolType) -> List[Symbol]:
        """Get all symbols of a specific type."""
        return [s for s in self.symbols if s.symbol_type == symbol_type]
    
    def get_relationships_by_type(self, rel_type: RelationshipType) -> List[Relationship]:
        """Get all relationships of a specific type."""
        return [r for r in self.relationships if r.relationship_type == rel_type]
    
    def get_cross_file_relationships(self) -> List[Relationship]:
        """Get only cross-file relationships."""
        return [r for r in self.relationships if r.is_cross_file or r.target_file]


class BaseParser(ABC):
    """
    Abstract base class for language-specific parsers.
    
    All language parsers must inherit from this class and implement
    the abstract methods.
    """
    
    def __init__(self, language: str):
        self.language = language
        self.logger = logging.getLogger(f"{__name__}.{language}")
    
    @abstractmethod
    def parse_file(self, file_path: Union[str, Path], content: Optional[str] = None) -> ParseResult:
        """
        Parse a source file and extract symbols and relationships.
        
        Args:
            file_path: Path to the source file
            content: Optional file content
            
        Returns:
            ParseResult containing extracted symbols and relationships
        """
        pass
    
    @abstractmethod
    def _get_supported_extensions(self) -> Set[str]:
        """
        Get set of supported file extensions.
        
        Returns:
            Set of file extensions (including the dot, e.g., {'.py'})
        """
        pass
    
    def supports_file(self, file_path: Union[str, Path]) -> bool:
        """Check if this parser can handle the given file."""
        path = Path(file_path)
        return path.suffix.lower() in self._get_supported_extensions()
    
    def validate_result(self, result: ParseResult) -> ParseResult:
        """Validate and clean up parse result."""
        # Remove duplicate symbols
        unique_symbols = []
        seen = set()
        for s in result.symbols:
            key = f"{s.name}:{s.symbol_type.value}:{s.range}"
            if key not in seen:
                unique_symbols.append(s)
                seen.add(key)
        result.symbols = unique_symbols
        
        # Remove duplicate relationships
        unique_rels = []
        seen_rels = set()
        for r in result.relationships:
            key = r.get_key()
            if key not in seen_rels:
                unique_rels.append(r)
                seen_rels.add(key)
        result.relationships = unique_rels
        
        return result


class ParserRegistry:
    """Registry for managing language-specific parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {}
        self._extension_map: Dict[str, str] = {}
    
    def register_parser(self, parser: BaseParser) -> None:
        """Register a language parser."""
        language = parser.language.lower()
        self._parsers[language] = parser
        
        for ext in parser._get_supported_extensions():
            self._extension_map[ext.lower()] = language
        
        logger.debug(f"Registered parser for {language}")
    
    def get_parser(self, language: str) -> Optional[BaseParser]:
        """Get parser for specific language."""
        return self._parsers.get(language.lower())
    
    def get_parser_for_file(self, file_path: Union[str, Path]) -> Optional[BaseParser]:
        """Get appropriate parser for a file based on extension."""
        path = Path(file_path)
        extension = path.suffix.lower()
        language = self._extension_map.get(extension)
        if language:
            return self._parsers.get(language)
        return None
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return list(self._parsers.keys())
    
    def get_supported_extensions(self) -> Set[str]:
        """Get set of all supported file extensions."""
        return set(self._extension_map.keys())


# Global parser registry instance
parser_registry = ParserRegistry()
