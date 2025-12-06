"""
Universal text parser for extracting references from any text content.

Extracts common textual references like "See X", "Depends on Y", URLs, tickets, etc.
This parser can be used as a fallback for any text that doesn't match a specific parser.
"""

import re
from typing import List, Optional, Set
from pathlib import Path

from .base import (
    BaseParser, Symbol, Relationship, ParseResult,
    RelationshipType, Range
)


class TextParser(BaseParser):
    """
    Universal parser for free-form text content.
    
    Extracts:
    - "See X", "Refer to X" references
    - "Depends on X", "Uses X", "Requires X"
    - "Extends X", "Implements X"
    - Jira tickets, GitHub issues, PRs
    - URLs, emails
    - Version references
    """
    
    language = "text"
    file_extensions = ['.txt', '.text', '.log']  # Fallback for plain text
    
    def __init__(self):
        """Initialize the text parser."""
        super().__init__(language=self.language)
    
    def _get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {'.txt', '.text', '.log'}
    
    # Patterns for textual references
    PATTERNS = {
        # "See X" / "See also X"
        'see_reference': re.compile(
            r'[Ss]ee\s+(?:also\s+)?[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Refer to X"
        'refer_to': re.compile(
            r'[Rr]efer(?:s|ring)?\s+to\s+[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Depends on X"
        'depends_on': re.compile(
            r'[Dd]epends\s+on\s+[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Uses X"
        'uses': re.compile(
            r'[Uu]ses\s+(?:the\s+)?[`\'"]?([A-Z]\w+)[`\'"]?(?:\s+(?:class|module|component|service))?',
            re.MULTILINE
        ),
        
        # "Requires X"
        'requires': re.compile(
            r'[Rr]equires\s+(?:the\s+)?[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Extends X"
        'extends': re.compile(
            r'[Ee]xtends\s+[`\'"]?([A-Z]\w+)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Implements X"
        'implements': re.compile(
            r'[Ii]mplements\s+[`\'"]?([A-Z]\w+)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Calls X" / "Invokes X"
        'calls': re.compile(
            r'(?:[Cc]alls?|[Ii]nvokes?)\s+(?:the\s+)?[`\'"]?([A-Z]\w+(?:\.\w+)*)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Returns X"
        'returns': re.compile(
            r'[Rr]eturns?\s+(?:a\s+|an\s+)?[`\'"]?([A-Z]\w+(?:<[^>]+>)?)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Defined in X"
        'defined_in': re.compile(
            r'(?:[Dd]efined|[Dd]eclared|[Ll]ocated)\s+in\s+[`\'"]?([A-Za-z][\w/.-]+(?:\.\w+)?)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Imported from X"
        'imported_from': re.compile(
            r'[Ii]mported?\s+from\s+[`\'"]?([A-Za-z][\w/.-]+)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Part of X"
        'part_of': re.compile(
            r'(?:[Pp]art\s+of|[Bb]elongs?\s+to)\s+(?:the\s+)?[`\'"]?([A-Z]\w+)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Wraps X"
        'wraps': re.compile(
            r'(?:[Ww]raps?|[Ww]rapper\s+for)\s+(?:the\s+)?[`\'"]?([A-Z]\w+)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Based on X"
        'based_on': re.compile(
            r'[Bb]ased\s+on\s+(?:the\s+)?[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?',
            re.MULTILINE
        ),
        
        # "Deprecated in favor of X"
        'deprecated_for': re.compile(
            r'(?:[Dd]eprecated\s+(?:in\s+favor\s+of|for)|[Rr]eplaced\s+by)\s+[`\'"]?([A-Z]\w+)[`\'"]?',
            re.MULTILINE
        ),
        
        # Jira ticket reference
        'jira_ticket': re.compile(r'\b([A-Z][A-Z0-9]+-\d+)\b'),
        
        # GitHub issue reference (#123)
        'github_issue': re.compile(r'(?:^|[\s(])#(\d{1,6})(?:$|[\s).,;:])', re.MULTILINE),
        
        # GitHub PR reference
        'github_pr': re.compile(r'(?:PR|[Pp]ull\s+[Rr]equest)\s*#?(\d+)', re.MULTILINE),
        
        # Commit SHA reference
        'commit_sha': re.compile(
            r'(?:commit|sha|rev(?:ision)?)[:\s]+([0-9a-f]{7,40})\b',
            re.IGNORECASE
        ),
        
        # URL reference
        'url': re.compile(r'(https?://[^\s<>\[\]()]+)', re.MULTILINE),
        
        # Email reference
        'email': re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
        
        # Version reference
        'version': re.compile(r'\b[Vv]?(\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?)\b'),
    }
    
    # Map pattern names to relationship types
    REL_TYPE_MAP = {
        'see_reference': RelationshipType.REFERENCES,
        'refer_to': RelationshipType.REFERENCES,
        'depends_on': RelationshipType.USES,
        'uses': RelationshipType.USES,
        'requires': RelationshipType.USES,
        'extends': RelationshipType.INHERITANCE,
        'implements': RelationshipType.IMPLEMENTATION,
        'calls': RelationshipType.CALLS,
        'returns': RelationshipType.REFERENCES,
        'defined_in': RelationshipType.REFERENCES,
        'imported_from': RelationshipType.IMPORTS,
        'part_of': RelationshipType.CONTAINS,
        'wraps': RelationshipType.USES,
        'based_on': RelationshipType.INHERITANCE,
        'deprecated_for': RelationshipType.REFERENCES,
        'jira_ticket': RelationshipType.REFERENCES,
        'github_issue': RelationshipType.REFERENCES,
        'github_pr': RelationshipType.REFERENCES,
        'commit_sha': RelationshipType.REFERENCES,
        'url': RelationshipType.REFERENCES,
        'email': RelationshipType.REFERENCES,
        'version': RelationshipType.REFERENCES,
    }
    
    # Confidence scores for each pattern type
    CONFIDENCE_MAP = {
        'see_reference': 0.70,
        'refer_to': 0.70,
        'depends_on': 0.80,
        'uses': 0.75,
        'requires': 0.80,
        'extends': 0.85,
        'implements': 0.85,
        'calls': 0.75,
        'returns': 0.65,
        'defined_in': 0.80,
        'imported_from': 0.85,
        'part_of': 0.70,
        'wraps': 0.75,
        'based_on': 0.75,
        'deprecated_for': 0.85,
        'jira_ticket': 0.95,
        'github_issue': 0.80,
        'github_pr': 0.85,
        'commit_sha': 0.90,
        'url': 0.90,
        'email': 0.85,
        'version': 0.60,
    }
    
    def _make_range(self, start_line: int, end_line: int = None) -> Range:
        """Create a Range object."""
        return Range(
            start_line=start_line,
            end_line=end_line or start_line,
            start_col=0,
            end_col=0
        )
    
    def _make_relationship(
        self,
        source: str,
        target: str,
        rel_type: RelationshipType,
        file_path: str,
        line: int,
        confidence: float = 0.80
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
        Parse text content for references.
        
        Args:
            file_path: Path or identifier for the content
            content: Optional content (read from file if not provided)
            
        Returns:
            ParseResult with relationships
        """
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                return ParseResult(symbols=[], relationships=[], errors=[f"Could not read {file_path}"])
        
        relationships: List[Relationship] = []
        errors: List[str] = []
        
        # Source name
        source_name = Path(file_path).stem if '/' in file_path or '\\' in file_path else file_path
        
        # Track seen references to avoid duplicates
        seen: set = set()
        
        # Process each pattern
        for pattern_name, pattern in self.PATTERNS.items():
            rel_type = self.REL_TYPE_MAP.get(pattern_name, RelationshipType.REFERENCES)
            confidence = self.CONFIDENCE_MAP.get(pattern_name, 0.70)
            
            for match in pattern.finditer(content):
                target = match.group(1)
                
                # Create unique key for deduplication
                key = (pattern_name, target)
                if key in seen:
                    continue
                seen.add(key)
                
                line = self._get_line_number(content, match.start())
                
                # Format special references
                if pattern_name == 'github_issue':
                    target = f"#{target}"
                elif pattern_name == 'github_pr':
                    target = f"PR#{target}"
                elif pattern_name == 'commit_sha':
                    target = f"commit:{target[:7]}"  # Shorten SHA
                elif pattern_name == 'version':
                    target = f"v{target}"
                
                relationships.append(self._make_relationship(
                    source=source_name,
                    target=target,
                    rel_type=rel_type,
                    file_path=file_path,
                    line=line,
                    confidence=confidence
                ))
        
        return ParseResult(
            symbols=[],
            relationships=relationships,
            errors=errors
        )
    
    def parse_content(self, content: str, source_name: str = "text") -> ParseResult:
        """
        Parse text content directly without a file path.
        
        Args:
            content: The text content to parse
            source_name: Name to use as the source in relationships
            
        Returns:
            ParseResult with relationships
        """
        return self.parse_file(source_name, content)
