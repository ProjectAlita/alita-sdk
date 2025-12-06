"""
Pattern loader - universal patterns for text extraction.

IMPORTANT: Language-specific parsing has been moved to dedicated parsers.
For parsing code and documents, use the parsers module:

    from alita_sdk.community.inventory.parsers import (
        parse_file,
        PythonParser, JavaScriptParser, JavaParser,
        KotlinParser, CSharpParser, RustParser, SwiftParser, GoParser,
        MarkdownParser, HTMLParser, YAMLParser, ConfluenceParser, TextParser,
    )

This module provides:
- Universal patterns for extracting references from any text
- Backward compatibility functions for existing code
"""

import re
from pathlib import Path
from typing import List, Dict, Any

from .registry import (
    Pattern, PatternCategory, RelationType, PatternRegistry,
    get_registry, register_universal_pattern
)


def _create_universal_patterns() -> List[Pattern]:
    """
    Create patterns that apply to all file types.
    
    These patterns extract common textual references from any content.
    For structured content (code, markdown, HTML, etc.), use the 
    dedicated parsers in alita_sdk.community.inventory.parsers.
    """
    return [
        # "See X" / "See also X"
        Pattern(
            name="see_reference",
            regex=re.compile(r'[Ss]ee\s+(?:also\s+)?[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.REFERENCES,
            confidence=0.70,
            description="'See' text reference",
            examples=["See MyClass", "see also UserService"]
        ),
        # "Refer to X"
        Pattern(
            name="refer_to",
            regex=re.compile(r'[Rr]efer(?:s|ring)?\s+to\s+[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.REFERENCES,
            confidence=0.70,
            description="'Refer to' text reference",
            examples=["Refers to ConfigManager"]
        ),
        # "Depends on X"
        Pattern(
            name="doc_depends",
            regex=re.compile(r'[Dd]epends\s+on\s+[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.DEPENDS_ON,
            confidence=0.75,
            description="'Depends on' text reference"
        ),
        # "Uses X"
        Pattern(
            name="doc_uses",
            regex=re.compile(r'[Uu]ses\s+(?:the\s+)?[`\'"]?([A-Z]\w+)[`\'"]?(?:\s+(?:class|module|component|service))?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.USES,
            confidence=0.70,
            description="'Uses' text reference"
        ),
        # "Extends X"
        Pattern(
            name="doc_extends",
            regex=re.compile(r'[Ee]xtends\s+[`\'"]?([A-Z]\w+)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.EXTENDS,
            confidence=0.75,
            description="'Extends' text reference",
            examples=["Extends BaseController"]
        ),
        # "Implements X"
        Pattern(
            name="doc_implements",
            regex=re.compile(r'[Ii]mplements\s+[`\'"]?([A-Z]\w+)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.IMPLEMENTS,
            confidence=0.75,
            description="'Implements' text reference"
        ),
        # "Requires X"
        Pattern(
            name="doc_requires",
            regex=re.compile(r'[Rr]equires\s+(?:the\s+)?[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.DEPENDS_ON,
            confidence=0.75,
            description="'Requires' text reference",
            examples=["Requires AuthService"]
        ),
        # "Calls X" / "Invokes X"
        Pattern(
            name="doc_calls",
            regex=re.compile(r'(?:[Cc]alls?|[Ii]nvokes?)\s+(?:the\s+)?[`\'"]?([A-Z]\w+(?:\.\w+)*)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.CALLS,
            confidence=0.70,
            description="'Calls/Invokes' text reference"
        ),
        # "Defined in X"
        Pattern(
            name="doc_defined_in",
            regex=re.compile(r'(?:[Dd]efined|[Dd]eclared|[Ll]ocated)\s+in\s+[`\'"]?([A-Za-z][\w/.-]+(?:\.\w+)?)[`\'"]?', re.MULTILINE),
            category=PatternCategory.LINK,
            relation_type=RelationType.REFERENCES,
            confidence=0.75,
            description="'Defined in' location reference"
        ),
        # "Part of X"
        Pattern(
            name="doc_part_of",
            regex=re.compile(r'(?:[Pp]art\s+of|[Bb]elongs?\s+to)\s+(?:the\s+)?[`\'"]?([A-Z]\w+)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.CONTAINS,
            confidence=0.70,
            description="'Part of' membership reference"
        ),
        # "Based on X"
        Pattern(
            name="doc_based_on",
            regex=re.compile(r'[Bb]ased\s+on\s+(?:the\s+)?[`\'"]?([A-Z]\w+(?:\.\w+)?)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.EXTENDS,
            confidence=0.70,
            description="'Based on' reference"
        ),
        # "Deprecated in favor of X" / "Replaced by X"
        Pattern(
            name="doc_deprecated_for",
            regex=re.compile(r'(?:[Dd]eprecated\s+(?:in\s+favor\s+of|for)|[Rr]eplaced\s+by)\s+[`\'"]?([A-Z]\w+)[`\'"]?', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.REFERENCES,
            confidence=0.80,
            description="'Deprecated for/Replaced by' reference"
        ),
        # Jira ticket reference (universal)
        Pattern(
            name="jira_ticket",
            regex=re.compile(r'\b([A-Z][A-Z0-9]+-\d+)\b'),
            category=PatternCategory.LINK,
            relation_type=RelationType.REFERENCES,
            confidence=0.95,
            description="Jira ticket reference",
            examples=["PROJ-123", "ABC-1"]
        ),
        # GitHub issue reference (#123)
        Pattern(
            name="github_issue",
            regex=re.compile(r'(?:^|[\s(])#(\d{1,6})(?:$|[\s).,;:])', re.MULTILINE),
            category=PatternCategory.LINK,
            relation_type=RelationType.REFERENCES,
            confidence=0.75,
            description="GitHub issue reference",
            examples=["#123", "fixes #456"]
        ),
        # GitHub PR reference
        Pattern(
            name="github_pr",
            regex=re.compile(r'(?:PR|[Pp]ull\s+[Rr]equest)\s*#?(\d+)', re.MULTILINE),
            category=PatternCategory.LINK,
            relation_type=RelationType.REFERENCES,
            confidence=0.80,
            description="GitHub PR reference"
        ),
        # URL reference
        Pattern(
            name="url_reference",
            regex=re.compile(r'(https?://[^\s<>\[\]()]+)', re.MULTILINE),
            category=PatternCategory.LINK,
            relation_type=RelationType.REFERENCES,
            confidence=0.90,
            description="URL reference"
        ),
        # Email reference
        Pattern(
            name="email_reference",
            regex=re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
            category=PatternCategory.CITATION,
            relation_type=RelationType.MENTIONS,
            confidence=0.85,
            description="Email reference"
        ),
        # User mention (@user)
        Pattern(
            name="user_mention",
            regex=re.compile(r'(?:^|[\s(])@(\w[\w.-]+)', re.MULTILINE),
            category=PatternCategory.CITATION,
            relation_type=RelationType.MENTIONS,
            confidence=0.80,
            description="User mention"
        ),
    ]


# Cache for loaded patterns
_patterns_loaded = False


def load_all_patterns() -> PatternRegistry:
    """
    Load universal patterns into the registry.
    
    NOTE: Language-specific patterns have been moved to dedicated parsers.
    For parsing code/documents, use the parsers module instead.
    
    Returns:
        The populated pattern registry
    """
    global _patterns_loaded
    
    registry = get_registry()
    
    if not _patterns_loaded:
        for pattern in _create_universal_patterns():
            register_universal_pattern(pattern)
        _patterns_loaded = True
    
    return registry


def get_universal_patterns() -> List[Pattern]:
    """
    Get all universal patterns.
    
    Returns:
        List of universal patterns applicable to any text
    """
    return _create_universal_patterns()


def extract_references_from_text(
    text: str, 
    source_name: str = "text",
    include_mentions: bool = True
) -> List[Dict[str, Any]]:
    """
    Extract references from arbitrary text using universal patterns.
    
    For structured content (code, markdown, HTML, etc.), use the 
    dedicated parsers instead:
    
        from alita_sdk.community.inventory.parsers import parse_file
        result = parse_file("path/to/file.md")
    
    Args:
        text: Text content to analyze
        source_name: Name for the source document
        include_mentions: Whether to include user mentions
        
    Returns:
        List of reference dictionaries with keys: 
        pattern, target, line, confidence, relation_type, source
    """
    references = []
    seen = set()  # Deduplicate
    
    for pattern in _create_universal_patterns():
        # Skip mentions if not requested
        if not include_mentions and pattern.relation_type == RelationType.MENTIONS:
            continue
            
        for match in pattern.regex.finditer(text):
            idx = pattern.group_index if pattern.group_index else 1
            try:
                target = match.group(idx)
            except IndexError:
                target = match.group(1)
            
            # Deduplicate
            key = (pattern.name, target)
            if key in seen:
                continue
            seen.add(key)
            
            line = text[:match.start()].count('\n') + 1
            
            references.append({
                'pattern': pattern.name,
                'target': target,
                'line': line,
                'confidence': pattern.confidence,
                'relation_type': pattern.relation_type.value if pattern.relation_type else 'references',
                'source': source_name
            })
    
    return references


# Backward compatibility aliases
def get_patterns_for_file(file_path: str) -> List[Pattern]:
    """
    Get patterns for a file. Returns universal patterns.
    
    DEPRECATED: Use parsers module for file-specific parsing:
        from alita_sdk.community.inventory.parsers import parse_file
    """
    return get_universal_patterns()


def get_patterns_for_content_type(content_type: str) -> List[Pattern]:
    """
    Get patterns for a content type. Returns universal patterns.
    
    DEPRECATED: Use parsers module for content-specific parsing:
        from alita_sdk.community.inventory.parsers import MarkdownParser, ConfluenceParser
    """
    return get_universal_patterns()


def extract_references_from_content(
    content: str, 
    content_type: str = 'text',
    include_mentions: bool = True
) -> List[Dict[str, Any]]:
    """
    Extract references from content.
    
    DEPRECATED: Use parsers module for structured content:
        from alita_sdk.community.inventory.parsers import parse_file, MarkdownParser
    
    For simple text extraction, use extract_references_from_text() instead.
    """
    return extract_references_from_text(content, content_type, include_mentions)


__all__ = [
    'load_all_patterns',
    'get_universal_patterns',
    'extract_references_from_text',
    'extract_references_from_content',
    'get_patterns_for_file',
    'get_patterns_for_content_type',
    '_create_universal_patterns',
]
