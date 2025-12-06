"""
HTML document parser for extracting links, scripts, and references.

Extracts links, script imports, stylesheets, and other references from HTML documents.
"""

import re
from typing import List, Optional, Set
from pathlib import Path

from .base import (
    BaseParser, Symbol, Relationship, ParseResult,
    RelationshipType, Range
)


class HTMLParser(BaseParser):
    """
    Parser for HTML documents.
    
    Extracts:
    - Anchor links (<a href="">)
    - Script imports (<script src="">)
    - Stylesheet links (<link href="">)
    - Image sources (<img src="">)
    - Form actions
    - Meta references
    - Embedded data attributes
    """
    
    language = "html"
    file_extensions = ['.html', '.htm', '.xhtml', '.vue', '.svelte']
    
    def __init__(self):
        """Initialize the HTML parser."""
        super().__init__(language=self.language)
    
    def _get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {'.html', '.htm', '.xhtml', '.vue', '.svelte'}
    
    # Patterns for HTML elements
    PATTERNS = {
        # Anchor links
        'anchor': re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # Script sources
        'script': re.compile(r'<script\s+[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # Stylesheet links
        'stylesheet': re.compile(r'<link\s+[^>]*href=["\']([^"\']+\.css(?:\?[^"\']*)?)["\']', re.IGNORECASE),
        
        # Image sources
        'image': re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # Form actions
        'form_action': re.compile(r'<form\s+[^>]*action=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # iframe sources
        'iframe': re.compile(r'<iframe\s+[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # Video/audio sources
        'media': re.compile(r'<(?:video|audio|source)\s+[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # Object/embed data
        'embed': re.compile(r'<(?:object|embed)\s+[^>]*(?:data|src)=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # Meta refresh/canonical
        'meta_url': re.compile(r'<meta\s+[^>]*(?:content|href)=["\'][^"\']*url=([^"\';\s]+)', re.IGNORECASE),
        
        # Background images in style
        'bg_image': re.compile(r'background(?:-image)?:\s*url\(["\']?([^"\')\s]+)["\']?\)', re.IGNORECASE),
        
        # Data attributes that might contain URLs
        'data_url': re.compile(r'data-(?:src|href|url)=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # Title tag (for document identification)
        'title': re.compile(r'<title>([^<]+)</title>', re.IGNORECASE),
        
        # ID attributes (for potential anchor targets)
        'id_attr': re.compile(r'<(\w+)\s+[^>]*id=["\']([^"\']+)["\']', re.IGNORECASE),
        
        # Comments that might contain references
        'html_comment': re.compile(r'<!--\s*(?:TODO|FIXME|NOTE|SEE|REF):\s*([^-]+)-->', re.IGNORECASE),
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
        Parse an HTML file for links and references.
        
        Args:
            file_path: Path to the file
            content: Optional file content (read from file if not provided)
            
        Returns:
            ParseResult with symbols (anchors, ids) and relationships (links, imports)
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
        
        # Extract title if present
        self._extract_title(content, file_path, symbols)
        
        # Extract ID attributes as potential anchor targets
        self._extract_ids(content, file_path, symbols)
        
        # Extract all link types
        self._extract_anchors(content, file_path, doc_name, relationships)
        self._extract_scripts(content, file_path, doc_name, relationships)
        self._extract_stylesheets(content, file_path, doc_name, relationships)
        self._extract_images(content, file_path, doc_name, relationships)
        self._extract_forms(content, file_path, doc_name, relationships)
        self._extract_media(content, file_path, doc_name, relationships)
        self._extract_embeds(content, file_path, doc_name, relationships)
        self._extract_background_images(content, file_path, doc_name, relationships)
        self._extract_data_urls(content, file_path, doc_name, relationships)
        
        return ParseResult(
            symbols=symbols,
            relationships=relationships,
            errors=errors
        )
    
    def _extract_title(self, content: str, file_path: str, symbols: List[Symbol]):
        """Extract document title."""
        match = self.PATTERNS['title'].search(content)
        if match:
            title = match.group(1).strip()
            line = self._get_line_number(content, match.start())
            symbols.append(self._make_symbol(
                name=title,
                symbol_type="document_title",
                line=line,
                file_path=file_path
            ))
    
    def _extract_ids(self, content: str, file_path: str, symbols: List[Symbol]):
        """Extract elements with IDs as potential anchor targets."""
        for match in self.PATTERNS['id_attr'].finditer(content):
            tag = match.group(1)
            id_value = match.group(2)
            line = self._get_line_number(content, match.start())
            
            symbols.append(self._make_symbol(
                name=f"#{id_value}",
                symbol_type="anchor_target",
                line=line,
                file_path=file_path,
                metadata={'tag': tag}
            ))
    
    def _extract_anchors(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract anchor links."""
        for match in self.PATTERNS['anchor'].finditer(content):
            href = match.group(1)
            line = self._get_line_number(content, match.start())
            
            # Skip empty or javascript: links
            if not href or href.startswith(('javascript:', '#', 'mailto:', 'tel:')):
                continue
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_url(href),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line
            ))
    
    def _extract_scripts(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract script imports."""
        for match in self.PATTERNS['script'].finditer(content):
            src = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_url(src),
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                line=line,
                confidence=0.95
            ))
    
    def _extract_stylesheets(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract stylesheet links."""
        for match in self.PATTERNS['stylesheet'].finditer(content):
            href = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_url(href),
                rel_type=RelationshipType.IMPORTS,
                file_path=file_path,
                line=line,
                confidence=0.95
            ))
    
    def _extract_images(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract image sources."""
        for match in self.PATTERNS['image'].finditer(content):
            src = match.group(1)
            line = self._get_line_number(content, match.start())
            
            # Skip data URIs
            if src.startswith('data:'):
                continue
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_url(src),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line,
                confidence=0.85
            ))
    
    def _extract_forms(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract form actions."""
        for match in self.PATTERNS['form_action'].finditer(content):
            action = match.group(1)
            line = self._get_line_number(content, match.start())
            
            if action and not action.startswith('#'):
                relationships.append(self._make_relationship(
                    source=doc_name,
                    target=self._normalize_url(action),
                    rel_type=RelationshipType.REFERENCES,
                    file_path=file_path,
                    line=line,
                    confidence=0.80
                ))
    
    def _extract_media(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract video/audio sources."""
        for match in self.PATTERNS['media'].finditer(content):
            src = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_url(src),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line,
                confidence=0.85
            ))
        
        # Also check iframe
        for match in self.PATTERNS['iframe'].finditer(content):
            src = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_url(src),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line,
                confidence=0.80
            ))
    
    def _extract_embeds(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract object/embed sources."""
        for match in self.PATTERNS['embed'].finditer(content):
            src = match.group(1)
            line = self._get_line_number(content, match.start())
            
            relationships.append(self._make_relationship(
                source=doc_name,
                target=self._normalize_url(src),
                rel_type=RelationshipType.REFERENCES,
                file_path=file_path,
                line=line,
                confidence=0.80
            ))
    
    def _extract_background_images(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract background images from inline styles."""
        for match in self.PATTERNS['bg_image'].finditer(content):
            url = match.group(1)
            line = self._get_line_number(content, match.start())
            
            if not url.startswith('data:'):
                relationships.append(self._make_relationship(
                    source=doc_name,
                    target=self._normalize_url(url),
                    rel_type=RelationshipType.REFERENCES,
                    file_path=file_path,
                    line=line,
                    confidence=0.75
                ))
    
    def _extract_data_urls(self, content: str, file_path: str, doc_name: str, relationships: List[Relationship]):
        """Extract URLs from data attributes."""
        for match in self.PATTERNS['data_url'].finditer(content):
            url = match.group(1)
            line = self._get_line_number(content, match.start())
            
            if not url.startswith('data:'):
                relationships.append(self._make_relationship(
                    source=doc_name,
                    target=self._normalize_url(url),
                    rel_type=RelationshipType.REFERENCES,
                    file_path=file_path,
                    line=line,
                    confidence=0.70
                ))
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistent reference."""
        url = url.strip()
        
        # Keep full URLs
        if url.startswith(('http://', 'https://', '//')):
            return url
        
        # Clean relative paths
        if url.startswith('./'):
            url = url[2:]
        
        # Remove query strings for local files
        if '?' in url and not url.startswith(('http://', 'https://')):
            url = url.split('?')[0]
        
        return url
