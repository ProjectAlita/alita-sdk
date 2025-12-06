"""
Swift Parser - Regex-based parser for Swift source files.

Extracts symbols and relationships from .swift files using comprehensive
regex patterns. Supports Swift-specific features like protocols, extensions,
optionals, closures, property wrappers, and async/await.
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


# Comprehensive Swift regex patterns
PATTERNS = {
    # Import statements
    'import': re.compile(
        r'^\s*import\s+(?:(\w+)\s+)?(\w+(?:\.\w+)*)',
        re.MULTILINE
    ),
    
    # Class declarations
    'class': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'  # Attributes
        r'(?:(open|public|internal|fileprivate|private)\s+)?'
        r'(?:(final)\s+)?'
        r'class\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?',  # Inheritance
        re.MULTILINE
    ),
    
    # Struct declarations
    'struct': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(public|internal|fileprivate|private)\s+)?'
        r'struct\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?',  # Protocol conformance
        re.MULTILINE
    ),
    
    # Protocol declarations
    'protocol': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(public|internal|fileprivate|private)\s+)?'
        r'protocol\s+(\w+)'
        r'(?:\s*:\s*([^{]+))?',  # Protocol inheritance
        re.MULTILINE
    ),
    
    # Enum declarations
    'enum': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(public|internal|fileprivate|private)\s+)?'
        r'(?:(indirect)\s+)?'
        r'enum\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?',  # Raw type or protocol conformance
        re.MULTILINE
    ),
    
    # Extension declarations
    'extension': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(public|internal|fileprivate|private)\s+)?'
        r'extension\s+(\w+)'
        r'(?:\s*:\s*([^{]+))?',  # Protocol conformance
        re.MULTILINE
    ),
    
    # Actor declarations (Swift 5.5+)
    'actor': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(public|internal|fileprivate|private)\s+)?'
        r'actor\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?',  # Protocol conformance
        re.MULTILINE
    ),
    
    # Function declarations
    'function': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(open|public|internal|fileprivate|private)\s+)?'
        r'(?:(override|static|class|final|mutating|nonmutating|async|nonisolated)\s+)*'
        r'func\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'\s*\([^)]*\)'  # Parameters
        r'(?:\s*(?:async\s+)?(?:throws\s+)?->\s*([^\n{]+))?',  # Return type
        re.MULTILINE
    ),
    
    # Initializer declarations
    'init': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(public|internal|fileprivate|private)\s+)?'
        r'(?:(convenience|required|override)\s+)*'
        r'init\s*\??\s*\([^)]*\)',
        re.MULTILINE
    ),
    
    # Property declarations
    'property': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(open|public|internal|fileprivate|private)\s+)?'
        r'(?:(static|class|lazy|weak|unowned)\s+)*'
        r'(let|var)\s+(\w+)\s*:\s*([^\n=]+)',
        re.MULTILINE
    ),
    
    # Computed property
    'computed_property': re.compile(
        r'^\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:(public|internal|fileprivate|private)\s+)?'
        r'(?:(static|class)\s+)?'
        r'var\s+(\w+)\s*:\s*([^{]+)\s*\{',
        re.MULTILINE
    ),
    
    # Type alias
    'typealias': re.compile(
        r'^\s*(?:(public|internal|fileprivate|private)\s+)?'
        r'typealias\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'\s*=\s*([^\n]+)',
        re.MULTILINE
    ),
    
    # Associated type
    'associatedtype': re.compile(
        r'^\s*associatedtype\s+(\w+)'
        r'(?:\s*:\s*([^\n=]+))?'  # Type constraints
        r'(?:\s*=\s*([^\n]+))?',  # Default type
        re.MULTILINE
    ),
    
    # Property wrapper
    'property_wrapper': re.compile(
        r'@(\w+)(?:\([^)]*\))?',
        re.MULTILINE
    ),
    
    # Method calls
    'method_call': re.compile(
        r'\.(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # Function calls
    'function_call': re.compile(
        r'(?:^|[^\w.])(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # Type references
    'type_ref': re.compile(
        r':\s*(?:\[)?(?:\w+\.)?([A-Z]\w*)',
        re.MULTILINE
    ),
    
    # Initializer calls
    'init_call': re.compile(
        r'([A-Z]\w*)\s*\(',
        re.MULTILINE
    ),
    
    # Generic type usage
    'generic_usage': re.compile(
        r'<\s*([A-Z]\w*)\s*(?:,\s*[A-Z]\w*)*\s*>',
        re.MULTILINE
    ),
    
    # Closure type
    'closure_type': re.compile(
        r'\(\s*(?:[^)]+)?\s*\)\s*(?:async\s+)?(?:throws\s+)?->\s*(\w+)',
        re.MULTILINE
    ),
    
    # Swift doc comments
    'doc_comment': re.compile(
        r'///\s*(.+)',
        re.MULTILINE
    ),
    'doc_comment_block': re.compile(
        r'/\*\*\s*([\s\S]*?)\s*\*/',
        re.MULTILINE
    ),
    
    # MARK comments (for structure understanding)
    'mark': re.compile(
        r'//\s*MARK:\s*-?\s*(.+)',
        re.MULTILINE
    ),
}


class SwiftParser(BaseParser):
    """Swift source code parser using regex patterns."""
    
    # Global symbol registry for cross-file resolution
    _global_symbols: Dict[str, Set[str]] = {}
    _symbol_to_file: Dict[str, str] = {}
    
    def __init__(self):
        super().__init__("swift")
    
    def _get_supported_extensions(self) -> Set[str]:
        return {'.swift'}
    
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
        """Parse Swift source code and extract symbols and relationships."""
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
        """Extract all symbols from Swift source code."""
        symbols = []
        module_name = Path(file_path).stem
        
        # Extract classes
        for match in PATTERNS['class'].finditer(content):
            visibility, final, name, inheritance = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            
            metadata = {'visibility': visibility or 'internal'}
            if final:
                metadata['final'] = True
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}.{name}",
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata=metadata
            ))
        
        # Extract structs
        for match in PATTERNS['struct'].finditer(content):
            visibility, name, conformance = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}.{name}",
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata={
                    'visibility': visibility or 'internal',
                    'is_struct': True
                }
            ))
        
        # Extract protocols
        for match in PATTERNS['protocol'].finditer(content):
            visibility, name, inheritance = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.INTERFACE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}.{name}",
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata={'visibility': visibility or 'internal'}
            ))
        
        # Extract enums
        for match in PATTERNS['enum'].finditer(content):
            visibility, indirect, name, raw_type = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            
            metadata = {'visibility': visibility or 'internal'}
            if indirect:
                metadata['indirect'] = True
            if raw_type:
                metadata['raw_type'] = raw_type.strip()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.ENUM,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}.{name}",
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata=metadata
            ))
        
        # Extract actors
        for match in PATTERNS['actor'].finditer(content):
            visibility, name, conformance = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}.{name}",
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata={
                    'visibility': visibility or 'internal',
                    'is_actor': True
                }
            ))
        
        # Extract extensions
        for match in PATTERNS['extension'].finditer(content):
            visibility, extended_type, conformance = match.groups()
            
            metadata = {'visibility': visibility or 'internal', 'is_extension': True}
            if conformance:
                metadata['conformance'] = [c.strip() for c in conformance.split(',')]
            
            symbols.append(self._make_symbol(
                name=f"{extended_type}_extension",
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}.{extended_type}_extension",
                visibility=visibility or 'internal',
                metadata=metadata
            ))
        
        # Extract functions
        for match in PATTERNS['function'].finditer(content):
            visibility, modifiers, name, return_type = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            
            metadata = {'visibility': visibility or 'internal'}
            is_async = False
            is_static = False
            if modifiers:
                modifier_list = modifiers.strip().split()
                metadata['modifiers'] = modifier_list
                if 'async' in modifier_list:
                    is_async = True
                    metadata['is_async'] = True
                if 'static' in modifier_list or 'class' in modifier_list:
                    is_static = True
                    metadata['is_static'] = True
            if return_type:
                metadata['return_type'] = return_type.strip()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.FUNCTION,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}.{name}",
                docstring=docstring,
                visibility=visibility or 'internal',
                is_static=is_static,
                is_async=is_async,
                return_type=return_type.strip() if return_type else None,
                metadata=metadata
            ))
        
        # Extract properties
        for match in PATTERNS['property'].finditer(content):
            visibility, modifiers, let_var, name, prop_type = match.groups()
            line = content[:match.start()].count('\n') + 1
            
            metadata = {
                'visibility': visibility or 'internal',
                'mutable': let_var == 'var',
                'type': prop_type.strip()
            }
            is_static = False
            if modifiers:
                modifier_list = modifiers.strip().split()
                metadata['modifiers'] = modifier_list
                if 'static' in modifier_list or 'class' in modifier_list:
                    is_static = True
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.VARIABLE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=line,
                full_name=f"{module_name}.{name}",
                visibility=visibility or 'internal',
                is_static=is_static,
                metadata=metadata
            ))
        
        # Extract type aliases
        for match in PATTERNS['typealias'].finditer(content):
            visibility, name, aliased_type = match.groups()
            line = content[:match.start()].count('\n') + 1
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.TYPE_ALIAS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=line,
                full_name=f"{module_name}.{name}",
                visibility=visibility or 'internal',
                metadata={
                    'visibility': visibility or 'internal',
                    'aliased_type': aliased_type.strip()
                }
            ))
        
        return symbols
    
    def _extract_relationships(
        self,
        content: str,
        file_path: str,
        symbols: List[Symbol]
    ) -> List[Relationship]:
        """Extract relationships from Swift source code."""
        relationships = []
        current_scope = Path(file_path).stem
        
        # Extract imports
        for match in PATTERNS['import'].finditer(content):
            kind, module = match.groups()
            
            metadata = {}
            if kind:
                metadata['kind'] = kind  # class, struct, func, etc.
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=module,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata=metadata if metadata else None
            ))
        
        # Extract class inheritance
        for match in PATTERNS['class'].finditer(content):
            _, _, class_name, inheritance = match.groups()
            if inheritance:
                parents = self._parse_inheritance(inheritance)
                for i, parent in enumerate(parents):
                    # First parent is superclass, rest are protocols
                    rel_type = RelationshipType.INHERITANCE if i == 0 and not parent.startswith('Any') else RelationshipType.IMPLEMENTATION
                    relationships.append(self._make_relationship(
                        source=class_name,
                        target=parent,
                        rel_type=rel_type,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract struct protocol conformance
        for match in PATTERNS['struct'].finditer(content):
            _, struct_name, conformance = match.groups()
            if conformance:
                for protocol in self._parse_inheritance(conformance):
                    relationships.append(self._make_relationship(
                        source=struct_name,
                        target=protocol,
                        rel_type=RelationshipType.IMPLEMENTATION,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract protocol inheritance
        for match in PATTERNS['protocol'].finditer(content):
            _, protocol_name, inheritance = match.groups()
            if inheritance:
                for parent in self._parse_inheritance(inheritance):
                    relationships.append(self._make_relationship(
                        source=protocol_name,
                        target=parent,
                        rel_type=RelationshipType.INHERITANCE,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract enum conformance
        for match in PATTERNS['enum'].finditer(content):
            _, _, enum_name, raw_or_conformance = match.groups()
            if raw_or_conformance:
                for item in self._parse_inheritance(raw_or_conformance):
                    # Could be raw type or protocol
                    relationships.append(self._make_relationship(
                        source=enum_name,
                        target=item,
                        rel_type=RelationshipType.IMPLEMENTATION,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract extension relationships
        for match in PATTERNS['extension'].finditer(content):
            _, extended_type, conformance = match.groups()
            
            # Extension extends a type
            relationships.append(self._make_relationship(
                source=f"{extended_type}_extension",
                target=extended_type,
                rel_type=RelationshipType.INHERITANCE,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'extension': True}
            ))
            
            # Protocol conformance in extension
            if conformance:
                for protocol in self._parse_inheritance(conformance):
                    relationships.append(self._make_relationship(
                        source=extended_type,
                        target=protocol,
                        rel_type=RelationshipType.IMPLEMENTATION,
                        file_path=file_path,
                        content=content,
                        offset=match.start(),
                        metadata={'via_extension': True}
                    ))
        
        # Extract property wrapper usage
        symbol_names = {s.name for s in symbols}
        for match in PATTERNS['property_wrapper'].finditer(content):
            wrapper = match.group(1)
            
            # Skip built-in attributes
            if wrapper not in {
                'available', 'objc', 'objcMembers', 'nonobjc', 'escaping', 'autoclosure',
                'discardableResult', 'inlinable', 'usableFromInline', 'frozen', 'unknown',
                'IBOutlet', 'IBAction', 'IBDesignable', 'IBInspectable', 'main', 'testable',
                'Published', 'State', 'Binding', 'ObservedObject', 'EnvironmentObject',
                'Environment', 'AppStorage', 'SceneStorage', 'FetchRequest', 'NSManaged'
            } and wrapper[0].isupper():
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=wrapper,
                    rel_type=RelationshipType.DECORATES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract initializer calls / type instantiation
        for match in PATTERNS['init_call'].finditer(content):
            type_name = match.group(1)
            
            if type_name not in symbol_names and type_name not in {
                'String', 'Int', 'Double', 'Float', 'Bool', 'Array', 'Dictionary', 'Set',
                'Optional', 'Result', 'UUID', 'URL', 'Date', 'Data', 'Error', 'NSError',
                'Range', 'ClosedRange', 'Substring', 'Character', 'CGFloat', 'CGPoint',
                'CGSize', 'CGRect', 'UIColor', 'NSColor', 'UIImage', 'NSImage', 'UIView',
                'NSView', 'DispatchQueue', 'Task', 'URLSession', 'JSONDecoder', 'JSONEncoder'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=type_name,
                    rel_type=RelationshipType.USES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract method calls
        for match in PATTERNS['method_call'].finditer(content):
            method_name = match.group(1)
            
            # Skip common methods
            if method_name not in {
                'map', 'flatMap', 'compactMap', 'filter', 'reduce', 'forEach', 'sorted',
                'first', 'last', 'append', 'insert', 'remove', 'contains', 'count',
                'isEmpty', 'joined', 'split', 'prefix', 'suffix', 'dropFirst', 'dropLast',
                'init', 'deinit', 'description', 'debugDescription', 'hash'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=method_name,
                    rel_type=RelationshipType.CALLS,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        return relationships
    
    def _parse_inheritance(self, inheritance: str) -> List[str]:
        """Parse inheritance/conformance clause to extract types."""
        # Remove generic parameters and where clauses
        clean = re.sub(r'<[^>]*>', '', inheritance)
        clean = re.sub(r'\s+where\s+.*', '', clean)
        
        types = []
        for part in clean.split(','):
            part = part.strip()
            if part:
                # Get just the type name
                type_name = part.split()[0].strip()
                if type_name:
                    types.append(type_name)
        
        return types
    
    def _find_preceding_doc(self, content: str, position: int) -> Optional[str]:
        """Find doc comment preceding a position."""
        before = content[:position]
        lines = before.split('\n')
        
        # Look for /// comments in preceding lines
        doc_lines = []
        for line in reversed(lines[:-1]):
            stripped = line.strip()
            if stripped.startswith('///'):
                doc_lines.insert(0, stripped[3:].strip())
            elif stripped.startswith('@'):
                # Skip attributes
                continue
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
        Parse multiple Swift files with optional cross-file resolution.
        
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
parser_registry.register_parser(SwiftParser())
