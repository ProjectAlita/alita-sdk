"""
Go Parser - Regex-based parser for Go source files.

Extracts symbols and relationships from .go files using comprehensive
regex patterns. Supports Go-specific features like interfaces, goroutines,
channels, defer, and struct embedding.
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import logging

from .base import (
    BaseParser,
    ParseResult,
    Symbol,
    Relationship,
    RelationshipType,
    SymbolType,
    Scope,
    Position,
    Range,
    parser_registry,
)

logger = logging.getLogger(__name__)

from typing import Any


# Comprehensive Go regex patterns
PATTERNS = {
    # Package declaration
    'package': re.compile(
        r'^\s*package\s+(\w+)',
        re.MULTILINE
    ),
    
    # Import statements
    'import_single': re.compile(
        r'^\s*import\s+(?:(\w+)\s+)?"([^"]+)"',
        re.MULTILINE
    ),
    'import_block': re.compile(
        r'import\s*\(\s*([\s\S]*?)\s*\)',
        re.MULTILINE
    ),
    'import_line': re.compile(
        r'^\s*(?:(\w+)\s+)?"([^"]+)"',
        re.MULTILINE
    ),
    
    # Struct declarations
    'struct': re.compile(
        r'^\s*type\s+(\w+)\s+struct\s*\{',
        re.MULTILINE
    ),
    
    # Interface declarations
    'interface': re.compile(
        r'^\s*type\s+(\w+)\s+interface\s*\{',
        re.MULTILINE
    ),
    
    # Type alias and definitions
    'type_alias': re.compile(
        r'^\s*type\s+(\w+)\s*=\s*([^\n{]+)',
        re.MULTILINE
    ),
    'type_def': re.compile(
        r'^\s*type\s+(\w+)\s+([^\n={]+)',
        re.MULTILINE
    ),
    
    # Function declarations
    'function': re.compile(
        r'^\s*func\s+(\w+)\s*(?:\[[^\]]+\])?\s*\([^)]*\)\s*(?:\([^)]*\)|[^\n{]+)?',
        re.MULTILINE
    ),
    
    # Method declarations (with receiver)
    'method': re.compile(
        r'^\s*func\s+\(\s*(\w+)\s+\*?(\w+)\s*\)\s*(\w+)\s*(?:\[[^\]]+\])?\s*\([^)]*\)',
        re.MULTILINE
    ),
    
    # Variable declarations
    'var': re.compile(
        r'^\s*var\s+(\w+)\s+([^\n=]+)',
        re.MULTILINE
    ),
    'var_block': re.compile(
        r'var\s*\(\s*([\s\S]*?)\s*\)',
        re.MULTILINE
    ),
    
    # Constant declarations
    'const': re.compile(
        r'^\s*const\s+(\w+)\s*(?:([^\n=]+))?\s*=',
        re.MULTILINE
    ),
    'const_block': re.compile(
        r'const\s*\(\s*([\s\S]*?)\s*\)',
        re.MULTILINE
    ),
    
    # Struct field with embedded type
    'embedded_type': re.compile(
        r'^\s*\*?([A-Z]\w*)\s*$',
        re.MULTILINE
    ),
    
    # Struct field with type
    'struct_field': re.compile(
        r'^\s*(\w+)\s+(\*?\[?\]?\*?(?:map\[[^\]]+\])?[A-Z]\w*)',
        re.MULTILINE
    ),
    
    # Interface method
    'interface_method': re.compile(
        r'^\s*(\w+)\s*\([^)]*\)',
        re.MULTILINE
    ),
    
    # Function calls
    'function_call': re.compile(
        r'(?:^|[^\w.])(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # Method calls
    'method_call': re.compile(
        r'\.(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # Type assertions
    'type_assertion': re.compile(
        r'\.\(\s*\*?(\w+)\s*\)',
        re.MULTILINE
    ),
    
    # Struct literal / composite literal
    'struct_literal': re.compile(
        r'([A-Z]\w*)\s*\{',
        re.MULTILINE
    ),
    
    # Package qualified access
    'pkg_access': re.compile(
        r'(\w+)\.([A-Z]\w*)',
        re.MULTILINE
    ),
    
    # Goroutine
    'goroutine': re.compile(
        r'\bgo\s+(\w+)',
        re.MULTILINE
    ),
    
    # Channel operations
    'channel_make': re.compile(
        r'make\s*\(\s*chan\s+([^\),]+)',
        re.MULTILINE
    ),
    
    # Defer statement
    'defer': re.compile(
        r'\bdefer\s+(\w+)',
        re.MULTILINE
    ),
    
    # Error handling pattern
    'error_return': re.compile(
        r'return\s+(?:\w+,\s*)?(\w+Error|errors\.New|fmt\.Errorf)',
        re.MULTILINE
    ),
    
    # Doc comments
    'doc_comment': re.compile(
        r'^//\s*(.+)',
        re.MULTILINE
    ),
    
    # Build tags
    'build_tag': re.compile(
        r'//go:build\s+(.+)',
        re.MULTILINE
    ),
    'plus_build': re.compile(
        r'//\s*\+build\s+(.+)',
        re.MULTILINE
    ),
}


class GoParser(BaseParser):
    """Go source code parser using regex patterns."""
    
    # Global symbol registry for cross-file resolution
    _global_symbols: Dict[str, Set[str]] = {}
    _symbol_to_file: Dict[str, str] = {}
    
    def __init__(self):
        super().__init__("go")
    
    def _get_supported_extensions(self) -> Set[str]:
        return {'.go'}
    
    def _make_range(self, content: str, start_offset: int, end_line: int) -> Range:
        """Create a Range object from content and offset."""
        start_line = content[:start_offset].count('\n') + 1
        last_newline = content.rfind('\n', 0, start_offset)
        start_col = start_offset - last_newline - 1 if last_newline >= 0 else start_offset
        return Range(
            start=Position(line=start_line, column=start_col),
            end=Position(line=end_line, column=0)
        )
    
    def _make_symbol(
        self,
        name: str,
        symbol_type: SymbolType,
        content: str,
        file_path: str,
        start_offset: int,
        end_line: int,
        scope: Scope = Scope.GLOBAL,
        parent: Optional[str] = None,
        full_name: Optional[str] = None,
        docstring: Optional[str] = None,
        visibility: Optional[str] = None,
        is_static: bool = False,
        is_async: bool = False,
        return_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Symbol:
        """Create a Symbol with correct fields."""
        return Symbol(
            name=name,
            symbol_type=symbol_type,
            scope=scope,
            range=self._make_range(content, start_offset, end_line),
            file_path=file_path,
            parent_symbol=parent,
            full_name=full_name,
            visibility=visibility,
            is_static=is_static,
            is_async=is_async,
            docstring=docstring,
            return_type=return_type,
            metadata=metadata or {}
        )
    
    def _make_relationship(
        self,
        source: str,
        target: str,
        rel_type: RelationshipType,
        file_path: str,
        content: str,
        offset: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Relationship:
        """Create a Relationship with correct fields."""
        return Relationship(
            source_symbol=source,
            target_symbol=target,
            relationship_type=rel_type,
            source_file=file_path,
            source_range=self._make_range(content, offset, content[:offset].count('\n') + 1),
            metadata=metadata or {}
        )
    
    def parse_file(self, file_path: str, content: Optional[str] = None) -> ParseResult:
        """Parse Go source code and extract symbols and relationships."""
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                return ParseResult(
                    file_path=file_path,
                    language=self.language,
                    symbols=[],
                    relationships=[],
                    errors=[str(e)]
                )
        
        symbols = self._extract_symbols(content, file_path)
        relationships = self._extract_relationships(content, file_path, symbols)
        
        return ParseResult(
            symbols=symbols,
            relationships=relationships,
            file_path=file_path,
            language=self.language
        )
    
    def _extract_symbols(self, content: str, file_path: str) -> List[Symbol]:
        """Extract all symbols from Go source code."""
        symbols = []
        package_name = self._extract_package(content)
        
        # Extract structs
        for match in PATTERNS['struct'].finditer(content):
            name = match.group(1)
            
            docstring = self._find_preceding_doc(content, match.start())
            is_exported = name[0].isupper()
            
            # Find embedded types in struct
            struct_content = self._extract_block_content(content, match.end())
            embedded = self._find_embedded_types(struct_content)
            
            metadata = {'exported': is_exported}
            if embedded:
                metadata['embedded_types'] = embedded
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{package_name}.{name}" if package_name else name,
                docstring=docstring,
                visibility='public' if is_exported else 'private',
                metadata=metadata
            ))
        
        # Extract interfaces
        for match in PATTERNS['interface'].finditer(content):
            name = match.group(1)
            
            docstring = self._find_preceding_doc(content, match.start())
            is_exported = name[0].isupper()
            
            # Find embedded interfaces
            iface_content = self._extract_block_content(content, match.end())
            embedded = self._find_embedded_types(iface_content)
            
            metadata = {'exported': is_exported}
            if embedded:
                metadata['embedded_interfaces'] = embedded
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.INTERFACE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{package_name}.{name}" if package_name else name,
                docstring=docstring,
                visibility='public' if is_exported else 'private',
                metadata=metadata
            ))
        
        # Extract type aliases
        for match in PATTERNS['type_alias'].finditer(content):
            name, aliased = match.groups()
            line = content[:match.start()].count('\n') + 1
            
            # Skip if it's actually a struct or interface (handled above)
            if 'struct' in aliased or 'interface' in aliased:
                continue
            
            is_exported = name[0].isupper()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.TYPE_ALIAS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=line,
                full_name=f"{package_name}.{name}" if package_name else name,
                visibility='public' if is_exported else 'private',
                metadata={
                    'exported': is_exported,
                    'aliased_type': aliased.strip()
                }
            ))
        
        # Extract type definitions (non-alias, non-struct, non-interface)
        for match in PATTERNS['type_def'].finditer(content):
            name, underlying = match.groups()
            line = content[:match.start()].count('\n') + 1
            
            # Skip struct, interface, and already handled aliases
            if 'struct' in underlying or 'interface' in underlying or '=' in underlying:
                continue
            
            is_exported = name[0].isupper()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.TYPE_ALIAS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=line,
                full_name=f"{package_name}.{name}" if package_name else name,
                visibility='public' if is_exported else 'private',
                metadata={
                    'exported': is_exported,
                    'underlying_type': underlying.strip()
                }
            ))
        
        # Extract functions
        for match in PATTERNS['function'].finditer(content):
            name = match.group(1)
            
            docstring = self._find_preceding_doc(content, match.start())
            is_exported = name[0].isupper()
            
            # Parse return type if present
            full_match = match.group(0)
            return_type = self._extract_return_type(full_match)
            
            metadata = {'exported': is_exported}
            if return_type:
                metadata['return_type'] = return_type
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.FUNCTION,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{package_name}.{name}" if package_name else name,
                docstring=docstring,
                visibility='public' if is_exported else 'private',
                return_type=return_type,
                metadata=metadata
            ))
        
        # Extract methods
        for match in PATTERNS['method'].finditer(content):
            receiver_name, receiver_type, method_name = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            is_exported = method_name[0].isupper()
            
            symbols.append(self._make_symbol(
                name=method_name,
                symbol_type=SymbolType.METHOD,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{package_name}.{receiver_type}.{method_name}" if package_name else f"{receiver_type}.{method_name}",
                parent=receiver_type,
                docstring=docstring,
                visibility='public' if is_exported else 'private',
                metadata={
                    'exported': is_exported,
                    'receiver_type': receiver_type,
                    'receiver_name': receiver_name
                }
            ))
        
        # Extract package-level variables
        for match in PATTERNS['var'].finditer(content):
            name, var_type = match.groups()
            line = content[:match.start()].count('\n') + 1
            
            is_exported = name[0].isupper()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.VARIABLE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=line,
                full_name=f"{package_name}.{name}" if package_name else name,
                visibility='public' if is_exported else 'private',
                metadata={
                    'exported': is_exported,
                    'type': var_type.strip()
                }
            ))
        
        # Extract constants
        for match in PATTERNS['const'].finditer(content):
            name, const_type = match.groups()
            line = content[:match.start()].count('\n') + 1
            
            is_exported = name[0].isupper()
            
            metadata = {'exported': is_exported}
            if const_type:
                metadata['type'] = const_type.strip()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CONSTANT,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=line,
                full_name=f"{package_name}.{name}" if package_name else name,
                visibility='public' if is_exported else 'private',
                metadata=metadata
            ))
        
        return symbols
    
    def _extract_relationships(
        self,
        content: str,
        file_path: str,
        symbols: List[Symbol]
    ) -> List[Relationship]:
        """Extract relationships from Go source code."""
        relationships = []
        current_scope = Path(file_path).stem
        package_name = self._extract_package(content)
        
        # Extract single imports
        for match in PATTERNS['import_single'].finditer(content):
            alias, path = match.groups()
            
            relationships.append(self._make_relationship(
                source=package_name or current_scope,
                target=path,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'alias': alias} if alias else None
            ))
        
        # Extract import blocks
        for match in PATTERNS['import_block'].finditer(content):
            block_content = match.group(1)
            
            for line_match in PATTERNS['import_line'].finditer(block_content):
                alias, path = line_match.groups()
                
                metadata = {}
                if alias:
                    metadata['alias'] = alias
                if alias == '_':
                    metadata['blank_import'] = True
                
                relationships.append(self._make_relationship(
                    source=package_name or current_scope,
                    target=path,
                    rel_type=RelationshipType.IMPORTS,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata=metadata if metadata else None
                ))
        
        # Extract struct embedding (composition)
        for match in PATTERNS['struct'].finditer(content):
            struct_name = match.group(1)
            
            struct_content = self._extract_block_content(content, match.end())
            embedded = self._find_embedded_types(struct_content)
            
            for embedded_type in embedded:
                relationships.append(self._make_relationship(
                    source=struct_name,
                    target=embedded_type,
                    rel_type=RelationshipType.COMPOSITION,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata={'embedding': True}
                ))
        
        # Extract interface embedding
        for match in PATTERNS['interface'].finditer(content):
            iface_name = match.group(1)
            
            iface_content = self._extract_block_content(content, match.end())
            embedded = self._find_embedded_types(iface_content)
            
            for embedded_iface in embedded:
                relationships.append(self._make_relationship(
                    source=iface_name,
                    target=embedded_iface,
                    rel_type=RelationshipType.INHERITANCE,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata={'embedding': True}
                ))
        
        # Extract method relationships (receiver type)
        for match in PATTERNS['method'].finditer(content):
            _, receiver_type, method_name = match.groups()
            
            relationships.append(self._make_relationship(
                source=method_name,
                target=receiver_type,
                rel_type=RelationshipType.CONTAINS,
                file_path=file_path,
                content=content,
                offset=match.start()
            ))
        
        # Extract function calls
        symbol_names = {s.name for s in symbols}
        for match in PATTERNS['function_call'].finditer(content):
            func_name = match.group(1)
            
            # Skip keywords, builtins, and local symbols
            if func_name not in symbol_names and func_name not in {
                'if', 'for', 'switch', 'select', 'go', 'defer', 'return', 'range',
                'make', 'new', 'len', 'cap', 'append', 'copy', 'delete', 'close',
                'panic', 'recover', 'print', 'println', 'complex', 'real', 'imag',
                'func', 'type', 'var', 'const', 'map', 'chan', 'interface', 'struct'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=func_name,
                    rel_type=RelationshipType.CALLS,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract package-qualified calls
        for match in PATTERNS['pkg_access'].finditer(content):
            pkg, name = match.groups()
            
            # Skip if pkg looks like a variable (lowercase)
            if pkg[0].islower() and pkg not in {'os', 'io', 'fmt', 'log', 'net', 'http', 'sync', 'time', 'json', 'xml', 'sql'}:
                continue
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=f"{pkg}.{name}",
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                content=content,
                offset=match.start()
            ))
        
        # Extract struct literal usage (instantiation)
        for match in PATTERNS['struct_literal'].finditer(content):
            type_name = match.group(1)
            
            if type_name not in symbol_names:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=type_name,
                    rel_type=RelationshipType.USES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract type assertions
        for match in PATTERNS['type_assertion'].finditer(content):
            type_name = match.group(1)
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=type_name,
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'type_assertion': True}
            ))
        
        # Extract goroutine calls
        for match in PATTERNS['goroutine'].finditer(content):
            func_name = match.group(1)
            
            if func_name not in {'func'}:  # Skip anonymous functions
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=func_name,
                    rel_type=RelationshipType.CALLS,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata={'goroutine': True}
                ))
        
        # Extract deferred calls
        for match in PATTERNS['defer'].finditer(content):
            func_name = match.group(1)
            
            if func_name not in {'func'}:  # Skip anonymous functions
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=func_name,
                    rel_type=RelationshipType.CALLS,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata={'deferred': True}
                ))
        
        return relationships
    
    def _extract_package(self, content: str) -> Optional[str]:
        """Extract package name from content."""
        match = PATTERNS['package'].search(content)
        return match.group(1) if match else None
    
    def _extract_block_content(self, content: str, start: int) -> str:
        """Extract content between braces."""
        brace_count = 0
        block_start = None
        
        for i, char in enumerate(content[start:], start):
            if char == '{':
                if block_start is None:
                    block_start = i + 1
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and block_start is not None:
                    return content[block_start:i]
        
        return ""
    
    def _find_embedded_types(self, block_content: str) -> List[str]:
        """Find embedded types in a struct or interface block."""
        embedded = []
        
        for line in block_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            # Check for embedded type (just a type name, possibly with *)
            match = re.match(r'^\*?([A-Z]\w*)(?:\s*`[^`]*`)?$', line)
            if match:
                embedded.append(match.group(1))
        
        return embedded
    
    def _extract_return_type(self, func_decl: str) -> Optional[str]:
        """Extract return type from function declaration."""
        # Look for return type after parameters
        match = re.search(r'\)\s*(?:\([^)]+\)|([^\n{]+))', func_decl)
        if match:
            ret = match.group(1) or match.group(0)
            ret = ret.strip()
            if ret and not ret.startswith('{'):
                # Clean up
                ret = re.sub(r'^\)\s*', '', ret)
                return ret.strip() if ret else None
        return None
    
    def _find_preceding_doc(self, content: str, position: int) -> Optional[str]:
        """Find doc comment preceding a position."""
        before = content[:position]
        lines = before.split('\n')
        
        doc_lines = []
        for line in reversed(lines[:-1]):
            stripped = line.strip()
            if stripped.startswith('//'):
                # Skip build tags
                if stripped.startswith('//go:') or stripped.startswith('// +build'):
                    break
                doc_lines.insert(0, stripped[2:].strip())
            elif stripped == '':
                continue
            else:
                break
        
        return '\n'.join(doc_lines) if doc_lines else None
    
    def _find_block_end(self, content: str, start: int) -> int:
        """Find the end line of a code block."""
        brace_count = 0
        in_block = False
        
        for i, char in enumerate(content[start:], start):
            if char == '{':
                brace_count += 1
                in_block = True
            elif char == '}':
                brace_count -= 1
                if in_block and brace_count == 0:
                    return content[:i].count('\n') + 1
        
        return content[:start].count('\n') + 1
    
    def parse_multiple_files(
        self,
        files: List[Tuple[str, Optional[str]]],
        resolve_cross_file: bool = True,
        max_workers: int = 4
    ) -> Dict[str, ParseResult]:
        """
        Parse multiple Go files with optional cross-file resolution.
        
        Args:
            files: List of (file_path, content) tuples
            resolve_cross_file: Whether to resolve cross-file references
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dict mapping file paths to ParseResult objects
        """
        results = {}
        
        def parse_single(file_info: Tuple[str, Optional[str]]) -> Tuple[str, Optional[ParseResult]]:
            file_path, content = file_info
            if content is None:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {e}")
                    return file_path, None
            
            try:
                result = self.parse(content, file_path)
                return file_path, result
            except Exception as e:
                logger.warning(f"Failed to parse {file_path}: {e}")
                return file_path, None
        
        # Parse files in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for file_path, result in executor.map(parse_single, files):
                if result:
                    results[file_path] = result
                    
                    # Register symbols for cross-file resolution
                    if resolve_cross_file:
                        for symbol in result.symbols:
                            self._symbol_to_file[symbol.name] = file_path
                            if symbol.qualified_name:
                                self._symbol_to_file[symbol.qualified_name] = file_path
        
        return results


# Register the parser
parser_registry.register_parser(GoParser())
