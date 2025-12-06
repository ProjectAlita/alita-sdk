"""
C#/.NET Parser - Regex-based parser for C# source files.

Extracts symbols and relationships from .cs files using comprehensive
regex patterns. Supports C# features like async/await, LINQ, generics,
records, nullable types, and pattern matching.
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


# Comprehensive C# regex patterns
PATTERNS = {
    # Namespace declaration
    'namespace': re.compile(
        r'^\s*namespace\s+([\w.]+)(?:\s*;|\s*\{)',
        re.MULTILINE
    ),
    
    # Using directives
    'using': re.compile(
        r'^\s*using\s+(?:static\s+)?([\w.]+)\s*;',
        re.MULTILINE
    ),
    'using_alias': re.compile(
        r'^\s*using\s+(\w+)\s*=\s*([\w.<>]+)\s*;',
        re.MULTILINE
    ),
    'using_global': re.compile(
        r'^\s*global\s+using\s+(?:static\s+)?([\w.]+)\s*;',
        re.MULTILINE
    ),
    
    # Class declarations
    'class': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'  # Attributes
        r'(?:(public|private|protected|internal)\s+)?'
        r'(?:(abstract|sealed|static|partial)\s+)*'
        r'class\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?',  # Inheritance
        re.MULTILINE
    ),
    
    # Record declarations (C# 9+)
    'record': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal)\s+)?'
        r'(?:(abstract|sealed)\s+)?'
        r'record\s+(?:struct\s+|class\s+)?'
        r'(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*\([^)]*\))?'  # Primary constructor
        r'(?:\s*:\s*([^{;]+))?',  # Inheritance
        re.MULTILINE
    ),
    
    # Interface declarations
    'interface': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal)\s+)?'
        r'(?:partial\s+)?'
        r'interface\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?',  # Extended interfaces
        re.MULTILINE
    ),
    
    # Struct declarations
    'struct': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal)\s+)?'
        r'(?:(readonly|ref|partial)\s+)*'
        r'struct\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?',  # Implemented interfaces
        re.MULTILINE
    ),
    
    # Enum declarations
    'enum': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal)\s+)?'
        r'enum\s+(\w+)'
        r'(?:\s*:\s*(\w+))?',  # Underlying type
        re.MULTILINE
    ),
    
    # Delegate declarations
    'delegate': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal)\s+)?'
        r'delegate\s+([\w<>,\s\[\]?]+)\s+(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # Method declarations
    'method': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal|new|override|virtual|abstract|sealed|static|extern|async|partial)\s+)*'
        r'([\w<>,\s\[\]?]+)\s+'  # Return type
        r'(\w+)\s*'  # Method name
        r'(?:<[^>]+>)?\s*'  # Generic parameters
        r'\([^)]*\)',  # Parameters
        re.MULTILINE
    ),
    
    # Property declarations
    'property': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal|new|override|virtual|abstract|sealed|static)\s+)*'
        r'(?:required\s+)?'
        r'([\w<>,\s\[\]?]+)\s+'  # Type
        r'(\w+)\s*'  # Property name
        r'(?:\{|=>)',
        re.MULTILINE
    ),
    
    # Field declarations
    'field': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal|new|static|readonly|const|volatile)\s+)*'
        r'([\w<>,\s\[\]?]+)\s+'  # Type
        r'(\w+)\s*'  # Field name
        r'(?:=|;)',
        re.MULTILINE
    ),
    
    # Event declarations
    'event': re.compile(
        r'^\s*(?:\[[\w\(\),\s]+\]\s*)*'
        r'(?:(public|private|protected|internal|static|virtual|override|new)\s+)*'
        r'event\s+'
        r'([\w<>,\s]+)\s+'  # Event type
        r'(\w+)',
        re.MULTILINE
    ),
    
    # Attribute usage
    'attribute': re.compile(
        r'\[(\w+)(?:\([^\]]*\))?\]',
        re.MULTILINE
    ),
    
    # Constructor calls (new keyword)
    'constructor_call': re.compile(
        r'new\s+([A-Z]\w*)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'\s*(?:\(|\{|\[)',
        re.MULTILINE
    ),
    
    # Method calls
    'method_call': re.compile(
        r'\.(\w+)\s*(?:<[^>]+>)?\s*\(',
        re.MULTILINE
    ),
    
    # Static method/property access
    'static_access': re.compile(
        r'([A-Z]\w*)\.(\w+)',
        re.MULTILINE
    ),
    
    # Generic type usage
    'generic_usage': re.compile(
        r'<\s*([A-Z]\w*)\s*(?:,\s*[A-Z]\w*)*\s*>',
        re.MULTILINE
    ),
    
    # typeof expression
    'typeof': re.compile(
        r'typeof\s*\(\s*(\w+)',
        re.MULTILINE
    ),
    
    # nameof expression
    'nameof': re.compile(
        r'nameof\s*\(\s*([\w.]+)',
        re.MULTILINE
    ),
    
    # LINQ query
    'linq_from': re.compile(
        r'\bfrom\s+\w+\s+in\s+(\w+)',
        re.MULTILINE
    ),
    
    # Extension method definition
    'extension_method': re.compile(
        r'static\s+[\w<>,\s\[\]?]+\s+(\w+)\s*\(\s*this\s+([\w<>,\s\[\]?]+)\s+(\w+)',
        re.MULTILINE
    ),
    
    # XML documentation
    'xml_doc': re.compile(
        r'///\s*(.+)',
        re.MULTILINE
    ),
    'xml_see_ref': re.compile(
        r'<see\s+cref="([^"]+)"',
        re.MULTILINE
    ),
}


class CSharpParser(BaseParser):
    """C# source code parser using regex patterns."""
    
    # Global symbol registry for cross-file resolution
    _global_symbols: Dict[str, Set[str]] = {}
    _symbol_to_file: Dict[str, str] = {}
    
    def __init__(self):
        super().__init__("csharp")
    
    def _get_supported_extensions(self) -> Set[str]:
        return {'.cs'}
    
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
        """Parse C# source code and extract symbols and relationships."""
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
        """Extract all symbols from C# source code."""
        symbols = []
        namespace = self._extract_namespace(content)
        
        # Extract classes
        for match in PATTERNS['class'].finditer(content):
            visibility, modifiers, name, inheritance = match.groups()
            
            metadata = {'visibility': visibility or 'internal'}
            if modifiers:
                metadata['modifiers'] = modifiers.strip().split()
            
            qualified_name = f"{namespace}.{name}" if namespace else name
            docstring = self._find_preceding_xml_doc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=qualified_name,
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata=metadata
            ))
        
        # Extract records
        for match in PATTERNS['record'].finditer(content):
            visibility, modifiers, name, inheritance = match.groups()
            
            metadata = {
                'visibility': visibility or 'internal',
                'is_record': True
            }
            if modifiers:
                metadata['modifiers'] = modifiers.strip().split()
            
            qualified_name = f"{namespace}.{name}" if namespace else name
            docstring = self._find_preceding_xml_doc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=qualified_name,
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata=metadata
            ))
        
        # Extract interfaces
        for match in PATTERNS['interface'].finditer(content):
            visibility, name, extends = match.groups()
            
            qualified_name = f"{namespace}.{name}" if namespace else name
            docstring = self._find_preceding_xml_doc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.INTERFACE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=qualified_name,
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata={'visibility': visibility or 'internal'}
            ))
        
        # Extract structs
        for match in PATTERNS['struct'].finditer(content):
            visibility, modifiers, name, implements = match.groups()
            
            metadata = {'visibility': visibility or 'internal'}
            if modifiers:
                metadata['modifiers'] = modifiers.strip().split()
            
            qualified_name = f"{namespace}.{name}" if namespace else name
            docstring = self._find_preceding_xml_doc(content, match.start())
            metadata['is_struct'] = True
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=qualified_name,
                docstring=docstring,
                visibility=visibility or 'internal',
                metadata=metadata
            ))
        
        # Extract enums
        for match in PATTERNS['enum'].finditer(content):
            visibility, name, underlying_type = match.groups()
            
            metadata = {'visibility': visibility or 'internal'}
            if underlying_type:
                metadata['underlying_type'] = underlying_type
            
            qualified_name = f"{namespace}.{name}" if namespace else name
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.ENUM,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=qualified_name,
                visibility=visibility or 'internal',
                metadata=metadata
            ))
        
        # Extract delegates
        for match in PATTERNS['delegate'].finditer(content):
            visibility, return_type, name = match.groups()
            
            qualified_name = f"{namespace}.{name}" if namespace else name
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.TYPE_ALIAS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=content[:match.start()].count('\n') + 1,
                full_name=qualified_name,
                visibility=visibility or 'internal',
                return_type=return_type.strip(),
                metadata={
                    'visibility': visibility or 'internal',
                    'is_delegate': True,
                    'return_type': return_type.strip()
                }
            ))
        
        # Extract methods
        for match in PATTERNS['method'].finditer(content):
            modifiers, return_type, name = match.groups()
            
            # Skip if it looks like a constructor or property getter/setter
            if name in {'get', 'set', 'init', 'add', 'remove'}:
                continue
            
            metadata = {}
            is_async = False
            is_static = False
            if modifiers:
                modifier_list = modifiers.strip().split()
                metadata['modifiers'] = modifier_list
                if 'async' in modifier_list:
                    is_async = True
                    metadata['is_async'] = True
                if 'static' in modifier_list:
                    is_static = True
                    metadata['is_static'] = True
            
            metadata['return_type'] = return_type.strip()
            docstring = self._find_preceding_xml_doc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.METHOD,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_method_end(content, match.end()),
                scope=Scope.CLASS,
                full_name=f"{namespace}.{name}" if namespace else name,
                docstring=docstring,
                is_async=is_async,
                is_static=is_static,
                return_type=return_type.strip(),
                metadata=metadata
            ))
        
        # Extract properties
        for match in PATTERNS['property'].finditer(content):
            modifiers, type_decl, name = match.groups()
            
            metadata = {'type': type_decl.strip(), 'is_property': True}
            if modifiers:
                modifier_list = modifiers.strip().split()
                metadata['modifiers'] = modifier_list
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.VARIABLE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=content[:match.start()].count('\n') + 1,
                scope=Scope.CLASS,
                full_name=f"{namespace}.{name}" if namespace else name,
                metadata=metadata
            ))
        
        # Extract events
        for match in PATTERNS['event'].finditer(content):
            modifiers, event_type, name = match.groups()
            
            metadata = {'event_type': event_type.strip(), 'is_event': True}
            if modifiers:
                metadata['modifiers'] = modifiers.strip().split()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.VARIABLE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=content[:match.start()].count('\n') + 1,
                scope=Scope.CLASS,
                full_name=f"{namespace}.{name}" if namespace else name,
                metadata=metadata
            ))
        
        return symbols
    
    def _extract_relationships(
        self,
        content: str,
        file_path: str,
        symbols: List[Symbol]
    ) -> List[Relationship]:
        """Extract relationships from C# source code."""
        relationships = []
        current_scope = Path(file_path).stem
        
        # Extract using directives
        for match in PATTERNS['using'].finditer(content):
            namespace_ref = match.group(1)
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=namespace_ref,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                content=content,
                offset=match.start()
            ))
        
        # Extract using aliases
        for match in PATTERNS['using_alias'].finditer(content):
            alias, type_ref = match.groups()
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=type_ref,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'alias': alias}
            ))
        
        # Extract global using
        for match in PATTERNS['using_global'].finditer(content):
            namespace_ref = match.group(1)
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=namespace_ref,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'global': True}
            ))
        
        # Extract class inheritance
        for match in PATTERNS['class'].finditer(content):
            _, _, class_name, inheritance = match.groups()
            if inheritance:
                for parent in self._parse_inheritance(inheritance):
                    rel_type = RelationshipType.IMPLEMENTATION if parent.startswith('I') and parent[1:2].isupper() else RelationshipType.INHERITANCE
                    relationships.append(self._make_relationship(
                        source=class_name,
                        target=parent,
                        rel_type=rel_type,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract record inheritance
        for match in PATTERNS['record'].finditer(content):
            _, _, record_name, inheritance = match.groups()
            if inheritance:
                for parent in self._parse_inheritance(inheritance):
                    rel_type = RelationshipType.IMPLEMENTATION if parent.startswith('I') and parent[1:2].isupper() else RelationshipType.INHERITANCE
                    relationships.append(self._make_relationship(
                        source=record_name,
                        target=parent,
                        rel_type=rel_type,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract interface extension
        for match in PATTERNS['interface'].finditer(content):
            _, iface_name, extends = match.groups()
            if extends:
                for parent in self._parse_inheritance(extends):
                    relationships.append(self._make_relationship(
                        source=iface_name,
                        target=parent,
                        rel_type=RelationshipType.INHERITANCE,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract struct implementations
        for match in PATTERNS['struct'].finditer(content):
            _, _, struct_name, implements = match.groups()
            if implements:
                for iface in self._parse_inheritance(implements):
                    relationships.append(self._make_relationship(
                        source=struct_name,
                        target=iface,
                        rel_type=RelationshipType.IMPLEMENTATION,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract attribute usage
        for match in PATTERNS['attribute'].finditer(content):
            attribute = match.group(1)
            
            # Skip common built-in attributes
            if attribute not in {'Serializable', 'Obsolete', 'Conditional', 'Flags',
                                  'DllImport', 'StructLayout', 'MarshalAs', 'FieldOffset',
                                  'Required', 'JsonProperty', 'JsonIgnore', 'Test', 
                                  'Fact', 'Theory', 'DataMember', 'DataContract'}:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=attribute,
                    rel_type=RelationshipType.DECORATES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract constructor calls
        symbol_names = {s.name for s in symbols}
        for match in PATTERNS['constructor_call'].finditer(content):
            class_name = match.group(1)
            
            if class_name not in symbol_names and class_name not in {
                'List', 'Dictionary', 'HashSet', 'StringBuilder', 'Task',
                'Exception', 'ArgumentException', 'Guid', 'DateTime', 'TimeSpan',
                'CancellationTokenSource', 'MemoryStream', 'StreamReader', 'StreamWriter'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=class_name,
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
                'ToString', 'GetType', 'Equals', 'GetHashCode', 'CompareTo',
                'Add', 'Remove', 'Contains', 'Clear', 'Count', 'Length',
                'Select', 'Where', 'OrderBy', 'GroupBy', 'Join', 'ToList', 'ToArray',
                'FirstOrDefault', 'First', 'Last', 'Any', 'All', 'Sum', 'Average',
                'ConfigureAwait', 'Wait', 'Result', 'GetAwaiter'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=method_name,
                    rel_type=RelationshipType.CALLS,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract static access
        for match in PATTERNS['static_access'].finditer(content):
            type_name, member = match.groups()
            
            if type_name not in symbol_names and type_name not in {
                'Console', 'Math', 'String', 'Convert', 'Enum', 'Array',
                'Task', 'File', 'Directory', 'Path', 'Environment',
                'Guid', 'DateTime', 'TimeSpan', 'Int32', 'Boolean', 'Double'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=type_name,
                    rel_type=RelationshipType.REFERENCES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract typeof references
        for match in PATTERNS['typeof'].finditer(content):
            type_name = match.group(1)
            
            if type_name not in symbol_names:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=type_name,
                    rel_type=RelationshipType.REFERENCES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract XML doc references
        for match in PATTERNS['xml_see_ref'].finditer(content):
            ref = match.group(1)
            
            # Extract just the type/member name
            ref_name = ref.split('.')[-1].split('(')[0]
            if ref_name:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=ref_name,
                    rel_type=RelationshipType.REFERENCES,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata={'from_documentation': True}
                ))
        
        return relationships
    
    def _extract_namespace(self, content: str) -> Optional[str]:
        """Extract namespace from content."""
        match = PATTERNS['namespace'].search(content)
        return match.group(1) if match else None
    
    def _parse_inheritance(self, inheritance: str) -> List[str]:
        """Parse inheritance clause to extract parent types."""
        # Remove generic parameters for simpler parsing
        clean = re.sub(r'<[^>]*>', '', inheritance)
        
        types = []
        for part in clean.split(','):
            part = part.strip()
            if part:
                # Get just the type name (without where clauses, etc.)
                type_name = part.split()[0].strip()
                if type_name and type_name != 'where':
                    types.append(type_name)
        
        return types
    
    def _find_preceding_xml_doc(self, content: str, position: int) -> Optional[str]:
        """Find XML documentation comment preceding a position."""
        before = content[:position]
        lines = before.split('\n')
        
        # Look for /// comments in preceding lines
        doc_lines = []
        for line in reversed(lines[:-1]):  # Skip current line
            stripped = line.strip()
            if stripped.startswith('///'):
                doc_lines.insert(0, stripped[3:].strip())
            elif stripped.startswith('['):
                # Skip attributes
                continue
            elif stripped == '':
                continue
            else:
                break
        
        if doc_lines:
            # Clean up XML tags
            doc = ' '.join(doc_lines)
            doc = re.sub(r'<[^>]+>', '', doc)
            return doc.strip()
        
        return None
    
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
    
    def _find_method_end(self, content: str, start: int) -> int:
        """Find the end line of a method."""
        # Check for expression body (=>) vs block body ({)
        rest = content[start:start + 100]
        
        if '=>' in rest.split('\n')[0] and '{' not in rest.split('\n')[0]:
            # Expression body - find semicolon
            semi_pos = content.find(';', start)
            return content[:semi_pos].count('\n') + 1 if semi_pos != -1 else content[:start].count('\n') + 1
        else:
            return self._find_block_end(content, start)
    
    def parse_multiple_files(
        self,
        files: List[Tuple[str, Optional[str]]],
        resolve_cross_file: bool = True,
        max_workers: int = 4
    ) -> Dict[str, ParseResult]:
        """
        Parse multiple C# files with optional cross-file resolution.
        
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
parser_registry.register_parser(CSharpParser())
