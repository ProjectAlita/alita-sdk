"""
Java Parser - Regex-based parsing.

This parser uses regex patterns for Java analysis:
- Import/package detection
- Class, interface, enum extraction
- Inheritance and implementation patterns
- Method and field detection
- Annotation support

Works without external dependencies like tree-sitter.
"""

import re
import hashlib
import logging
import time
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Tuple

from .base import (
    BaseParser, ParseResult, Symbol, Relationship,
    SymbolType, RelationshipType, Scope, Position, Range,
    parser_registry
)

logger = logging.getLogger(__name__)


# Comprehensive regex patterns for Java
PATTERNS = {
    # Package
    'package': re.compile(
        r'package\s+([\w.]+)\s*;',
        re.MULTILINE
    ),
    
    # Imports
    'import': re.compile(
        r'import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;',
        re.MULTILINE
    ),
    
    # Classes
    'class_def': re.compile(
        r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?class\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generics
        r'(?:\s+extends\s+(\w+)(?:<[^>]+>)?)?'
        r'(?:\s+implements\s+([\w,\s<>]+))?',
        re.MULTILINE
    ),
    
    # Interfaces
    'interface_def': re.compile(
        r'(?:public\s+|private\s+|protected\s+)?interface\s+(\w+)'
        r'(?:<[^>]+>)?'
        r'(?:\s+extends\s+([\w,\s<>]+))?',
        re.MULTILINE
    ),
    
    # Enums
    'enum_def': re.compile(
        r'(?:public\s+|private\s+|protected\s+)?enum\s+(\w+)'
        r'(?:\s+implements\s+([\w,\s<>]+))?',
        re.MULTILINE
    ),
    
    # Records (Java 14+)
    'record_def': re.compile(
        r'(?:public\s+|private\s+|protected\s+)?record\s+(\w+)\s*\([^)]*\)'
        r'(?:\s+implements\s+([\w,\s<>]+))?',
        re.MULTILINE
    ),
    
    # Methods
    'method_def': re.compile(
        r'(?:public\s+|private\s+|protected\s+)?'
        r'(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:abstract\s+)?'
        r'(?:<[^>]+>\s+)?'  # Generic type params
        r'([\w<>\[\],\s]+)\s+'  # Return type
        r'(\w+)\s*'  # Method name
        r'\([^)]*\)',  # Parameters
        re.MULTILINE
    ),
    
    # Constructors
    'constructor_def': re.compile(
        r'(?:public\s+|private\s+|protected\s+)?(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{',
        re.MULTILINE
    ),
    
    # Fields
    'field_def': re.compile(
        r'(?:public\s+|private\s+|protected\s+)?'
        r'(?:static\s+)?(?:final\s+)?'
        r'([\w<>\[\],\s]+)\s+'  # Type
        r'(\w+)\s*'  # Name
        r'(?:=|;)',
        re.MULTILINE
    ),
    
    # Annotations
    'annotation': re.compile(
        r'@(\w+)(?:\([^)]*\))?',
        re.MULTILINE
    ),
    
    # Method calls
    'method_call': re.compile(
        r'(?:(\w+)\.)?(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # Object instantiation
    'new_instance': re.compile(
        r'new\s+(\w+)\s*(?:<[^>]*>)?\s*\(',
        re.MULTILINE
    ),
    
    # JavaDoc @see
    'javadoc_see': re.compile(
        r'@see\s+(?:#|{@link\s+)?(\w+(?:\.\w+)*)',
        re.MULTILINE
    ),
    
    # Type references in generics
    'generic_type': re.compile(
        r'<(\w+)(?:\s*,\s*(\w+))*>',
        re.MULTILINE
    ),
}


def _parse_single_file(file_path: str) -> Tuple[str, ParseResult]:
    """Parse a single Java file."""
    try:
        parser = JavaParser()
        result = parser.parse_file(file_path)
        return file_path, result
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return file_path, ParseResult(
            file_path=file_path,
            language="java",
            symbols=[],
            relationships=[]
        )


class JavaParser(BaseParser):
    """
    Java parser using regex patterns.
    
    Extracts classes, interfaces, methods, and relationships.
    """
    
    def __init__(self):
        super().__init__("java")
        self._current_file = ""
        self._current_content = ""
        self._current_package = ""
        
        # Cross-file resolution
        self._global_classes: Dict[str, str] = {}  # class_name -> file_path
        self._global_interfaces: Dict[str, str] = {}
    
    def _get_supported_extensions(self) -> Set[str]:
        return {'.java'}
    
    def parse_file(self, file_path: Union[str, Path], content: Optional[str] = None) -> ParseResult:
        """Parse a Java file."""
        start_time = time.time()
        file_path = str(file_path)
        self._current_file = file_path
        
        try:
            if content is None:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            
            self._current_content = content
            
            # Extract package
            pkg_match = PATTERNS['package'].search(content)
            self._current_package = pkg_match.group(1) if pkg_match else ""
            
            symbols = self._extract_symbols(content, file_path)
            relationships = self._extract_relationships(content, symbols, file_path)
            imports = self._extract_imports(content)
            
            result = ParseResult(
                file_path=file_path,
                language="java",
                symbols=symbols,
                relationships=relationships,
                imports=imports,
                parse_time=time.time() - start_time
            )
            
            return self.validate_result(result)
            
        except Exception as e:
            logger.error(f"Failed to parse Java file {file_path}: {e}")
            return ParseResult(
                file_path=file_path,
                language="java",
                symbols=[],
                relationships=[],
                parse_time=time.time() - start_time,
                errors=[str(e)]
            )
    
    def _extract_symbols(self, content: str, file_path: str) -> List[Symbol]:
        """Extract symbols from Java content."""
        symbols = []
        lines = content.split('\n')
        class_name = Path(file_path).stem
        
        # Module/file symbol
        full_name = f"{self._current_package}.{class_name}" if self._current_package else class_name
        symbols.append(Symbol(
            name=class_name,
            symbol_type=SymbolType.MODULE,
            scope=Scope.GLOBAL,
            range=Range(Position(1, 0), Position(len(lines), 0)),
            file_path=file_path,
            full_name=full_name
        ))
        
        # Classes
        for match in PATTERNS['class_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            name = match.group(1)
            extends = match.group(2)
            
            symbols.append(Symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                full_name=f"{self._current_package}.{name}" if self._current_package else name,
                visibility='public' if 'public' in match.group(0) else 'package',
                metadata={'extends': extends} if extends else {}
            ))
        
        # Interfaces
        for match in PATTERNS['interface_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            name = match.group(1)
            
            symbols.append(Symbol(
                name=name,
                symbol_type=SymbolType.INTERFACE,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                full_name=f"{self._current_package}.{name}" if self._current_package else name,
                visibility='public' if 'public' in match.group(0) else 'package'
            ))
        
        # Enums
        for match in PATTERNS['enum_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            name = match.group(1)
            
            symbols.append(Symbol(
                name=name,
                symbol_type=SymbolType.ENUM,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                full_name=f"{self._current_package}.{name}" if self._current_package else name,
                visibility='public' if 'public' in match.group(0) else 'package'
            ))
        
        # Records
        for match in PATTERNS['record_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            name = match.group(1)
            
            symbols.append(Symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                full_name=f"{self._current_package}.{name}" if self._current_package else name,
                visibility='public' if 'public' in match.group(0) else 'package',
                metadata={'is_record': True}
            ))
        
        # Methods
        for match in PATTERNS['method_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            return_type = match.group(1).strip()
            name = match.group(2)
            
            # Skip if it looks like a constructor (return type == class name)
            if name in [s.name for s in symbols if s.symbol_type in (SymbolType.CLASS, SymbolType.INTERFACE)]:
                continue
            
            symbols.append(Symbol(
                name=name,
                symbol_type=SymbolType.METHOD,
                scope=Scope.CLASS,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                return_type=return_type,
                visibility='public' if 'public' in match.group(0) else ('private' if 'private' in match.group(0) else 'protected'),
                is_static='static' in match.group(0),
                is_async='synchronized' in match.group(0)  # Using is_async for synchronized
            ))
        
        # Fields
        for match in PATTERNS['field_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            field_type = match.group(1).strip()
            name = match.group(2)
            
            # Skip common false positives (method returns, etc.)
            if field_type in ('return', 'throw', 'if', 'else', 'for', 'while', 'switch', 'case'):
                continue
            
            symbols.append(Symbol(
                name=name,
                symbol_type=SymbolType.FIELD,
                scope=Scope.CLASS,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                return_type=field_type,
                visibility='public' if 'public' in match.group(0) else ('private' if 'private' in match.group(0) else 'protected'),
                is_static='static' in match.group(0)
            ))
        
        # Imports as symbols
        for match in PATTERNS['import'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            import_path = match.group(1)
            name = import_path.split('.')[-1]
            
            symbols.append(Symbol(
                name=name,
                symbol_type=SymbolType.IMPORT,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                metadata={'full_path': import_path, 'is_static': 'static' in match.group(0)}
            ))
        
        return symbols
    
    def _extract_relationships(self, content: str, symbols: List[Symbol], file_path: str) -> List[Relationship]:
        """Extract relationships from Java content."""
        relationships = []
        module_name = Path(file_path).stem
        
        # Import relationships
        for match in PATTERNS['import'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            import_path = match.group(1)
            
            relationships.append(Relationship(
                source_symbol=module_name,
                target_symbol=import_path,
                relationship_type=RelationshipType.IMPORTS,
                source_file=file_path,
                source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                confidence=1.0
            ))
        
        # Inheritance (extends)
        for match in PATTERNS['class_def'].finditer(content):
            class_name = match.group(1)
            extends = match.group(2)
            implements = match.group(3)
            line = content[:match.start()].count('\n') + 1
            
            if extends:
                relationships.append(Relationship(
                    source_symbol=class_name,
                    target_symbol=extends,
                    relationship_type=RelationshipType.INHERITANCE,
                    source_file=file_path,
                    source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                    confidence=0.95
                ))
            
            if implements:
                for iface in implements.split(','):
                    iface = re.sub(r'<[^>]*>', '', iface).strip()  # Remove generics
                    if iface:
                        relationships.append(Relationship(
                            source_symbol=class_name,
                            target_symbol=iface,
                            relationship_type=RelationshipType.IMPLEMENTATION,
                            source_file=file_path,
                            source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                            confidence=0.95
                        ))
        
        # Interface extension
        for match in PATTERNS['interface_def'].finditer(content):
            iface_name = match.group(1)
            extends = match.group(2)
            if extends:
                line = content[:match.start()].count('\n') + 1
                for parent in extends.split(','):
                    parent = re.sub(r'<[^>]*>', '', parent).strip()
                    if parent:
                        relationships.append(Relationship(
                            source_symbol=iface_name,
                            target_symbol=parent,
                            relationship_type=RelationshipType.INHERITANCE,
                            source_file=file_path,
                            source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                            confidence=0.95
                        ))
        
        # Enum implementation
        for match in PATTERNS['enum_def'].finditer(content):
            enum_name = match.group(1)
            implements = match.group(2)
            if implements:
                line = content[:match.start()].count('\n') + 1
                for iface in implements.split(','):
                    iface = re.sub(r'<[^>]*>', '', iface).strip()
                    if iface:
                        relationships.append(Relationship(
                            source_symbol=enum_name,
                            target_symbol=iface,
                            relationship_type=RelationshipType.IMPLEMENTATION,
                            source_file=file_path,
                            source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                            confidence=0.95
                        ))
        
        # Object instantiation (new)
        for match in PATTERNS['new_instance'].finditer(content):
            type_name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            
            relationships.append(Relationship(
                source_symbol=module_name,
                target_symbol=type_name,
                relationship_type=RelationshipType.USES,
                source_file=file_path,
                source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                confidence=0.85
            ))
        
        # Annotation relationships
        annotations_found = list(PATTERNS['annotation'].finditer(content))
        for i, match in enumerate(annotations_found):
            ann_name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            
            # Find the next class, interface, method, or field
            remaining = content[match.end():]
            target = None
            
            class_match = PATTERNS['class_def'].search(remaining)
            iface_match = PATTERNS['interface_def'].search(remaining)
            method_match = PATTERNS['method_def'].search(remaining)
            
            if class_match and (not method_match or class_match.start() < method_match.start()):
                target = class_match.group(1)
            elif iface_match and (not method_match or iface_match.start() < method_match.start()):
                target = iface_match.group(1)
            elif method_match:
                target = method_match.group(2)
            
            if target:
                relationships.append(Relationship(
                    source_symbol=ann_name,
                    target_symbol=target,
                    relationship_type=RelationshipType.DECORATES,
                    source_file=file_path,
                    source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                    confidence=0.90
                ))
        
        # JavaDoc @see references
        for match in PATTERNS['javadoc_see'].finditer(content):
            ref = match.group(1)
            line = content[:match.start()].count('\n') + 1
            
            relationships.append(Relationship(
                source_symbol=module_name,
                target_symbol=ref,
                relationship_type=RelationshipType.REFERENCES,
                source_file=file_path,
                source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                confidence=0.80
            ))
        
        return relationships
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import paths."""
        imports = []
        for match in PATTERNS['import'].finditer(content):
            imports.append(match.group(1))
        return list(set(imports))
    
    def parse_multiple_files(self, file_paths: List[str], max_workers: int = 4) -> Dict[str, ParseResult]:
        """Parse multiple Java files with cross-file resolution."""
        results: Dict[str, ParseResult] = {}
        total = len(file_paths)
        
        self._global_classes = {}
        self._global_interfaces = {}
        
        logger.info(f"Parsing {total} Java files")
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_parse_single_file, fp): fp for fp in file_paths}
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    fp, result = future.result(timeout=60)
                    results[fp] = result
                except Exception as e:
                    fp = futures[future]
                    logger.error(f"Failed to parse {fp}: {e}")
                    results[fp] = ParseResult(
                        file_path=fp,
                        language="java",
                        symbols=[],
                        relationships=[],
                        errors=[str(e)]
                    )
        
        # Build global registry
        for fp, result in results.items():
            self._build_global_registry(fp, result)
        
        # Enhance relationships
        for fp, result in results.items():
            self._enhance_relationships(fp, result)
        
        elapsed = time.time() - start_time
        logger.info(f"Parsed {len(results)} Java files in {elapsed:.2f}s")
        
        return results
    
    def _build_global_registry(self, file_path: str, result: ParseResult):
        """Build global class/interface registry."""
        for symbol in result.symbols:
            if symbol.symbol_type == SymbolType.CLASS:
                self._global_classes[symbol.name] = file_path
                if symbol.full_name:
                    self._global_classes[symbol.full_name] = file_path
            elif symbol.symbol_type == SymbolType.INTERFACE:
                self._global_interfaces[symbol.name] = file_path
                if symbol.full_name:
                    self._global_interfaces[symbol.full_name] = file_path
    
    def _enhance_relationships(self, file_path: str, result: ParseResult):
        """Enhance relationships with cross-file info."""
        for rel in result.relationships:
            target = rel.target_symbol
            
            # Extract simple name from qualified
            simple_name = target.split('.')[-1] if '.' in target else target
            
            # Check global registries
            if target in self._global_classes:
                target_file = self._global_classes[target]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True
            elif simple_name in self._global_classes:
                target_file = self._global_classes[simple_name]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True
            elif target in self._global_interfaces:
                target_file = self._global_interfaces[target]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True
            elif simple_name in self._global_interfaces:
                target_file = self._global_interfaces[simple_name]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True


# Register the parser
parser_registry.register_parser(JavaParser())
