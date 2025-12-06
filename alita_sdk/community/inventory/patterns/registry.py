"""
Pattern registry and data structures for cross-file reference detection.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Pattern as RePattern, Set, Any, Callable


class PatternCategory(Enum):
    """Categories of cross-file reference patterns."""
    IMPORT = "import"           # Code imports/includes
    LINK = "link"               # Documentation links
    CITATION = "citation"       # Text references
    INHERITANCE = "inheritance" # Class/type inheritance
    ANNOTATION = "annotation"   # Decorators, annotations
    TYPE_REF = "type_ref"       # Type references/annotations


class RelationType(Enum):
    """Types of relationships that patterns can detect."""
    IMPORTS = "IMPORTS"
    REFERENCES = "REFERENCES"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    MENTIONS = "MENTIONS"
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    INSTANTIATES = "INSTANTIATES"


@dataclass
class Pattern:
    """
    A single pattern for detecting cross-file references.
    
    Attributes:
        name: Human-readable pattern name
        regex: Compiled regex pattern
        category: Pattern category (import, link, etc.)
        relation_type: Type of relationship this pattern detects
        confidence: Base confidence score (0.0-1.0)
        group_index: Which regex group contains the reference (default: 1)
        description: Optional description of what this pattern matches
        examples: Example strings this pattern should match
        transform: Optional function to transform the matched value
    """
    name: str
    regex: RePattern
    category: PatternCategory
    relation_type: RelationType
    confidence: float = 0.9
    group_index: int = 1
    description: str = ""
    examples: List[str] = field(default_factory=list)
    transform: Optional[Callable[[str], str]] = None
    
    def match(self, content: str) -> List[str]:
        """
        Find all matches in content.
        
        Returns:
            List of matched references (already transformed if transform is set)
        """
        matches = self.regex.findall(content)
        results = []
        
        for match in matches:
            # Handle tuple results from multiple groups
            if isinstance(match, tuple):
                # Use the specified group index (0-based for tuple)
                idx = self.group_index - 1 if self.group_index > 0 else 0
                value = match[idx] if idx < len(match) else match[0]
            else:
                value = match
            
            if value:
                # Apply transform if specified
                if self.transform:
                    value = self.transform(value)
                results.append(value)
        
        return results


@dataclass 
class LanguagePatterns:
    """
    Collection of patterns for a specific language or document type.
    
    Attributes:
        language: Language identifier (e.g., 'python', 'javascript', 'markdown')
        extensions: File extensions this applies to (e.g., ['.py', '.pyw'])
        patterns: List of patterns for this language
        description: Description of the language/type
    """
    language: str
    extensions: List[str]
    patterns: List[Pattern]
    description: str = ""
    
    # Optional: mime types for non-file content
    mime_types: List[str] = field(default_factory=list)


class PatternRegistry:
    """
    Registry for managing language patterns.
    
    Supports:
    - Registering patterns by language
    - Looking up patterns by file extension
    - Getting all patterns for a category
    - Adding custom patterns at runtime
    """
    
    def __init__(self):
        self._by_language: Dict[str, LanguagePatterns] = {}
        self._by_extension: Dict[str, str] = {}  # extension -> language
        self._universal_patterns: List[Pattern] = []  # Apply to all files
    
    def register(self, lang_patterns: LanguagePatterns) -> None:
        """Register patterns for a language."""
        self._by_language[lang_patterns.language] = lang_patterns
        
        # Index by extension
        for ext in lang_patterns.extensions:
            ext_lower = ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            self._by_extension[ext_lower] = lang_patterns.language
    
    def register_universal(self, pattern: Pattern) -> None:
        """Register a pattern that applies to all files."""
        self._universal_patterns.append(pattern)
    
    def get_patterns_for_extension(self, extension: str) -> List[Pattern]:
        """Get all patterns for a file extension."""
        ext_lower = extension.lower() if extension.startswith('.') else f'.{extension.lower()}'
        
        patterns = list(self._universal_patterns)
        
        language = self._by_extension.get(ext_lower)
        if language and language in self._by_language:
            patterns.extend(self._by_language[language].patterns)
        
        return patterns
    
    def get_patterns_for_language(self, language: str) -> List[Pattern]:
        """Get all patterns for a specific language."""
        patterns = list(self._universal_patterns)
        
        if language in self._by_language:
            patterns.extend(self._by_language[language].patterns)
        
        return patterns
    
    def get_patterns_by_category(self, category: PatternCategory) -> List[Pattern]:
        """Get all patterns of a specific category across all languages."""
        patterns = [p for p in self._universal_patterns if p.category == category]
        
        for lang_patterns in self._by_language.values():
            patterns.extend([p for p in lang_patterns.patterns if p.category == category])
        
        return patterns
    
    def get_all_extensions(self) -> Set[str]:
        """Get all registered file extensions."""
        return set(self._by_extension.keys())
    
    def get_all_languages(self) -> List[str]:
        """Get all registered languages."""
        return list(self._by_language.keys())
    
    def get_language_for_extension(self, extension: str) -> Optional[str]:
        """Get the language for a file extension."""
        ext_lower = extension.lower() if extension.startswith('.') else f'.{extension.lower()}'
        return self._by_extension.get(ext_lower)


# Global registry instance
_registry = PatternRegistry()


def get_registry() -> PatternRegistry:
    """Get the global pattern registry."""
    return _registry


def register_patterns(lang_patterns: LanguagePatterns) -> None:
    """Register patterns in the global registry."""
    _registry.register(lang_patterns)


def register_universal_pattern(pattern: Pattern) -> None:
    """Register a universal pattern in the global registry."""
    _registry.register_universal(pattern)
