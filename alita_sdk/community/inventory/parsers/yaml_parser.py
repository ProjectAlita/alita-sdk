"""
YAML/Configuration file parser for extracting references.

Extracts references from YAML, JSON, and config files including $ref, !include, and dependency declarations.
"""

import re
from typing import List, Optional, Set
from pathlib import Path

from .base import (
    BaseParser, Symbol, Relationship, ParseResult,
    RelationshipType, Range
)


class YAMLParser(BaseParser):
    """
    Parser for YAML and configuration files.
    
    Extracts:
    - $ref references (OpenAPI, JSON Schema)
    - !include directives
    - Dependency declarations
    - Service references
    - Environment variables
    """
    
    language = "yaml"
    file_extensions = ['.yml', '.yaml', '.json']
    
    def __init__(self):
        """Initialize the YAML parser."""
        super().__init__(language=self.language)
    
    def _get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {'.yml', '.yaml', '.json'}
    
    # Patterns for YAML/config references
    PATTERNS = {
        # JSON Schema / OpenAPI $ref
        'schema_ref': re.compile(r'\$ref:\s*[\'"]?([^\s\'"#]+(?:#[^\s\'"]*)?)[\'"]?', re.MULTILINE),
        
        # YAML !include directive
        'yaml_include': re.compile(r'!include\s+[\'"]?([^\s\'"]+)[\'"]?', re.MULTILINE),
        
        # Extends/inherits references
        'extends': re.compile(r'extends:\s*[\'"]?([^\s\'"]+)[\'"]?', re.MULTILINE),
        
        # File path references
        'file_ref': re.compile(r'(?:file|path|source|template):\s*[\'"]?([^\s\'"]+\.\w+)[\'"]?', re.MULTILINE),
        
        # Service/dependency names in docker-compose style
        'depends_on': re.compile(r'depends_on:\s*\n((?:\s+-\s*\w+\n?)+)', re.MULTILINE),
        'depends_on_item': re.compile(r'-\s*(\w+)', re.MULTILINE),
        
        # Image references
        'image_ref': re.compile(r'image:\s*[\'"]?([^\s\'"]+)[\'"]?', re.MULTILINE),
        
        # Environment variable references
        'env_var': re.compile(r'\$\{([A-Z_][A-Z0-9_]*)\}', re.MULTILINE),
        
        # Kubernetes references
        'k8s_configmap': re.compile(r'configMapKeyRef:\s*\n\s*name:\s*[\'"]?([^\s\'"]+)[\'"]?', re.MULTILINE),
        'k8s_secret': re.compile(r'secretKeyRef:\s*\n\s*name:\s*[\'"]?([^\s\'"]+)[\'"]?', re.MULTILINE),
        'k8s_service': re.compile(r'serviceName:\s*[\'"]?([^\s\'"]+)[\'"]?', re.MULTILINE),
        
        # GitHub Actions uses
        'gh_action': re.compile(r'uses:\s*[\'"]?([^\s\'"@]+)(?:@[^\s\'"]+)?[\'"]?', re.MULTILINE),
        
        # Module/package references
        'module_ref': re.compile(r'(?:module|package|import):\s*[\'"]?([^\s\'"]+)[\'"]?', re.MULTILINE),
        
        # URL references
        'url_ref': re.compile(r'(?:url|uri|endpoint|href):\s*[\'"]?(https?://[^\s\'"]+)[\'"]?', re.MULTILINE),
        
        # Top-level keys (for document structure)
        'top_level_key': re.compile(r'^([a-zA-Z_][a-zA-Z0-9_-]*):', re.MULTILINE),
    }
    
    def _make_range(self, start_line: int, end_line: int = None) -> Range:
        """Create a Range object."""
        return Range(
            start_line=start_line,
            end_line=end_line or start_line,
            start_col=0,
            end_col=0
        )
    
    def _make_symbol(
        self,
        name: str,
        symbol_type: str,
        line: int,
        file_path: str,
        scope: str = "config",
        **kwargs
    ) -> Symbol:
        """Create a Symbol with proper fields."""
        return Symbol(
            name=name,
            symbol_type=symbol_type,
            scope=scope,
            range=self._make_range(line),
            file_path=file_path,
            **kwargs
        )
    
    def _make_relationship(
        self,
        source: str,
        target: str,
        rel_type: RelationshipType,
        file_path: str,
        line: int,
        confidence: float = 0.90
    ) -> Relationship:
        """Create a Relationship with proper fields."""
        return Relationship(
            source_symbol=source,
            target_symbol=target,
            relationship_type=rel_type,
            source_file=file_path,
            source_range=self._make_range(line),
            confidence=confidence
        )
    
    def _get_line_number(self, content: str, match_start: int) -> int:
        """Get line number from character position."""
        return content[:match_start].count('\n') + 1
    
    def parse_file(self, file_path: str, content: Optional[str] = None) -> ParseResult:
        """
        Parse a YAML/config file for references.
        
        Args:
            file_path: Path to the file
            content: Optional file content (read from file if not provided)
            
        Returns:
            ParseResult with symbols (keys) and relationships (references)
        """
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                return ParseResult(symbols=[], relationships=[], errors=[f"Could not read {file_path}"])
        
        symbols: List[Symbol] = []
        relationships: List[Relationship] = []
        errors: List[str] = []
        
        # Config name for source references
        config_name = Path(file_path).stem
        
        # Extract top-level structure
        self._extract_structure(content, file_path, symbols)
        
        # Extract all reference types
        self._extract_schema_refs(content, file_path, config_name, relationships)
        self._extract_includes(content, file_path, config_name, relationships)
        self._extract_extends(content, file_path, config_name, relationships)
        self._extract_dependencies(content, file_path, config_name, relationships)
        self._extract_file_refs(content, file_path, config_name, relationships)
        self._extract_k8s_refs(content, file_path, config_name, relationships)
        self._extract_gh_actions(content, file_path, config_name, relationships)
        self._extract_url_refs(content, file_path, config_name, relationships)
        
        return ParseResult(
            symbols=symbols,
            relationships=relationships,
            errors=errors
        )
    
    def _extract_structure(self, content: str, file_path: str, symbols: List[Symbol]):
        """Extract top-level keys as config structure."""
        for match in self.PATTERNS['top_level_key'].finditer(content):
            key = match.group(1)
            line = self._get_line_number(content, match.start())
            
            # Skip common metadata keys
            if key.lower() not in ['version', 'kind', 'apiversion', 'metadata']:
                symbols.append(self._make_symbol(
                    name=key,
                    symbol_type="config_key",
                    line=line,
                    file_path=file_path
                ))
    
    def _extract_schema_refs(self, content: str, file_path: str, config_name: str, relationships: List[Relationship]):
        """Extract $ref references."""
        for match in self.PATTERNS['schema_ref'].finditer(content):
            ref = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=self._normalize_ref(ref),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line,
                confidence=0.95
            ))
    
    def _extract_includes(self, content: str, file_path: str, config_name: str, relationships: List[Relationship]):
        """Extract !include directives."""
        for match in self.PATTERNS['yaml_include'].finditer(content):
            include_path = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=include_path,
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                line=line,
                confidence=0.95
            ))
    
    def _extract_extends(self, content: str, file_path: str, config_name: str, relationships: List[Relationship]):
        """Extract extends references."""
        for match in self.PATTERNS['extends'].finditer(content):
            extends = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=extends,
                rel_type=RelationshipType.INHERITANCE,
                file_path=file_path,
                line=line,
                confidence=0.90
            ))
    
    def _extract_dependencies(self, content: str, file_path: str, config_name: str, relationships: List[Relationship]):
        """Extract service dependencies."""
        for match in self.PATTERNS['depends_on'].finditer(content):
            deps_block = match.group(1)
            line = self._get_line_number(content, match.start())
            
            for dep_match in self.PATTERNS['depends_on_item'].finditer(deps_block):
                dep_name = dep_match.group(1)
                relationships.append(self._make_relationship(
                    source=config_name,
                    target=dep_name,
                    rel_type=RelationshipType.USES,
                    file_path=file_path,
                    line=line,
                    confidence=0.90
                ))
        
        # Also extract image references
        for match in self.PATTERNS['image_ref'].finditer(content):
            image = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=image,
                rel_type=RelationshipType.USES,
                file_path=file_path,
                line=line,
                confidence=0.85
            ))
    
    def _extract_file_refs(self, content: str, file_path: str, config_name: str, relationships: List[Relationship]):
        """Extract file path references."""
        for match in self.PATTERNS['file_ref'].finditer(content):
            file_ref = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=file_ref,
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line,
                confidence=0.85
            ))
    
    def _extract_k8s_refs(self, content: str, file_path: str, config_name: str, relationships: List[Relationship]):
        """Extract Kubernetes resource references."""
        # ConfigMaps
        for match in self.PATTERNS['k8s_configmap'].finditer(content):
            configmap = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=f"configmap:{configmap}",
                rel_type=RelationshipType.USES,
                file_path=file_path,
                line=line,
                confidence=0.90
            ))
        
        # Secrets
        for match in self.PATTERNS['k8s_secret'].finditer(content):
            secret = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=f"secret:{secret}",
                rel_type=RelationshipType.USES,
                file_path=file_path,
                line=line,
                confidence=0.90
            ))
        
        # Services
        for match in self.PATTERNS['k8s_service'].finditer(content):
            service = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=f"service:{service}",
                rel_type=RelationshipType.USES,
                file_path=file_path,
                line=line,
                confidence=0.90
            ))
    
    def _extract_gh_actions(self, content: str, file_path: str, config_name: str, relationships: List[Relationship]):
        """Extract GitHub Actions references."""
        for match in self.PATTERNS['gh_action'].finditer(content):
            action = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=action,
                rel_type=RelationshipType.USES,
                file_path=file_path,
                line=line,
                confidence=0.95
            ))
    
    def _extract_url_refs(self, content: str, file_path: str, config_name: str, relationships: List[Relationship]):
        """Extract URL references."""
        for match in self.PATTERNS['url_ref'].finditer(content):
            url = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=config_name,
                target=url,
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line,
                confidence=0.80
            ))
    
    def _normalize_ref(self, ref: str) -> str:
        """Normalize a $ref value."""
        # Handle JSON pointer refs
        if ref.startswith('#/'):
            return ref
        
        # Handle file refs with anchors
        if '#' in ref:
            file_part, anchor = ref.split('#', 1)
            if file_part:
                return file_part
            return f"#{anchor}"
        
        return ref
