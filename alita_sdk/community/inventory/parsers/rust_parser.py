"""
Rust Parser - Regex-based parser for Rust source files.

Extracts symbols and relationships from .rs files using comprehensive
regex patterns. Supports Rust-specific features like traits, lifetimes,
macros, async/await, and pattern matching.
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


# Comprehensive Rust regex patterns
PATTERNS = {
    # Module declaration
    'mod_declaration': re.compile(
        r'^\s*(?:(pub(?:\([^)]+\))?)\s+)?mod\s+(\w+)\s*[{;]',
        re.MULTILINE
    ),
    
    # Use statements
    'use': re.compile(
        r'^\s*(?:(pub(?:\([^)]+\))?)\s+)?use\s+([\w:]+)(?:::\{([^}]+)\})?(?:\s+as\s+(\w+))?\s*;',
        re.MULTILINE
    ),
    'use_glob': re.compile(
        r'^\s*(?:pub(?:\([^)]+\))?\s+)?use\s+([\w:]+)::\*\s*;',
        re.MULTILINE
    ),
    
    # Struct declarations
    'struct': re.compile(
        r'^\s*(?:#\[[^\]]+\]\s*)*'  # Attributes
        r'(?:(pub(?:\([^)]+\))?)\s+)?'
        r'struct\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*\([^)]*\))?'  # Tuple struct
        r'(?:\s+where\s+[^{;]+)?',  # Where clause
        re.MULTILINE
    ),
    
    # Enum declarations
    'enum': re.compile(
        r'^\s*(?:#\[[^\]]+\]\s*)*'
        r'(?:(pub(?:\([^)]+\))?)\s+)?'
        r'enum\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s+where\s+[^{]+)?',  # Where clause
        re.MULTILINE
    ),
    
    # Trait declarations
    'trait': re.compile(
        r'^\s*(?:#\[[^\]]+\]\s*)*'
        r'(?:(pub(?:\([^)]+\))?)\s+)?'
        r'(?:(unsafe)\s+)?'
        r'trait\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?'  # Supertraits
        r'(?:\s+where\s+[^{]+)?',  # Where clause
        re.MULTILINE
    ),
    
    # Impl blocks
    'impl': re.compile(
        r'^\s*(?:(unsafe)\s+)?'
        r'impl\s*'
        r'(?:<[^>]+>\s*)?'  # Generic parameters
        r'(?:(\w+)\s+for\s+)?'  # Trait impl
        r'(\w+)'  # Type
        r'(?:<[^>]+>)?'  # Type parameters
        r'(?:\s+where\s+[^{]+)?',  # Where clause
        re.MULTILINE
    ),
    
    # Function declarations
    'function': re.compile(
        r'^\s*(?:#\[[^\]]+\]\s*)*'
        r'(?:(pub(?:\([^)]+\))?)\s+)?'
        r'(?:(const|async|unsafe|extern(?:\s+"[^"]*")?)\s+)*'
        r'fn\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'\s*\([^)]*\)'  # Parameters
        r'(?:\s*->\s*([^\n{;]+))?',  # Return type
        re.MULTILINE
    ),
    
    # Type alias
    'type_alias': re.compile(
        r'^\s*(?:(pub(?:\([^)]+\))?)\s+)?'
        r'type\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'\s*=\s*([^;]+);',
        re.MULTILINE
    ),
    
    # Const declarations
    'const': re.compile(
        r'^\s*(?:(pub(?:\([^)]+\))?)\s+)?'
        r'const\s+(\w+)\s*:\s*([^=]+)\s*=',
        re.MULTILINE
    ),
    
    # Static declarations
    'static': re.compile(
        r'^\s*(?:(pub(?:\([^)]+\))?)\s+)?'
        r'static\s+(?:mut\s+)?(\w+)\s*:\s*([^=]+)\s*=',
        re.MULTILINE
    ),
    
    # Macro definitions
    'macro_rules': re.compile(
        r'^\s*(?:#\[[^\]]+\]\s*)*'
        r'macro_rules!\s+(\w+)',
        re.MULTILINE
    ),
    
    # Declarative macro (macro 2.0)
    'macro_decl': re.compile(
        r'^\s*(?:(pub(?:\([^)]+\))?)\s+)?'
        r'macro\s+(\w+)',
        re.MULTILINE
    ),
    
    # Attribute macros and derive
    'attribute': re.compile(
        r'#\[(\w+)(?:\([^\]]*\))?\]',
        re.MULTILINE
    ),
    'derive': re.compile(
        r'#\[derive\(([^\]]+)\)\]',
        re.MULTILINE
    ),
    
    # Method calls
    'method_call': re.compile(
        r'\.(\w+)\s*(?::<[^>]+>)?\s*\(',
        re.MULTILINE
    ),
    
    # Function calls
    'function_call': re.compile(
        r'(?:^|[^\w.])(\w+)\s*(?::<[^>]+>)?\s*\(',
        re.MULTILINE
    ),
    
    # Macro invocations
    'macro_call': re.compile(
        r'(\w+)!\s*[\(\[\{]',
        re.MULTILINE
    ),
    
    # Type references (in type position)
    'type_ref': re.compile(
        r':\s*(?:&(?:\'[\w]+\s+)?(?:mut\s+)?)?([A-Z]\w*)',
        re.MULTILINE
    ),
    
    # Path expressions (e.g., std::collections::HashMap)
    'path_expr': re.compile(
        r'(\w+(?:::\w+)+)',
        re.MULTILINE
    ),
    
    # Struct instantiation
    'struct_init': re.compile(
        r'([A-Z]\w*)\s*(?:::<[^>]+>)?\s*\{',
        re.MULTILINE
    ),
    
    # Trait bounds
    'trait_bound': re.compile(
        r'(?:impl|dyn)\s+([A-Z]\w*)',
        re.MULTILINE
    ),
    
    # Doc comments
    'doc_comment': re.compile(
        r'///\s*(.+)',
        re.MULTILINE
    ),
    'doc_comment_block': re.compile(
        r'/\*\*\s*([\s\S]*?)\s*\*/',
        re.MULTILINE
    ),
    
    # Lifetime annotations (for metadata)
    'lifetime': re.compile(
        r"'(\w+)",
        re.MULTILINE
    ),
}


class RustParser(BaseParser):
    """Rust source code parser using regex patterns."""
    
    # Global symbol registry for cross-file resolution
    _global_symbols: Dict[str, Set[str]] = {}
    _symbol_to_file: Dict[str, str] = {}
    
    def __init__(self):
        super().__init__("rust")
    
    def _get_supported_extensions(self) -> Set[str]:
        return {'.rs'}
    
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
        """Parse Rust source code and extract symbols and relationships."""
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
        """Extract all symbols from Rust source code."""
        symbols = []
        module_name = self._extract_module_path(file_path)
        
        # Extract module declarations
        for match in PATTERNS['mod_declaration'].finditer(content):
            visibility, name = match.groups()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.MODULE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()) if '{' in match.group() else content[:match.start()].count('\n') + 1,
                full_name=f"{module_name}::{name}" if module_name else name,
                visibility=visibility or 'private',
                metadata={'visibility': visibility or 'private'}
            ))
        
        # Extract structs
        for match in PATTERNS['struct'].finditer(content):
            visibility, name = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            derives = self._find_derives_before(content, match.start())
            
            metadata = {'visibility': visibility or 'private'}
            if derives:
                metadata['derives'] = derives
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}::{name}" if module_name else name,
                docstring=docstring,
                visibility=visibility or 'private',
                metadata=metadata
            ))
        
        # Extract enums
        for match in PATTERNS['enum'].finditer(content):
            visibility, name = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            derives = self._find_derives_before(content, match.start())
            
            metadata = {'visibility': visibility or 'private'}
            if derives:
                metadata['derives'] = derives
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.ENUM,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}::{name}" if module_name else name,
                docstring=docstring,
                visibility=visibility or 'private',
                metadata=metadata
            ))
        
        # Extract traits
        for match in PATTERNS['trait'].finditer(content):
            visibility, unsafe_kw, name, supertraits = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            
            metadata = {'visibility': visibility or 'private'}
            if unsafe_kw:
                metadata['unsafe'] = True
            if supertraits:
                metadata['supertraits'] = [s.strip() for s in supertraits.split('+')]
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.INTERFACE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}::{name}" if module_name else name,
                docstring=docstring,
                visibility=visibility or 'private',
                metadata=metadata
            ))
        
        # Extract functions
        for match in PATTERNS['function'].finditer(content):
            visibility, modifiers, name, return_type = match.groups()
            
            docstring = self._find_preceding_doc(content, match.start())
            
            metadata = {'visibility': visibility or 'private'}
            is_async = False
            if modifiers:
                modifier_list = modifiers.strip().split()
                metadata['modifiers'] = modifier_list
                if 'async' in modifiers:
                    is_async = True
                    metadata['is_async'] = True
                if 'unsafe' in modifiers:
                    metadata['is_unsafe'] = True
                if 'const' in modifiers:
                    metadata['is_const'] = True
            if return_type:
                metadata['return_type'] = return_type.strip()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.FUNCTION,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}::{name}" if module_name else name,
                docstring=docstring,
                visibility=visibility or 'private',
                is_async=is_async,
                return_type=return_type.strip() if return_type else None,
                metadata=metadata
            ))
        
        # Extract type aliases
        for match in PATTERNS['type_alias'].finditer(content):
            visibility, name, aliased_type = match.groups()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.TYPE_ALIAS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=content[:match.start()].count('\n') + 1,
                full_name=f"{module_name}::{name}" if module_name else name,
                visibility=visibility or 'private',
                metadata={
                    'visibility': visibility or 'private',
                    'aliased_type': aliased_type.strip()
                }
            ))
        
        # Extract constants
        for match in PATTERNS['const'].finditer(content):
            visibility, name, const_type = match.groups()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.CONSTANT,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=content[:match.start()].count('\n') + 1,
                full_name=f"{module_name}::{name}" if module_name else name,
                visibility=visibility or 'private',
                metadata={
                    'visibility': visibility or 'private',
                    'type': const_type.strip()
                }
            ))
        
        # Extract statics
        for match in PATTERNS['static'].finditer(content):
            visibility, name, static_type = match.groups()
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.VARIABLE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=content[:match.start()].count('\n') + 1,
                full_name=f"{module_name}::{name}" if module_name else name,
                visibility=visibility or 'private',
                is_static=True,
                metadata={
                    'visibility': visibility or 'private',
                    'type': static_type.strip(),
                    'is_static': True
                }
            ))
        
        # Extract macro_rules definitions
        for match in PATTERNS['macro_rules'].finditer(content):
            name = match.group(1)
            
            docstring = self._find_preceding_doc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.FUNCTION,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=self._find_block_end(content, match.end()),
                full_name=f"{module_name}::{name}" if module_name else name,
                docstring=docstring,
                metadata={'is_macro': True}
            ))
        
        return symbols
    
    def _extract_relationships(
        self,
        content: str,
        file_path: str,
        symbols: List[Symbol]
    ) -> List[Relationship]:
        """Extract relationships from Rust source code."""
        relationships = []
        current_scope = Path(file_path).stem
        
        # Extract use statements
        for match in PATTERNS['use'].finditer(content):
            visibility, path, items, alias = match.groups()
            
            if items:
                # Multiple imports: use foo::{bar, baz}
                for item in items.split(','):
                    item = item.strip()
                    if item:
                        relationships.append(self._make_relationship(
                            source=current_scope,
                            target=f"{path}::{item}",
                            rel_type=RelationshipType.IMPORTS,
                            file_path=file_path,
                            content=content,
                            offset=match.start()
                        ))
            else:
                # Single import
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=path,
                    rel_type=RelationshipType.IMPORTS,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata={'alias': alias} if alias else None
                ))
        
        # Extract glob imports
        for match in PATTERNS['use_glob'].finditer(content):
            path = match.group(1)
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=path,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'glob': True}
            ))
        
        # Extract impl blocks (trait implementations)
        for match in PATTERNS['impl'].finditer(content):
            unsafe_kw, trait_name, type_name = match.groups()
            
            if trait_name:
                # Trait implementation
                relationships.append(self._make_relationship(
                    source=type_name,
                    target=trait_name,
                    rel_type=RelationshipType.IMPLEMENTATION,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata={'unsafe': True} if unsafe_kw else None
                ))
        
        # Extract trait supertraits
        for match in PATTERNS['trait'].finditer(content):
            _, _, trait_name, supertraits = match.groups()
            if supertraits:
                for supertrait in supertraits.split('+'):
                    supertrait = supertrait.strip()
                    if supertrait and not supertrait.startswith("'"):  # Skip lifetimes
                        relationships.append(self._make_relationship(
                            source=trait_name,
                            target=supertrait,
                            rel_type=RelationshipType.INHERITANCE,
                            file_path=file_path,
                            content=content,
                            offset=match.start()
                        ))
        
        # Extract derive macro usages
        for match in PATTERNS['derive'].finditer(content):
            derives = match.group(1)
            
            for derive in derives.split(','):
                derive = derive.strip()
                if derive:
                    relationships.append(self._make_relationship(
                        source=current_scope,
                        target=derive,
                        rel_type=RelationshipType.DECORATES,
                        file_path=file_path,
                        content=content,
                        offset=match.start(),
                        metadata={'derive': True}
                    ))
        
        # Extract attribute macro usages
        symbol_names = {s.name for s in symbols}
        for match in PATTERNS['attribute'].finditer(content):
            attr = match.group(1)
            
            # Skip built-in attributes
            if attr not in {
                'derive', 'cfg', 'test', 'bench', 'allow', 'warn', 'deny', 'forbid',
                'deprecated', 'must_use', 'doc', 'inline', 'cold', 'link', 'link_name',
                'no_mangle', 'repr', 'path', 'macro_use', 'macro_export', 'global_allocator',
                'feature', 'non_exhaustive', 'target_feature', 'track_caller'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=attr,
                    rel_type=RelationshipType.DECORATES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract function calls
        for match in PATTERNS['function_call'].finditer(content):
            func_name = match.group(1)
            
            # Skip keywords and common functions
            if func_name not in symbol_names and func_name not in {
                'if', 'match', 'while', 'for', 'loop', 'return', 'break', 'continue',
                'Some', 'None', 'Ok', 'Err', 'Box', 'Vec', 'String', 'Option', 'Result',
                'println', 'print', 'eprintln', 'eprint', 'format', 'panic', 'assert',
                'assert_eq', 'assert_ne', 'debug_assert', 'unreachable', 'unimplemented',
                'todo', 'cfg', 'env', 'concat', 'stringify', 'include', 'include_str',
                'include_bytes', 'file', 'line', 'column', 'module_path'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=func_name,
                    rel_type=RelationshipType.CALLS,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract macro calls
        for match in PATTERNS['macro_call'].finditer(content):
            macro_name = match.group(1)
            
            # Skip common std macros
            if macro_name not in {
                'println', 'print', 'eprintln', 'eprint', 'format', 'panic', 'assert',
                'assert_eq', 'assert_ne', 'debug_assert', 'debug_assert_eq', 'debug_assert_ne',
                'unreachable', 'unimplemented', 'todo', 'cfg', 'env', 'concat', 'stringify',
                'include', 'include_str', 'include_bytes', 'file', 'line', 'column',
                'module_path', 'vec', 'format_args', 'write', 'writeln', 'try', 'matches'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=macro_name,
                    rel_type=RelationshipType.CALLS,
                    file_path=file_path,
                    content=content,
                    offset=match.start(),
                    metadata={'macro': True}
                ))
        
        # Extract struct instantiations
        for match in PATTERNS['struct_init'].finditer(content):
            struct_name = match.group(1)
            
            if struct_name not in symbol_names:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=struct_name,
                    rel_type=RelationshipType.USES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract trait bound references
        for match in PATTERNS['trait_bound'].finditer(content):
            trait_name = match.group(1)
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=trait_name,
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'trait_bound': True}
            ))
        
        # Extract path expressions (crate paths)
        for match in PATTERNS['path_expr'].finditer(content):
            path = match.group(1)
            
            # Get the first component
            first_component = path.split('::')[0]
            if first_component not in {'self', 'super', 'crate', 'std', 'core', 'alloc'}:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=path,
                    rel_type=RelationshipType.REFERENCES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        return relationships
    
    def _extract_module_path(self, file_path: str) -> Optional[str]:
        """Extract module path from file path."""
        path = Path(file_path)
        
        # Get relative path components
        parts = []
        current = path
        while current.name not in {'src', 'lib', 'bin', ''}:
            if current.stem not in {'mod', 'lib', 'main'}:
                parts.insert(0, current.stem)
            current = current.parent
        
        return '::'.join(parts) if parts else None
    
    def _find_preceding_doc(self, content: str, position: int) -> Optional[str]:
        """Find doc comment preceding a position."""
        before = content[:position]
        lines = before.split('\n')
        
        # Look for /// comments in preceding lines
        doc_lines = []
        for line in reversed(lines[:-1]):  # Skip current line
            stripped = line.strip()
            if stripped.startswith('///'):
                doc_lines.insert(0, stripped[3:].strip())
            elif stripped.startswith('#['):
                # Skip attributes
                continue
            elif stripped == '':
                continue
            else:
                break
        
        return '\n'.join(doc_lines) if doc_lines else None
    
    def _find_derives_before(self, content: str, position: int) -> List[str]:
        """Find derive attributes before a position."""
        before = content[:position]
        
        # Look for #[derive(...)] in the preceding content
        derives = []
        for match in PATTERNS['derive'].finditer(before[-500:]):  # Look in last 500 chars
            for derive in match.group(1).split(','):
                derive = derive.strip()
                if derive:
                    derives.append(derive)
        
        return derives
    
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
        Parse multiple Rust files with optional cross-file resolution.
        
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
parser_registry.register_parser(RustParser())
