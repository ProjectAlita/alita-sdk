"""
JavaScript/TypeScript Parser - Regex-based parsing.

This parser uses regex patterns for JavaScript/TypeScript analysis:
- Import/export detection
- Class and function extraction
- Inheritance patterns
- Function calls and references

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


# Comprehensive regex patterns for JavaScript/TypeScript
PATTERNS = {
    # ES6 imports
    'import_default': re.compile(
        r'import\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    ),
    'import_named': re.compile(
        r'import\s+\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    ),
    'import_all': re.compile(
        r'import\s+\*\s+as\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    ),
    'import_side_effect': re.compile(
        r'import\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    ),
    'import_type': re.compile(
        r'import\s+type\s+\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    ),
    
    # CommonJS
    'require': re.compile(
        r'(?:const|let|var)\s+(\w+)\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        re.MULTILINE
    ),
    'require_destructure': re.compile(
        r'(?:const|let|var)\s+\{([^}]+)\}\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        re.MULTILINE
    ),
    
    # Dynamic import
    'dynamic_import': re.compile(
        r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        re.MULTILINE
    ),
    
    # Exports
    'export_default': re.compile(
        r'export\s+default\s+(?:class|function|const|let|var)?\s*(\w+)?',
        re.MULTILINE
    ),
    'export_named': re.compile(
        r'export\s+(?:const|let|var|function|class|interface|type|enum)\s+(\w+)',
        re.MULTILINE
    ),
    'export_from': re.compile(
        r'export\s+\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    ),
    'export_all': re.compile(
        r'export\s+\*\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    ),
    
    # Classes
    'class_def': re.compile(
        r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?',
        re.MULTILINE
    ),
    
    # Functions
    'function_def': re.compile(
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)',
        re.MULTILINE
    ),
    'arrow_function': re.compile(
        r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>',
        re.MULTILINE
    ),
    'method_def': re.compile(
        r'^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{',
        re.MULTILINE
    ),
    
    # Interfaces and types (TypeScript)
    'interface_def': re.compile(
        r'(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?',
        re.MULTILINE
    ),
    'type_alias': re.compile(
        r'(?:export\s+)?type\s+(\w+)\s*=',
        re.MULTILINE
    ),
    'enum_def': re.compile(
        r'(?:export\s+)?enum\s+(\w+)',
        re.MULTILINE
    ),
    
    # Variables
    'const_def': re.compile(
        r'(?:export\s+)?const\s+(\w+)\s*(?::\s*[\w<>\[\]|&\s]+)?\s*=',
        re.MULTILINE
    ),
    
    # Function calls
    'function_call': re.compile(
        r'(?<![.\w])(\w+)\s*\(',
        re.MULTILINE
    ),
    
    # JSX component usage
    'jsx_component': re.compile(
        r'<([A-Z]\w*)[>\s/]',
        re.MULTILINE
    ),
    
    # Decorators (TypeScript/experimental)
    'decorator': re.compile(
        r'@(\w+)(?:\([^)]*\))?',
        re.MULTILINE
    ),
}


def _parse_single_file(file_path: str) -> Tuple[str, ParseResult]:
    """Parse a single JavaScript file."""
    try:
        parser = JavaScriptParser()
        result = parser.parse_file(file_path)
        return file_path, result
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return file_path, ParseResult(
            file_path=file_path,
            language="javascript",
            symbols=[],
            relationships=[]
        )


class JavaScriptParser(BaseParser):
    """
    JavaScript/TypeScript parser using regex patterns.
    
    Extracts imports, exports, classes, functions, and relationships.
    """
    
    def __init__(self):
        super().__init__("javascript")
        self._current_file = ""
        self._current_content = ""
        
        # Cross-file resolution
        self._global_exports: Dict[str, str] = {}  # export_name -> file_path
        self._global_classes: Dict[str, str] = {}
        self._global_functions: Dict[str, str] = {}
    
    def _get_supported_extensions(self) -> Set[str]:
        return {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}
    
    def parse_file(self, file_path: Union[str, Path], content: Optional[str] = None) -> ParseResult:
        """Parse a JavaScript/TypeScript file."""
        start_time = time.time()
        file_path = str(file_path)
        self._current_file = file_path
        
        try:
            if content is None:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            
            self._current_content = content
            
            symbols = self._extract_symbols(content, file_path)
            relationships = self._extract_relationships(content, symbols, file_path)
            imports = self._extract_imports(content)
            exports = self._extract_exports(content)
            
            result = ParseResult(
                file_path=file_path,
                language="javascript",
                symbols=symbols,
                relationships=relationships,
                imports=imports,
                exports=exports,
                parse_time=time.time() - start_time
            )
            
            return self.validate_result(result)
            
        except Exception as e:
            logger.error(f"Failed to parse JS file {file_path}: {e}")
            return ParseResult(
                file_path=file_path,
                language="javascript",
                symbols=[],
                relationships=[],
                parse_time=time.time() - start_time,
                errors=[str(e)]
            )
    
    def _extract_symbols(self, content: str, file_path: str) -> List[Symbol]:
        """Extract symbols from JavaScript content."""
        symbols = []
        lines = content.split('\n')
        
        # Module symbol
        symbols.append(Symbol(
            name=Path(file_path).stem,
            symbol_type=SymbolType.MODULE,
            scope=Scope.GLOBAL,
            range=Range(Position(1, 0), Position(len(lines), 0)),
            file_path=file_path
        ))
        
        # Classes
        for match in PATTERNS['class_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            class_name = match.group(1)
            extends = match.group(2)
            
            symbols.append(Symbol(
                name=class_name,
                symbol_type=SymbolType.CLASS,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                is_exported='export' in match.group(0),
                metadata={'extends': extends} if extends else {}
            ))
        
        # Interfaces (TypeScript)
        for match in PATTERNS['interface_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type=SymbolType.INTERFACE,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                is_exported='export' in match.group(0)
            ))
        
        # Type aliases
        for match in PATTERNS['type_alias'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type=SymbolType.TYPE_ALIAS,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                is_exported='export' in match.group(0)
            ))
        
        # Enums
        for match in PATTERNS['enum_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type=SymbolType.ENUM,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                is_exported='export' in match.group(0)
            ))
        
        # Functions
        for match in PATTERNS['function_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type=SymbolType.FUNCTION,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                is_async='async' in match.group(0),
                is_exported='export' in match.group(0)
            ))
        
        # Arrow functions
        for match in PATTERNS['arrow_function'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type=SymbolType.FUNCTION,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                is_async='async' in match.group(0)
            ))
        
        # Constants
        for match in PATTERNS['const_def'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            name = match.group(1)
            # Skip if already added as arrow function
            if not any(s.name == name and s.symbol_type == SymbolType.FUNCTION for s in symbols):
                symbols.append(Symbol(
                    name=name,
                    symbol_type=SymbolType.CONSTANT if name.isupper() else SymbolType.VARIABLE,
                    scope=Scope.GLOBAL,
                    range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                    file_path=file_path,
                    is_exported='export' in match.group(0)
                ))
        
        # Imports as symbols
        for match in PATTERNS['import_default'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type=SymbolType.IMPORT,
                scope=Scope.GLOBAL,
                range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                file_path=file_path,
                metadata={'from': match.group(2), 'type': 'default'}
            ))
        
        for match in PATTERNS['import_named'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            names = [n.strip().split(' as ')[0].strip() for n in match.group(1).split(',')]
            for name in names:
                if name:
                    symbols.append(Symbol(
                        name=name,
                        symbol_type=SymbolType.IMPORT,
                        scope=Scope.GLOBAL,
                        range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                        file_path=file_path,
                        metadata={'from': match.group(2), 'type': 'named'}
                    ))
        
        return symbols
    
    def _extract_relationships(self, content: str, symbols: List[Symbol], file_path: str) -> List[Relationship]:
        """Extract relationships from JavaScript content."""
        relationships = []
        module_name = Path(file_path).stem
        symbol_names = {s.name for s in symbols}
        
        # Import relationships
        for match in PATTERNS['import_default'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            relationships.append(Relationship(
                source_symbol=module_name,
                target_symbol=match.group(2),
                relationship_type=RelationshipType.IMPORTS,
                source_file=file_path,
                source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                confidence=1.0
            ))
        
        for match in PATTERNS['import_named'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            relationships.append(Relationship(
                source_symbol=module_name,
                target_symbol=match.group(2),
                relationship_type=RelationshipType.IMPORTS,
                source_file=file_path,
                source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                confidence=1.0
            ))
        
        for match in PATTERNS['import_all'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            relationships.append(Relationship(
                source_symbol=module_name,
                target_symbol=match.group(2),
                relationship_type=RelationshipType.IMPORTS,
                source_file=file_path,
                source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                confidence=1.0
            ))
        
        for match in PATTERNS['require'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            relationships.append(Relationship(
                source_symbol=module_name,
                target_symbol=match.group(2),
                relationship_type=RelationshipType.IMPORTS,
                source_file=file_path,
                source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                confidence=1.0
            ))
        
        for match in PATTERNS['dynamic_import'].finditer(content):
            line = content[:match.start()].count('\n') + 1
            relationships.append(Relationship(
                source_symbol=module_name,
                target_symbol=match.group(1),
                relationship_type=RelationshipType.IMPORTS,
                source_file=file_path,
                source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                confidence=0.9
            ))
        
        # Inheritance relationships
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
                    iface = iface.strip()
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
                    parent = parent.strip()
                    if parent:
                        relationships.append(Relationship(
                            source_symbol=iface_name,
                            target_symbol=parent,
                            relationship_type=RelationshipType.INHERITANCE,
                            source_file=file_path,
                            source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                            confidence=0.95
                        ))
        
        # JSX component usage
        for match in PATTERNS['jsx_component'].finditer(content):
            component = match.group(1)
            if component in symbol_names or component[0].isupper():
                line = content[:match.start()].count('\n') + 1
                relationships.append(Relationship(
                    source_symbol=module_name,
                    target_symbol=component,
                    relationship_type=RelationshipType.USES,
                    source_file=file_path,
                    source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                    confidence=0.85
                ))
        
        # Decorator relationships
        for match in PATTERNS['decorator'].finditer(content):
            dec_name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            
            # Find what's being decorated (next class/function)
            remaining = content[match.end():]
            class_match = PATTERNS['class_def'].search(remaining)
            func_match = PATTERNS['function_def'].search(remaining)
            
            target = None
            if class_match and (not func_match or class_match.start() < func_match.start()):
                target = class_match.group(1)
            elif func_match:
                target = func_match.group(1)
            
            if target:
                relationships.append(Relationship(
                    source_symbol=dec_name,
                    target_symbol=target,
                    relationship_type=RelationshipType.DECORATES,
                    source_file=file_path,
                    source_range=Range(Position(line, 0), Position(line, len(match.group(0)))),
                    confidence=0.90
                ))
        
        return relationships
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import paths."""
        imports = []
        
        for match in PATTERNS['import_default'].finditer(content):
            imports.append(match.group(2))
        for match in PATTERNS['import_named'].finditer(content):
            imports.append(match.group(2))
        for match in PATTERNS['import_all'].finditer(content):
            imports.append(match.group(2))
        for match in PATTERNS['import_side_effect'].finditer(content):
            imports.append(match.group(1))
        for match in PATTERNS['require'].finditer(content):
            imports.append(match.group(2))
        for match in PATTERNS['dynamic_import'].finditer(content):
            imports.append(match.group(1))
        
        return list(set(imports))
    
    def _extract_exports(self, content: str) -> List[str]:
        """Extract export names."""
        exports = []
        
        for match in PATTERNS['export_default'].finditer(content):
            if match.group(1):
                exports.append(match.group(1))
            else:
                exports.append('default')
        
        for match in PATTERNS['export_named'].finditer(content):
            exports.append(match.group(1))
        
        for match in PATTERNS['export_from'].finditer(content):
            names = [n.strip().split(' as ')[0].strip() for n in match.group(1).split(',')]
            exports.extend([n for n in names if n])
        
        return list(set(exports))
    
    def parse_multiple_files(self, file_paths: List[str], max_workers: int = 4) -> Dict[str, ParseResult]:
        """Parse multiple JavaScript files with cross-file resolution."""
        results: Dict[str, ParseResult] = {}
        total = len(file_paths)
        
        self._global_exports = {}
        self._global_classes = {}
        self._global_functions = {}
        
        logger.info(f"Parsing {total} JavaScript files")
        start_time = time.time()
        
        # Parse in parallel
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
                        language="javascript",
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
        logger.info(f"Parsed {len(results)} JavaScript files in {elapsed:.2f}s")
        
        return results
    
    def _build_global_registry(self, file_path: str, result: ParseResult):
        """Build global export registry."""
        for exp in result.exports:
            self._global_exports[exp] = file_path
        
        for symbol in result.symbols:
            if symbol.is_exported:
                if symbol.symbol_type == SymbolType.CLASS:
                    self._global_classes[symbol.name] = file_path
                elif symbol.symbol_type == SymbolType.FUNCTION:
                    self._global_functions[symbol.name] = file_path
    
    def _enhance_relationships(self, file_path: str, result: ParseResult):
        """Enhance relationships with cross-file info."""
        for rel in result.relationships:
            target = rel.target_symbol
            
            # Check global registries
            if target in self._global_exports:
                target_file = self._global_exports[target]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True
            elif target in self._global_classes:
                target_file = self._global_classes[target]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True
            elif target in self._global_functions:
                target_file = self._global_functions[target]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True


# Register the parser
parser_registry.register_parser(JavaScriptParser())
