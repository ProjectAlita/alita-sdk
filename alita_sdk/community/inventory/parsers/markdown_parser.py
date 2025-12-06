"""
Markdown/RST document parser for extracting references and links.

Unlike code parsers that extract symbols (functions, classes), document parsers
extract references and links from text content.
"""

import re
from typing import List, Optional, Dict, Tuple, Set
from pathlib import Path

from .base import (
    BaseParser, Symbol, Relationship, ParseResult,
    RelationshipType, Range
)


class MarkdownParser(BaseParser):
    """
    Parser for Markdown, RST, and plain text documents.
    
    Extracts:
    - Markdown links [text](url)
    - Wiki-style links [[Page]]
    - Image references
    - RST cross-references
    - ADR/RFC references
    - File path references
    """
    
    language = "markdown"
    file_extensions = ['.md', '.markdown', '.mdx', '.rst', '.txt']
    
    def __init__(self):
        """Initialize the Markdown parser."""
        super().__init__(language=self.language)
    
    def _get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {'.md', '.markdown', '.mdx', '.rst'}
    
    # Patterns for different reference types
    PATTERNS = {
        # Markdown links [text](url)
        'md_link': re.compile(r'\[([^\]]+)\]\(([^)]+)\)', re.MULTILINE),
        
        # Wiki-style links [[Page Name]] or [[Page|Display]]
        'wiki_link': re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', re.MULTILINE),
        
        # Markdown images ![alt](path)
        'md_image': re.compile(r'!\[([^\]]*)\]\(([^)]+)\)', re.MULTILINE),
        
        # Markdown reference-style links [text][ref]
        'md_ref_link': re.compile(r'\[([^\]]+)\]\[([^\]]+)\]', re.MULTILINE),
        
        # Markdown reference definitions [ref]: url
        'md_ref_def': re.compile(r'^\s*\[([^\]]+)\]:\s*(\S+)', re.MULTILINE),
        
        # RST :doc: and :ref: references
        'rst_doc_ref': re.compile(r':doc:`([^`]+)`', re.MULTILINE),
        'rst_ref': re.compile(r':ref:`([^`]+)`', re.MULTILINE),
        'rst_class_ref': re.compile(r':class:`([^`]+)`', re.MULTILINE),
        'rst_func_ref': re.compile(r':func:`([^`]+)`', re.MULTILINE),
        'rst_meth_ref': re.compile(r':meth:`([^`]+)`', re.MULTILINE),
        
        # ADR references (ADR-0001)
        'adr_ref': re.compile(r'(?:ADR|adr)[- ]?(\d{4})', re.MULTILINE),
        
        # RFC references
        'rfc_ref': re.compile(r'RFC[- ]?(\d+)', re.IGNORECASE),
        
        # File path references in text
        'file_path': re.compile(
            r'(?:^|\s)([a-zA-Z][\w/.-]+\.(?:py|js|ts|java|go|rs|kt|cs|swift|rb|php|c|cpp|h|md|yml|yaml|json))\b',
            re.MULTILINE
        ),
        
        # Code block with file reference
        'code_file_ref': re.compile(r'```\w*\s*(?://|#)\s*(?:file|source):\s*([^\n]+)', re.MULTILINE),
        
        # Headings (for document structure)
        'heading': re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE),
        
        # RST headings (underlined)
        'rst_heading': re.compile(r'^(.+)\n([=\-~`]+)$', re.MULTILINE),
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
        scope: str = "document",
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
        line: int
    ) -> Relationship:
        """Create a Relationship with proper fields."""
        return Relationship(
            source_symbol=source,
            target_symbol=target,
            relationship_type=rel_type,
            source_file=file_path,
            source_range=self._make_range(line),
            confidence=0.85
        )
    
    def _get_line_number(self, content: str, match_start: int) -> int:
        """Get line number from character position."""
        return content[:match_start].count('\n') + 1
    
    def parse_file(self, file_path: str, content: Optional[str] = None) -> ParseResult:
        """
        Parse a markdown/RST file for references and document structure.
        
        Args:
            file_path: Path to the file
            content: Optional file content (read from file if not provided)
            
        Returns:
            ParseResult with symbols (headings) and relationships (references)
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
        
        # Document name for source references
        doc_name = Path(file_path).stem
        
        # Extract headings as document structure symbols
        self._extract_headings(content, file_path, symbols)
        
        # Extract all references
        self._extract_links(content, file_path, doc_name, relationships)
        self._extract_wiki_links(content, file_path, doc_name, relationships)
        self._extract_images(content, file_path, doc_name, relationships)
        self._extract_rst_refs(content, file_path, doc_name, relationships)
        self._extract_document_refs(content, file_path, doc_name, relationships)
        self._extract_file_refs(content, file_path, doc_name, relationships)
        
        return ParseResult(
            symbols=symbols,
            relationships=relationships,
            errors=errors
        )
    
    def _extract_headings(self, content: str, file_path: str, symbols: List[Symbol]):
        """Extract headings as document structure."""
        # Markdown headings
        for match in self.PATTERNS['heading'].finditer(content):
            level = len(match.group(1))
            title = match.group(2).strip()
            line = self._get_line_number(content, match.start())
            
            symbols.append(self._make_symbol(
                name=title,
                symbol_type=f"heading_h{level}",
                line=line,
                file_path=file_path,
                metadata={'level': level}
            ))
        
        # RST headings
        for match in self.PATTERNS['rst_heading'].finditer(content):
            title = match.group(1).strip()
            underline = match.group(2)
            line = self._get_line_number(content, match.start())
            
            # Determine level by underline character
            level_map = {'=': 1, '-': 2, '~': 3, '`': 4}
            level = level_map.get(underline[0], 2)
            
            symbols.append(self._make_symbol(
                name=title,
                symbol_type=f"heading_h{level}",
                line=line,
                file_path=file_path,
                metadata={'level': level, 'format': 'rst'}
            ))
    
    def _extract_links(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract markdown links."""
        for match in self.PATTERNS['md_link'].finditer(content):
            target = match.group(2)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_target(target),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
        
        # Reference definitions
        for match in self.PATTERNS['md_ref_def'].finditer(content):
            target = match.group(2)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_target(target),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
    
    def _extract_wiki_links(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract wiki-style links."""
        for match in self.PATTERNS['wiki_link'].finditer(content):
            target = match.group(1).strip()
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=target,
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
    
    def _extract_images(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract image references."""
        for match in self.PATTERNS['md_image'].finditer(content):
            target = match.group(2)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_target(target),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
    
    def _extract_rst_refs(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract RST cross-references."""
        rst_patterns = ['rst_doc_ref', 'rst_ref', 'rst_class_ref', 'rst_func_ref', 'rst_meth_ref']
        
        for pattern_name in rst_patterns:
            for match in self.PATTERNS[pattern_name].finditer(content):
                target = match.group(1)
                line = self._get_line_number(content, match.start())
                
                # Clean up RST target (remove ~ prefix for short names)
                if target.startswith('~'):
                    target = target[1:].split('.')[-1]
                
                relationships.append(self._make_relationship(
                    source=doc_name,
                    target=target,
                    rel_type=RelationshipType.REFERENCES,
                    file_path=file_path,
                    line=line
                ))
    
    def _extract_document_refs(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract ADR, RFC, and similar document references."""
        # ADR references
        for match in self.PATTERNS['adr_ref'].finditer(content):
            adr_num = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=f"ADR-{adr_num}",
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
        
        # RFC references
        for match in self.PATTERNS['rfc_ref'].finditer(content):
            rfc_num = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=f"RFC-{rfc_num}",
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
    
    def _extract_file_refs(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract file path references."""
        for match in self.PATTERNS['file_path'].finditer(content):
            target = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=target,
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
        
        # Code block file references
        for match in self.PATTERNS['code_file_ref'].finditer(content):
            target = match.group(1).strip()
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=target,
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
    
    def _normalize_target(self, target: str) -> str:
        """Normalize link target to a clean reference name."""
        # Remove URL scheme for external links
        if target.startswith(('http://', 'https://')):
            return target
        
        # Clean relative paths
        target = target.strip()
        if target.startswith('./'):
            target = target[2:]
        
        # Extract filename without extension for local files
        if '/' in target or '.' in target:
            path = Path(target)
            if path.suffix in ['.md', '.html', '.rst']:
                return path.stem
        
        return target
