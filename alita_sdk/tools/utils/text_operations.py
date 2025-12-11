"""
Shared text operations utilities for file manipulation across toolkits.

Provides common functionality for:
- Parsing OLD/NEW marker-based edits
- Text file validation
- Line-based slicing and partial reads
- Content searching with context
"""
import re
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)

# Text file extensions that support editing
TEXT_EDITABLE_EXTENSIONS = {
    '.md', '.txt', '.csv', '.json', '.xml', '.html', 
    '.yaml', '.yml', '.ini', '.conf', '.log', '.sh',
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go',
    '.rb', '.php', '.c', '.cpp', '.h', '.hpp', '.cs',
    '.sql', '.r', '.m', '.swift', '.kt', '.rs', '.scala'
}


def parse_old_new_markers(file_query: str) -> List[Tuple[str, str]]:
    """
    Parse OLD/NEW marker-based edit instructions.
    
    Extracts pairs of old and new content from a file query using markers:
    - OLD <<<< ... >>>> OLD
    - NEW <<<< ... >>>> NEW
    
    Args:
        file_query: String containing marked old and new content sections
        
    Returns:
        List of tuples (old_content, new_content) for each edit pair
        
    Example:
        >>> query = '''
        ... OLD <<<<
        ... Hello World
        ... >>>> OLD
        ... NEW <<<<
        ... Hello Mars
        ... >>>> NEW
        ... '''
        >>> parse_old_new_markers(query)
        [('Hello World', 'Hello Mars')]
    """
    # Split the file content by lines
    code_lines = file_query.split("\n")

    # Initialize lists to hold the contents of OLD and NEW sections
    old_contents = []
    new_contents = []

    # Initialize variables to track whether the current line is within an OLD or NEW section
    in_old_section = False
    in_new_section = False

    # Temporary storage for the current section's content
    current_section_content = []

    # Iterate through each line in the file content
    for line in code_lines:
        # Check for OLD section start
        if "OLD <<<" in line:
            in_old_section = True
            current_section_content = []  # Reset current section content
            continue  # Skip the line with the marker

        # Check for OLD section end
        if ">>>> OLD" in line:
            in_old_section = False
            old_contents.append("\n".join(current_section_content).strip())  # Add the captured content
            current_section_content = []  # Reset current section content
            continue  # Skip the line with the marker

        # Check for NEW section start
        if "NEW <<<" in line:
            in_new_section = True
            current_section_content = []  # Reset current section content
            continue  # Skip the line with the marker

        # Check for NEW section end
        if ">>>> NEW" in line:
            in_new_section = False
            new_contents.append("\n".join(current_section_content).strip())  # Add the captured content
            current_section_content = []  # Reset current section content
            continue  # Skip the line with the marker

        # If currently in an OLD or NEW section, add the line to the current section content
        if in_old_section or in_new_section:
            current_section_content.append(line)

    # Pair the OLD and NEW contents
    paired_contents = list(zip(old_contents, new_contents))

    return paired_contents


def is_text_editable(filename: str) -> bool:
    """
    Check if a file is editable as text based on its extension.
    
    Args:
        filename: Name or path of the file to check
        
    Returns:
        True if file extension is in the text-editable whitelist
        
    Example:
        >>> is_text_editable("config.json")
        True
        >>> is_text_editable("image.png")
        False
    """
    from pathlib import Path
    ext = Path(filename).suffix.lower()
    return ext in TEXT_EDITABLE_EXTENSIONS


def apply_line_slice(
    content: str, 
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    head: Optional[int] = None,
    tail: Optional[int] = None
) -> str:
    """
    Apply line-based slicing to text content.
    
    Supports multiple modes:
    - offset + limit: Read from line `offset` for `limit` lines (1-indexed)
    - head: Read only first N lines
    - tail: Read only last N lines
    - No params: Return full content
    
    Args:
        content: Text content to slice
        offset: Starting line number (1-indexed, inclusive)
        limit: Number of lines to read from offset
        head: Return only first N lines
        tail: Return only last N lines
        
    Returns:
        Sliced content as string
        
    Example:
        >>> text = "line1\\nline2\\nline3\\nline4\\nline5"
        >>> apply_line_slice(text, offset=2, limit=2)
        'line2\\nline3'
        >>> apply_line_slice(text, head=2)
        'line1\\nline2'
        >>> apply_line_slice(text, tail=2)
        'line4\\nline5'
    """
    if not content:
        return content
        
    lines = content.splitlines(keepends=True)
    
    # Head mode: first N lines
    if head is not None:
        return ''.join(lines[:head])
    
    # Tail mode: last N lines
    if tail is not None:
        return ''.join(lines[-tail:] if tail > 0 else lines)
    
    # Offset + limit mode: slice from offset for limit lines
    if offset is not None:
        start_idx = max(0, offset - 1)  # Convert 1-indexed to 0-indexed
        if limit is not None:
            end_idx = start_idx + limit
            return ''.join(lines[start_idx:end_idx])
        else:
            return ''.join(lines[start_idx:])
    
    # No slicing parameters: return full content
    return content


def search_in_content(
    content: str,
    pattern: str,
    is_regex: bool = True,
    context_lines: int = 2
) -> List[Dict[str, any]]:
    """
    Search for pattern in content with context lines.
    
    Args:
        content: Text content to search
        pattern: Search pattern (regex if is_regex=True, else literal string)
        is_regex: Whether to treat pattern as regex (default True)
        context_lines: Number of lines before/after match to include (default 2)
        
    Returns:
        List of match dictionaries with keys:
            - line_number: 1-indexed line number of match
            - line_content: The matching line
            - match_text: The actual matched text
            - context_before: List of lines before match
            - context_after: List of lines after match
            
    Example:
        >>> text = "line1\\nHello World\\nline3"
        >>> matches = search_in_content(text, "Hello", is_regex=False)
        >>> matches[0]['line_number']
        2
        >>> matches[0]['match_text']
        'Hello'
    """
    if not content:
        return []
    
    lines = content.splitlines()
    matches = []
    
    # Compile regex pattern or escape for literal search
    if is_regex:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            return []
    else:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)
    
    # Search each line
    for line_idx, line in enumerate(lines):
        match = regex.search(line)
        if match:
            line_number = line_idx + 1  # Convert to 1-indexed
            
            # Get context lines
            context_start = max(0, line_idx - context_lines)
            context_end = min(len(lines), line_idx + context_lines + 1)
            
            context_before = lines[context_start:line_idx]
            context_after = lines[line_idx + 1:context_end]
            
            matches.append({
                'line_number': line_number,
                'line_content': line,
                'match_text': match.group(0),
                'context_before': context_before,
                'context_after': context_after,
            })
    
    return matches
