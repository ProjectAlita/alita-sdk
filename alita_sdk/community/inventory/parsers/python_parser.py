"""
Python Parser - Uses built-in ast module for AST parsing.

This parser provides comprehensive Python AST analysis with support for:
- Complete symbol extraction (functions, classes, methods, variables)
- Relationship detection (inheritance, composition, calls, imports)
- Cross-file resolution with multi-file parsing
- Type annotation support
- Decorator support

No external dependencies required - uses Python's built-in ast module.
"""

import ast
import hashlib
import logging
import time
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any, Tuple

from .base import (
    BaseParser, ParseResult, Symbol, Relationship,
    SymbolType, RelationshipType, Scope, Position, Range,
    parser_registry
)

logger = logging.getLogger(__name__)


def _parse_single_file(file_path: str) -> Tuple[str, ParseResult]:
    """Parse a single Python file - used by parallel workers."""
    try:
        parser = PythonParser()
        result = parser.parse_file(file_path)
        return file_path, result
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return file_path, ParseResult(
            file_path=file_path,
            language="python",
            symbols=[],
            relationships=[]
        )


class PythonParser(BaseParser):
    """
    Python AST parser using built-in ast module.
    
    Extracts symbols and relationships from Python source code.
    """
    
    def __init__(self):
        super().__init__("python")
        self._current_file = ""
        self._current_content = ""
        
        # Cross-file resolution support
        self._global_class_locations: Dict[str, str] = {}
        self._global_function_locations: Dict[str, str] = {}
        self._global_symbol_registry: Dict[str, str] = {}
    
    def _get_supported_extensions(self) -> Set[str]:
        return {'.py', '.pyx', '.pyi', '.pyw'}
    
    def parse_file(self, file_path: Union[str, Path], content: Optional[str] = None) -> ParseResult:
        """Parse a Python file and extract symbols and relationships."""
        start_time = time.time()
        file_path = str(file_path)
        self._current_file = file_path
        
        try:
            if content is None:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            
            self._current_content = content
            file_hash = hashlib.md5(content.encode()).hexdigest()
            
            try:
                ast_tree = ast.parse(content, filename=file_path)
            except SyntaxError as e:
                return ParseResult(
                    file_path=file_path,
                    language="python",
                    symbols=[],
                    relationships=[],
                    parse_time=time.time() - start_time,
                    errors=[f"Syntax error: {e}"]
                )
            
            symbols = self._extract_symbols(ast_tree, file_path)
            relationships = self._extract_relationships(ast_tree, symbols, file_path)
            imports, exports = self._extract_module_info(ast_tree)
            module_docstring = ast.get_docstring(ast_tree)
            
            result = ParseResult(
                file_path=file_path,
                language="python",
                symbols=symbols,
                relationships=relationships,
                imports=imports,
                exports=exports,
                module_docstring=module_docstring,
                parse_time=time.time() - start_time
            )
            
            return self.validate_result(result)
            
        except Exception as e:
            logger.error(f"Failed to parse Python file {file_path}: {e}")
            return ParseResult(
                file_path=file_path,
                language="python",
                symbols=[],
                relationships=[],
                parse_time=time.time() - start_time,
                errors=[f"Parse error: {e}"]
            )
    
    def _extract_symbols(self, ast_tree: ast.AST, file_path: str) -> List[Symbol]:
        """Extract symbols from Python AST."""
        symbols = []
        
        class SymbolVisitor(ast.NodeVisitor):
            def __init__(self, parser):
                self.parser = parser
                self.scope_stack = []
            
            def visit_Module(self, node):
                symbols.append(Symbol(
                    name=Path(file_path).stem,
                    symbol_type=SymbolType.MODULE,
                    scope=Scope.GLOBAL,
                    range=Range(Position(1, 0), Position(len(self.parser._current_content.split('\n')), 0)),
                    file_path=file_path,
                    docstring=ast.get_docstring(node)
                ))
                self.generic_visit(node)
            
            def visit_ClassDef(self, node):
                parent = '.'.join(self.scope_stack) if self.scope_stack else None
                full_name = f"{parent}.{node.name}" if parent else node.name
                
                symbols.append(Symbol(
                    name=node.name,
                    symbol_type=SymbolType.CLASS,
                    scope=Scope.CLASS if self.scope_stack else Scope.GLOBAL,
                    range=self.parser._node_to_range(node),
                    file_path=file_path,
                    parent_symbol=parent,
                    full_name=full_name,
                    docstring=ast.get_docstring(node),
                    source_text=self.parser._extract_node_source(node)
                ))
                
                self.scope_stack.append(node.name)
                self.generic_visit(node)
                self.scope_stack.pop()
            
            def visit_FunctionDef(self, node):
                self._visit_function(node, is_async=False)
            
            def visit_AsyncFunctionDef(self, node):
                self._visit_function(node, is_async=True)
            
            def _visit_function(self, node, is_async=False):
                parent = '.'.join(self.scope_stack) if self.scope_stack else None
                full_name = f"{parent}.{node.name}" if parent else node.name
                
                # Determine if method or function
                is_method = any(s in [sym.name for sym in symbols if sym.symbol_type == SymbolType.CLASS] 
                               for s in self.scope_stack)
                
                return_type = self.parser._get_type_annotation(node.returns) if node.returns else None
                
                symbols.append(Symbol(
                    name=node.name,
                    symbol_type=SymbolType.METHOD if is_method else SymbolType.FUNCTION,
                    scope=Scope.FUNCTION,
                    range=self.parser._node_to_range(node),
                    file_path=file_path,
                    parent_symbol=parent,
                    full_name=full_name,
                    docstring=ast.get_docstring(node),
                    return_type=return_type,
                    is_async=is_async,
                    source_text=self.parser._extract_node_source(node),
                    signature=self.parser._build_signature(node, return_type)
                ))
                
                self.scope_stack.append(node.name)
                self.generic_visit(node)
                self.scope_stack.pop()
            
            def visit_Assign(self, node):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        parent = '.'.join(self.scope_stack) if self.scope_stack else None
                        scope = Scope.FUNCTION if self.scope_stack else Scope.GLOBAL
                        sym_type = SymbolType.CONSTANT if target.id.isupper() else SymbolType.VARIABLE
                        
                        symbols.append(Symbol(
                            name=target.id,
                            symbol_type=sym_type,
                            scope=scope,
                            range=self.parser._node_to_range(target),
                            file_path=file_path,
                            parent_symbol=parent
                        ))
                self.generic_visit(node)
            
            def visit_Import(self, node):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    symbols.append(Symbol(
                        name=name,
                        symbol_type=SymbolType.IMPORT,
                        scope=Scope.GLOBAL,
                        range=self.parser._node_to_range(node),
                        file_path=file_path,
                        metadata={'original': alias.name, 'alias': alias.asname}
                    ))
                self.generic_visit(node)
            
            def visit_ImportFrom(self, node):
                module = node.module or ""
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    symbols.append(Symbol(
                        name=name,
                        symbol_type=SymbolType.IMPORT,
                        scope=Scope.GLOBAL,
                        range=self.parser._node_to_range(node),
                        file_path=file_path,
                        metadata={'module': module, 'original': alias.name, 'alias': alias.asname}
                    ))
                self.generic_visit(node)
        
        visitor = SymbolVisitor(self)
        visitor.visit(ast_tree)
        return symbols
    
    def _extract_relationships(self, ast_tree: ast.AST, symbols: List[Symbol], file_path: str) -> List[Relationship]:
        """Extract relationships from Python AST."""
        relationships = []
        
        class RelVisitor(ast.NodeVisitor):
            def __init__(self, parser):
                self.parser = parser
                self.current_symbol = None
                self.scope_stack = []
            
            def visit_ClassDef(self, node):
                old_symbol = self.current_symbol
                self.current_symbol = node.name
                
                # Inheritance
                for base in node.bases:
                    base_name = self.parser._get_name(base)
                    if base_name:
                        relationships.append(Relationship(
                            source_symbol=node.name,
                            target_symbol=base_name,
                            relationship_type=RelationshipType.INHERITANCE,
                            source_file=file_path,
                            source_range=self.parser._node_to_range(base),
                            confidence=0.95
                        ))
                
                # Decorators
                for dec in node.decorator_list:
                    dec_name = self.parser._get_name(dec)
                    if dec_name:
                        relationships.append(Relationship(
                            source_symbol=dec_name,
                            target_symbol=node.name,
                            relationship_type=RelationshipType.DECORATES,
                            source_file=file_path,
                            source_range=self.parser._node_to_range(dec),
                            confidence=0.95
                        ))
                
                self.scope_stack.append(node.name)
                self.generic_visit(node)
                self.scope_stack.pop()
                self.current_symbol = old_symbol
            
            def visit_FunctionDef(self, node):
                self._visit_func(node)
            
            def visit_AsyncFunctionDef(self, node):
                self._visit_func(node)
            
            def _visit_func(self, node):
                old_symbol = self.current_symbol
                self.current_symbol = node.name
                
                # Decorators
                for dec in node.decorator_list:
                    dec_name = self.parser._get_name(dec)
                    if dec_name:
                        relationships.append(Relationship(
                            source_symbol=dec_name,
                            target_symbol=node.name,
                            relationship_type=RelationshipType.DECORATES,
                            source_file=file_path,
                            source_range=self.parser._node_to_range(dec),
                            confidence=0.95
                        ))
                
                self.scope_stack.append(node.name)
                self.generic_visit(node)
                self.scope_stack.pop()
                self.current_symbol = old_symbol
            
            def visit_Call(self, node):
                if self.current_symbol:
                    called = self.parser._get_name(node.func)
                    if called:
                        relationships.append(Relationship(
                            source_symbol=self.current_symbol,
                            target_symbol=called,
                            relationship_type=RelationshipType.CALLS,
                            source_file=file_path,
                            source_range=self.parser._node_to_range(node),
                            confidence=0.85
                        ))
                self.generic_visit(node)
            
            def visit_Import(self, node):
                module_name = Path(file_path).stem
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    relationships.append(Relationship(
                        source_symbol=module_name,
                        target_symbol=name,
                        relationship_type=RelationshipType.IMPORTS,
                        source_file=file_path,
                        source_range=self.parser._node_to_range(node),
                        confidence=1.0
                    ))
                self.generic_visit(node)
            
            def visit_ImportFrom(self, node):
                module_name = Path(file_path).stem
                from_module = node.module or ""
                for alias in node.names:
                    if alias.name == "*":
                        target = f"{from_module}.*"
                    else:
                        target = f"{from_module}.{alias.name}" if from_module else alias.name
                    
                    relationships.append(Relationship(
                        source_symbol=module_name,
                        target_symbol=target,
                        relationship_type=RelationshipType.IMPORTS,
                        source_file=file_path,
                        source_range=self.parser._node_to_range(node),
                        confidence=1.0
                    ))
                self.generic_visit(node)
        
        visitor = RelVisitor(self)
        visitor.visit(ast_tree)
        return relationships
    
    def _node_to_range(self, node: ast.AST) -> Range:
        """Convert AST node to Range."""
        start_line = getattr(node, 'lineno', 1)
        start_col = getattr(node, 'col_offset', 0)
        end_line = getattr(node, 'end_lineno', start_line)
        end_col = getattr(node, 'end_col_offset', start_col + 1)
        return Range(Position(start_line, start_col), Position(end_line, end_col))
    
    def _extract_node_source(self, node: ast.AST) -> str:
        """Extract source code for an AST node."""
        try:
            lines = self._current_content.split('\n')
            start = getattr(node, 'lineno', 1) - 1
            end = getattr(node, 'end_lineno', start + 1)
            if start < len(lines) and end <= len(lines):
                return '\n'.join(lines[start:end])
        except Exception:
            pass
        return ""
    
    def _get_name(self, node: ast.AST) -> Optional[str]:
        """Extract name from various AST node types."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return '.'.join(reversed(parts))
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        elif isinstance(node, ast.Subscript):
            return self._get_name(node.value)
        return None
    
    def _get_type_annotation(self, node: ast.AST) -> str:
        """Extract type annotation as string."""
        try:
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                return self._get_name(node) or "Any"
            elif isinstance(node, ast.Constant):
                return str(node.value)
            elif isinstance(node, ast.Subscript):
                value = self._get_type_annotation(node.value)
                slice_val = self._get_type_annotation(node.slice)
                return f"{value}[{slice_val}]"
            elif hasattr(ast, 'unparse'):
                return ast.unparse(node)
        except Exception:
            pass
        return "Any"
    
    def _build_signature(self, node: ast.FunctionDef, return_type: Optional[str]) -> str:
        """Build function signature string."""
        try:
            params = []
            for arg in node.args.args:
                p = arg.arg
                if arg.annotation:
                    p += f": {self._get_type_annotation(arg.annotation)}"
                params.append(p)
            
            if node.args.vararg:
                p = f"*{node.args.vararg.arg}"
                if node.args.vararg.annotation:
                    p += f": {self._get_type_annotation(node.args.vararg.annotation)}"
                params.append(p)
            
            if node.args.kwarg:
                p = f"**{node.args.kwarg.arg}"
                if node.args.kwarg.annotation:
                    p += f": {self._get_type_annotation(node.args.kwarg.annotation)}"
                params.append(p)
            
            sig = f"{node.name}({', '.join(params)})"
            if return_type:
                sig += f" -> {return_type}"
            return sig
        except Exception:
            return node.name
    
    def _extract_module_info(self, ast_tree: ast.Module) -> Tuple[List[str], List[str]]:
        """Extract imports and exports."""
        imports = []
        exports = []
        
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if alias.name == "*":
                        imports.append(f"{module}.*")
                    else:
                        imports.append(f"{module}.{alias.name}")
            elif isinstance(node, ast.Assign):
                if (len(node.targets) == 1 and 
                    isinstance(node.targets[0], ast.Name) and 
                    node.targets[0].id == "__all__" and
                    isinstance(node.value, ast.List)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            exports.append(elt.value)
        
        return imports, exports
    
    def parse_multiple_files(self, file_paths: List[str], max_workers: int = 4) -> Dict[str, ParseResult]:
        """
        Parse multiple Python files with cross-file resolution.
        
        Args:
            file_paths: List of file paths
            max_workers: Number of parallel workers
            
        Returns:
            Dict mapping file paths to ParseResult
        """
        results: Dict[str, ParseResult] = {}
        total = len(file_paths)
        
        # Reset global registries
        self._global_class_locations = {}
        self._global_function_locations = {}
        self._global_symbol_registry = {}
        
        # First pass: Parse all files in parallel
        logger.info(f"Parsing {total} Python files with {max_workers} workers")
        start_time = time.time()
        
        batch_size = 500
        num_batches = (total + batch_size - 1) // batch_size
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total)
            batch_files = file_paths[start_idx:end_idx]
            
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(_parse_single_file, fp): fp for fp in batch_files}
                    
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            fp, result = future.result(timeout=60)
                            results[fp] = result
                        except Exception as e:
                            fp = futures[future]
                            logger.error(f"Failed to parse {fp}: {e}")
                            results[fp] = ParseResult(
                                file_path=fp,
                                language="python",
                                symbols=[],
                                relationships=[],
                                errors=[str(e)]
                            )
            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} failed: {e}")
                for fp in batch_files:
                    if fp not in results:
                        try:
                            _, result = _parse_single_file(fp)
                            results[fp] = result
                        except Exception as inner_e:
                            results[fp] = ParseResult(
                                file_path=fp,
                                language="python",
                                symbols=[],
                                relationships=[],
                                errors=[str(inner_e)]
                            )
        
        # Build global symbol registry
        for fp, result in results.items():
            if result.symbols:
                self._extract_global_symbols(fp, result)
        
        # Enhance relationships with cross-file info
        for fp, result in results.items():
            if result.symbols:
                self._enhance_relationships(fp, result)
        
        elapsed = time.time() - start_time
        logger.info(f"Parsed {len(results)} Python files in {elapsed:.2f}s")
        
        return results
    
    def _extract_global_symbols(self, file_path: str, result: ParseResult):
        """Extract symbols for global cross-file resolution."""
        file_name = Path(file_path).stem
        
        for symbol in result.symbols:
            if symbol.symbol_type == SymbolType.CLASS:
                self._global_class_locations[symbol.name] = file_path
                self._global_symbol_registry[symbol.name] = f"{file_name}.{symbol.name}"
            elif symbol.symbol_type == SymbolType.FUNCTION:
                self._global_function_locations[symbol.name] = file_path
                self._global_symbol_registry[symbol.name] = f"{file_name}.{symbol.name}"
    
    def _enhance_relationships(self, file_path: str, result: ParseResult):
        """Enhance relationships with cross-file information."""
        for rel in result.relationships:
            target = rel.target_symbol
            
            # Check if target is in another file
            if target in self._global_class_locations:
                target_file = self._global_class_locations[target]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True
            elif target in self._global_function_locations:
                target_file = self._global_function_locations[target]
                if target_file != file_path:
                    rel.target_file = target_file
                    rel.is_cross_file = True
            elif '.' in target:
                # Check partial match
                parts = target.split('.')
                for part in parts:
                    if part in self._global_class_locations:
                        target_file = self._global_class_locations[part]
                        if target_file != file_path:
                            rel.target_file = target_file
                            rel.is_cross_file = True
                            break


# Register the parser
parser_registry.register_parser(PythonParser())
