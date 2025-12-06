"""
Kotlin Parser - Regex-based parser for Kotlin source files.

Extracts symbols and relationships from .kt and .kts files using
comprehensive regex patterns. Supports Kotlin-specific features like
data classes, sealed classes, companion objects, extension functions,
and coroutines.
"""

import re
from typing import Dict, List, Optional, Set, Tuple, Union, Any
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


# Comprehensive Kotlin regex patterns
PATTERNS = {
    # Package declaration
    'package': re.compile(
        r'^\s*package\s+([\w.]+)',
        re.MULTILINE
    ),
    
    # Import patterns
    'import': re.compile(
        r'^\s*import\s+([\w.]+)(?:\s+as\s+(\w+))?',
        re.MULTILINE
    ),
    'import_wildcard': re.compile(
        r'^\s*import\s+([\w.]+)\.\*',
        re.MULTILINE
    ),
    
    # Class declarations
    'class': re.compile(
        r'^\s*(?:(public|private|protected|internal)\s+)?'
        r'(?:(abstract|open|final|sealed|data|enum|annotation|inner|value)\s+)*'
        r'class\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*\([^)]*\))?'  # Primary constructor
        r'(?:\s*:\s*([^{]+))?',  # Inheritance
        re.MULTILINE
    ),
    
    # Interface declarations
    'interface': re.compile(
        r'^\s*(?:(public|private|protected|internal)\s+)?'
        r'(?:(fun)\s+)?'  # fun interface
        r'interface\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'(?:\s*:\s*([^{]+))?',  # Extended interfaces
        re.MULTILINE
    ),
    
    # Object declarations (singleton, companion)
    'object': re.compile(
        r'^\s*(?:(public|private|protected|internal)\s+)?'
        r'(?:(companion)\s+)?'
        r'object\s+(\w+)?'
        r'(?:\s*:\s*([^{]+))?',
        re.MULTILINE
    ),
    
    # Function declarations
    'function': re.compile(
        r'^\s*(?:(public|private|protected|internal|override|open|final|abstract|inline|suspend|tailrec|operator|infix|external)\s+)*'
        r'fun\s+'
        r'(?:<[^>]+>\s+)?'  # Generic parameters
        r'(?:(\w+)\.)?'  # Extension receiver
        r'(\w+)'  # Function name
        r'\s*\([^)]*\)'  # Parameters
        r'(?:\s*:\s*([^\n{=]+))?',  # Return type
        re.MULTILINE
    ),
    
    # Property declarations
    'property': re.compile(
        r'^\s*(?:(public|private|protected|internal|override|open|final|abstract|lateinit|const)\s+)*'
        r'(val|var)\s+'
        r'(?:(\w+)\.)?'  # Extension receiver
        r'(\w+)'  # Property name
        r'(?:\s*:\s*([^\n=]+))?'  # Type
        r'(?:\s*(?:=|by)\s*([^\n]+))?',  # Initializer or delegate
        re.MULTILINE
    ),
    
    # Type alias
    'typealias': re.compile(
        r'^\s*(?:(public|private|protected|internal)\s+)?'
        r'typealias\s+(\w+)'
        r'(?:<[^>]+>)?'  # Generic parameters
        r'\s*=\s*([^\n]+)',
        re.MULTILINE
    ),
    
    # Annotations
    'annotation_use': re.compile(
        r'@(\w+)(?:\([^)]*\))?',
        re.MULTILINE
    ),
    
    # Function calls
    'function_call': re.compile(
        r'(?:^|[^\w.])(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # Method calls (with receiver)
    'method_call': re.compile(
        r'\.(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # Constructor calls
    'constructor_call': re.compile(
        r'(?:^|[^\w])([A-Z]\w*)\s*\(',
        re.MULTILINE
    ),
    
    # Delegation (by keyword)
    'delegation': re.compile(
        r'(?:class|interface)\s+\w+[^{]*:\s*[^{]*\s+by\s+(\w+)',
        re.MULTILINE
    ),
    
    # Coroutine patterns
    'coroutine_launch': re.compile(
        r'(?:launch|async|runBlocking|withContext)\s*(?:\([^)]*\))?\s*\{',
        re.MULTILINE
    ),
    
    # Generic type usage
    'generic_usage': re.compile(
        r'<\s*([A-Z]\w*)\s*(?:,\s*[A-Z]\w*)*\s*>',
        re.MULTILINE
    ),
    
    # DSL patterns (common Kotlin builders)
    'dsl_builder': re.compile(
        r'(\w+)\s*\{\s*\n',
        re.MULTILINE
    ),
    
    # Destructuring
    'destructuring': re.compile(
        r'\(\s*(\w+(?:\s*,\s*\w+)*)\s*\)\s*=',
        re.MULTILINE
    ),
    
    # KDoc patterns
    'kdoc': re.compile(
        r'/\*\*\s*([\s\S]*?)\s*\*/',
        re.MULTILINE
    ),
    'kdoc_reference': re.compile(
        r'\[(\w+(?:\.\w+)*)\]',
        re.MULTILINE
    ),
}


class KotlinParser(BaseParser):
    """Kotlin source code parser using regex patterns."""
    
    # Global symbol registry for cross-file resolution
    _global_symbols: Dict[str, Set[str]] = {}
    _symbol_to_file: Dict[str, str] = {}
    
    def __init__(self):
        super().__init__("kotlin")
    
    def _get_supported_extensions(self) -> Set[str]:
        return {'.kt', '.kts'}
    
    def _make_range(self, content: str, start_offset: int, end_line: int) -> Range:
        """Create a Range object from content and offset."""
        start_line = content[:start_offset].count('\n') + 1
        # Find column (chars since last newline)
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
    
    def parse_file(self, file_path: Union[str, Path], content: Optional[str] = None) -> ParseResult:
        """Parse a Kotlin file and extract symbols and relationships."""
        import time
        start_time = time.time()
        file_path = str(file_path)
        
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
            file_path=file_path,
            language=self.language,
            symbols=symbols,
            relationships=relationships,
            parse_time=time.time() - start_time
        )
    
    def _extract_symbols(self, content: str, file_path: str) -> List[Symbol]:
        """Extract all symbols from Kotlin source code."""
        symbols = []
        package_name = self._extract_package(content)
        
        # Extract classes
        for match in PATTERNS['class'].finditer(content):
            visibility, modifiers, name, inheritance = match.groups()
            end_line = self._find_block_end(content, match.end())
            
            # Determine symbol type based on modifiers
            symbol_type = SymbolType.CLASS
            metadata = {'visibility': visibility or 'public'}
            
            if modifiers:
                metadata['modifiers'] = modifiers.strip()
                if 'enum' in modifiers:
                    symbol_type = SymbolType.ENUM
                elif 'data' in modifiers:
                    metadata['is_data_class'] = True
                elif 'sealed' in modifiers:
                    metadata['is_sealed'] = True
            
            qualified_name = f"{package_name}.{name}" if package_name else name
            docstring = self._find_preceding_kdoc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=symbol_type,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=end_line,
                scope=Scope.GLOBAL,
                full_name=qualified_name,
                docstring=docstring,
                visibility=visibility or 'public',
                metadata=metadata
            ))
        
        # Extract interfaces
        for match in PATTERNS['interface'].finditer(content):
            visibility, fun_modifier, name, extends = match.groups()
            end_line = self._find_block_end(content, match.end())
            
            metadata = {'visibility': visibility or 'public'}
            if fun_modifier:
                metadata['is_fun_interface'] = True
            
            qualified_name = f"{package_name}.{name}" if package_name else name
            docstring = self._find_preceding_kdoc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.INTERFACE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=end_line,
                scope=Scope.GLOBAL,
                full_name=qualified_name,
                docstring=docstring,
                visibility=visibility or 'public',
                metadata=metadata
            ))
        
        # Extract objects
        for match in PATTERNS['object'].finditer(content):
            visibility, companion, name, implements = match.groups()
            if not name and not companion:
                continue  # Skip anonymous objects in expressions
            
            obj_name = name if name else 'Companion'
            end_line = self._find_block_end(content, match.end())
            
            metadata = {'visibility': visibility or 'public'}
            if companion:
                metadata['is_companion'] = True
            
            qualified_name = f"{package_name}.{obj_name}" if package_name else obj_name
            docstring = self._find_preceding_kdoc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=obj_name,
                symbol_type=SymbolType.CLASS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=end_line,
                scope=Scope.GLOBAL,
                full_name=qualified_name,
                docstring=docstring,
                visibility=visibility or 'public',
                metadata=metadata
            ))
        
        # Extract functions
        for match in PATTERNS['function'].finditer(content):
            modifiers, receiver, name, return_type = match.groups()
            end_line = self._find_function_end(content, match.end())
            
            metadata = {}
            is_async = False
            if modifiers:
                modifier_list = modifiers.strip().split()
                metadata['modifiers'] = modifier_list
                if 'suspend' in modifier_list:
                    is_async = True
                    metadata['is_suspend'] = True
                if 'inline' in modifier_list:
                    metadata['is_inline'] = True
            
            if receiver:
                metadata['extension_receiver'] = receiver
            
            qualified_name = f"{package_name}.{name}" if package_name else name
            docstring = self._find_preceding_kdoc(content, match.start())
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.FUNCTION,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=end_line,
                scope=Scope.GLOBAL,
                full_name=qualified_name,
                docstring=docstring,
                is_async=is_async,
                return_type=return_type.strip() if return_type else None,
                metadata=metadata
            ))
        
        # Extract properties
        for match in PATTERNS['property'].finditer(content):
            modifiers, val_var, receiver, name, type_decl, initializer = match.groups()
            line = content[:match.start()].count('\n') + 1
            
            metadata = {'mutable': val_var == 'var'}
            if modifiers:
                metadata['modifiers'] = modifiers.strip().split()
            if receiver:
                metadata['extension_receiver'] = receiver
            if type_decl:
                metadata['type'] = type_decl.strip()
            
            qualified_name = f"{package_name}.{name}" if package_name else name
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.VARIABLE,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=line,
                scope=Scope.GLOBAL,
                full_name=qualified_name,
                metadata=metadata
            ))
        
        # Extract type aliases
        for match in PATTERNS['typealias'].finditer(content):
            visibility, name, aliased_type = match.groups()
            line = content[:match.start()].count('\n') + 1
            
            qualified_name = f"{package_name}.{name}" if package_name else name
            
            symbols.append(self._make_symbol(
                name=name,
                symbol_type=SymbolType.TYPE_ALIAS,
                content=content,
                file_path=file_path,
                start_offset=match.start(),
                end_line=line,
                scope=Scope.GLOBAL,
                full_name=qualified_name,
                visibility=visibility or 'public',
                metadata={'aliased_type': aliased_type.strip()}
            ))
        
        return symbols
    
    def _extract_relationships(
        self,
        content: str,
        file_path: str,
        symbols: List[Symbol]
    ) -> List[Relationship]:
        """Extract relationships from Kotlin source code."""
        relationships = []
        current_scope = Path(file_path).stem
        
        # Extract imports
        for match in PATTERNS['import'].finditer(content):
            import_path, alias = match.groups()
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=import_path,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'alias': alias} if alias else None
            ))
        
        # Extract wildcard imports
        for match in PATTERNS['import_wildcard'].finditer(content):
            import_path = match.group(1)
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=import_path,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'wildcard': True}
            ))
        
        # Extract inheritance relationships
        for match in PATTERNS['class'].finditer(content):
            _, _, class_name, inheritance = match.groups()
            if inheritance:
                parents = self._parse_inheritance(inheritance)
                for parent, rel_type in parents:
                    relationships.append(self._make_relationship(
                        source=class_name,
                        target=parent,
                        rel_type=rel_type,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract interface extension
        for match in PATTERNS['interface'].finditer(content):
            _, _, iface_name, extends = match.groups()
            if extends:
                for parent in self._parse_type_list(extends):
                    relationships.append(self._make_relationship(
                        source=iface_name,
                        target=parent,
                        rel_type=RelationshipType.INHERITANCE,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract object implementations
        for match in PATTERNS['object'].finditer(content):
            _, companion, obj_name, implements = match.groups()
            if implements and obj_name:
                for parent in self._parse_type_list(implements):
                    relationships.append(self._make_relationship(
                        source=obj_name,
                        target=parent,
                        rel_type=RelationshipType.IMPLEMENTATION,
                        file_path=file_path,
                        content=content,
                        offset=match.start()
                    ))
        
        # Extract delegation relationships
        for match in PATTERNS['delegation'].finditer(content):
            delegate = match.group(1)
            
            relationships.append(self._make_relationship(
                source=current_scope,
                target=delegate,
                rel_type=RelationshipType.COMPOSITION,
                file_path=file_path,
                content=content,
                offset=match.start(),
                metadata={'delegation': True}
            ))
        
        # Extract annotation usage
        for match in PATTERNS['annotation_use'].finditer(content):
            annotation = match.group(1)
            
            # Skip common built-in annotations
            if annotation not in {'Override', 'Deprecated', 'Suppress', 'JvmStatic', 
                                   'JvmField', 'JvmOverloads', 'JvmName', 'Throws',
                                   'Nullable', 'NotNull', 'Test', 'Before', 'After'}:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=annotation,
                    rel_type=RelationshipType.DECORATES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract function calls
        symbol_names = {s.name for s in symbols}
        for match in PATTERNS['function_call'].finditer(content):
            func_name = match.group(1)
            
            # Skip keywords and common functions
            if func_name not in symbol_names and func_name not in {
                'if', 'when', 'for', 'while', 'try', 'catch', 'finally',
                'return', 'throw', 'break', 'continue', 'print', 'println',
                'listOf', 'mapOf', 'setOf', 'arrayOf', 'mutableListOf',
                'mutableMapOf', 'mutableSetOf', 'lazy', 'require', 'check',
                'assert', 'error', 'TODO', 'also', 'apply', 'let', 'run', 'with'
            }:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=func_name,
                    rel_type=RelationshipType.CALLS,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        # Extract constructor calls
        for match in PATTERNS['constructor_call'].finditer(content):
            class_name = match.group(1)
            
            if class_name not in symbol_names:
                relationships.append(self._make_relationship(
                    source=current_scope,
                    target=class_name,
                    rel_type=RelationshipType.USES,
                    file_path=file_path,
                    content=content,
                    offset=match.start()
                ))
        
        return relationships
    
    def _extract_package(self, content: str) -> Optional[str]:
        """Extract package name from content."""
        match = PATTERNS['package'].search(content)
        return match.group(1) if match else None
    
    def _parse_inheritance(self, inheritance: str) -> List[Tuple[str, RelationshipType]]:
        """Parse inheritance clause to extract parent types."""
        results = []
        
        # Remove generic parameters for simpler parsing
        clean = re.sub(r'<[^>]*>', '', inheritance)
        
        # Split by comma
        for part in clean.split(','):
            part = part.strip()
            if not part:
                continue
            
            # Remove constructor call parentheses
            part = re.sub(r'\([^)]*\)', '', part).strip()
            
            # Get the type name
            type_name = part.split()[0] if part else None
            if type_name:
                # Heuristic: if it has parentheses in original, it's a class
                if '(' in inheritance and type_name in inheritance.split('(')[0]:
                    results.append((type_name, RelationshipType.INHERITANCE))
                else:
                    # Could be either, default to implementation for interfaces
                    results.append((type_name, RelationshipType.IMPLEMENTATION))
        
        return results
    
    def _parse_type_list(self, type_list: str) -> List[str]:
        """Parse a comma-separated list of types."""
        # Remove generic parameters
        clean = re.sub(r'<[^>]*>', '', type_list)
        
        types = []
        for part in clean.split(','):
            part = part.strip()
            if part:
                # Get just the type name
                type_name = part.split()[0]
                type_name = re.sub(r'\([^)]*\)', '', type_name).strip()
                if type_name:
                    types.append(type_name)
        
        return types
    
    def _find_preceding_kdoc(self, content: str, position: int) -> Optional[str]:
        """Find KDoc comment preceding a position."""
        # Look for KDoc before the position
        before = content[:position]
        match = re.search(r'/\*\*\s*([\s\S]*?)\s*\*/\s*$', before)
        
        if match:
            doc = match.group(1)
            # Clean up the doc
            lines = doc.split('\n')
            cleaned = []
            for line in lines:
                line = re.sub(r'^\s*\*\s?', '', line)
                cleaned.append(line.strip())
            return '\n'.join(cleaned).strip()
        
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
    
    def _find_function_end(self, content: str, start: int) -> int:
        """Find the end line of a function."""
        # Check for expression body (=) vs block body ({)
        rest = content[start:start + 100]
        
        if '=' in rest.split('\n')[0] and '{' not in rest.split('\n')[0]:
            # Expression body - find newline
            newline_pos = content.find('\n', start)
            return content[:newline_pos].count('\n') + 1 if newline_pos != -1 else content[:start].count('\n') + 1
        else:
            return self._find_block_end(content, start)
    
    def parse_multiple_files(
        self,
        files: List[Tuple[str, Optional[str]]],
        resolve_cross_file: bool = True,
        max_workers: int = 4
    ) -> Dict[str, ParseResult]:
        """
        Parse multiple Kotlin files with optional cross-file resolution.
        
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
parser_registry.register_parser(KotlinParser())
