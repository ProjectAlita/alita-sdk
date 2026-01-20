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
    
    Extracts all pairs of old and new content from a file query using markers:
    - OLD <<<< ... >>>> OLD
    - NEW <<<< ... >>>> NEW
    
    Markers must be on their own dedicated line (with optional surrounding whitespace).
    This prevents literal marker strings within file content from being interpreted
    as actual delimiters.

    Args:
        file_query: String containing marked old and new content sections
        
    Returns:
        List of tuples (old_content, new_content) for all valid edit pairs found.
        Returns empty list if no valid OLD/NEW pairs are found.

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

        Multiple pairs are supported:
        >>> query = '''
        ... OLD <<<<
        ... first old
        ... >>>> OLD
        ... NEW <<<<
        ... first new
        ... >>>> NEW
        ... OLD <<<<
        ... second old
        ... >>>> OLD
        ... NEW <<<<
        ... second new
        ... >>>> NEW
        ... '''
        >>> parse_old_new_markers(query)
        [('first old', 'first new'), ('second old', 'second new')]
    """
    # Compile regex patterns for strict line-only marker matching
    # Markers must be alone on their line (with optional whitespace)
    old_start_pattern = re.compile(r'^\s*OLD\s*<<<<\s*$')
    old_end_pattern = re.compile(r'^\s*>>>>\s*OLD\s*$')
    new_start_pattern = re.compile(r'^\s*NEW\s*<<<<\s*$')
    new_end_pattern = re.compile(r'^\s*>>>>\s*NEW\s*$')

    # Split the file content by lines
    code_lines = file_query.split("\n")

    # Initialize variables to track section state
    in_old_section = False
    in_new_section = False
    old_content = None
    new_content = None

    # Temporary storage for the current section's content
    current_section_content = []

    # List to collect all found edit pairs
    edit_pairs = []

    # Iterate through each line in the file content
    for line in code_lines:
        # Check for OLD section start (strict line match)
        if old_start_pattern.match(line):
            in_old_section = True
            current_section_content = []  # Reset current section content
            continue  # Skip the line with the marker

        # Check for OLD section end (strict line match)
        if old_end_pattern.match(line):
            in_old_section = False
            old_content = "\n".join(current_section_content).strip()
            current_section_content = []  # Reset current section content
            continue  # Skip the line with the marker

        # Check for NEW section start (strict line match)
        if new_start_pattern.match(line):
            in_new_section = True
            current_section_content = []  # Reset current section content
            continue  # Skip the line with the marker

        # Check for NEW section end (strict line match)
        if new_end_pattern.match(line):
            in_new_section = False
            new_content = "\n".join(current_section_content).strip()
            # Add the completed pair to the list
            if old_content is not None and new_content is not None:
                edit_pairs.append((old_content, new_content))
                # Reset for next potential pair
                old_content = None
                new_content = None
            current_section_content = []  # Reset current section content
            continue  # Skip the line with the marker

        # If currently in an OLD or NEW section, add the line to the current section content
        if in_old_section or in_new_section:
            current_section_content.append(line)

    return edit_pairs


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


def _normalize_for_match(text: str) -> str:
    """Normalize text for tolerant OLD/NEW matching.

    - Split into lines
    - Replace common Unicode spaces with regular spaces
    - Strip leading/trailing whitespace per line
    - Collapse internal whitespace runs to a single space
    - Join with '\n'
    """
    lines = text.splitlines()
    norm_lines = []
    for line in lines:
        # Normalize common Unicode spaces to regular space
        line = line.replace("\u00A0", " ").replace("\u2009", " ")
        # Strip outer whitespace
        line = line.strip()
        # Collapse internal whitespace
        line = re.sub(r"\s+", " ", line)
        norm_lines.append(line)
    return "\n".join(norm_lines)


def try_apply_edit(
    content: str,
    old_text: str,
    new_text: str,
    file_path: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Apply a single OLD/NEW edit with a tolerant fallback.

    This helper is used by edit_file to apply one (old_text, new_text) pair:
    
    1. First tries exact substring replacement (old_text in content).
    2. If that fails, performs a tolerant, line-based match:
       - Builds a logical OLD sequence without empty/whitespace-only lines
       - Scans content while skipping empty/whitespace-only lines
       - Compares using `_normalize_for_match` so minor spacing differences
         don't break the match
       - If exactly one such region is found, replaces that region with new_text
       - If zero or multiple regions are found, no change is applied
    
    Args:
        content: Current file content
        old_text: OLD block extracted from markers
        new_text: NEW block extracted from markers
        file_path: Optional path for logging context
    
    Returns:
        (updated_content, warning_message)
        - updated_content: resulting content (may be unchanged)
        - warning_message: human-readable warning if no edit was applied
          or if the operation was ambiguous; None if an edit was
          successfully and unambiguously applied.
    """
    # Stage 1: exact match
    if old_text:
        occurrences = content.count(old_text)
        if occurrences == 1:
            return content.replace(old_text, new_text, 1), None
        if occurrences > 1:
            msg = (
                "Exact OLD block appears %d times in %s; no replacement applied to avoid ambiguity. "
                "OLD value: %r" % (
                    occurrences,
                    file_path or "<unknown>",
                    old_text,
                )
            )
            logger.warning(msg)
            return content, msg

    # Stage 2: tolerant match
    if not old_text or not old_text.strip() or not content:
        msg = None
        if not old_text or not old_text.strip():
            msg = (
                "OLD block is empty or whitespace-only; no replacement applied. "
                "OLD value: %r" % (old_text,)
            )
        elif not content:
            msg = "Content is empty; no replacement applied."
        if msg:
            logger.warning(msg)
        return content, msg

    # Logical OLD: drop empty/whitespace-only lines
    old_lines_raw = old_text.splitlines()
    old_lines = [l for l in old_lines_raw if l.strip()]
    if not old_lines:
        msg = (
            "OLD block contains only empty/whitespace lines; no replacement applied. "
            "OLD value: %r" % (old_text,)
        )
        logger.warning(msg)
        return content, msg

    # Precompute normalized OLD (joined by '\n')
    norm_old = _normalize_for_match("\n".join(old_lines))

    content_lines = content.splitlines(keepends=True)
    total = len(content_lines)
    candidates: list[tuple[int, int, str]] = []  # (start_idx, end_idx, block)

    # Scan content for regions whose non-empty, normalized lines match norm_old
    for start in range(total):
        idx = start
        collected_non_empty: list[str] = []
        window_lines: list[str] = []

        while idx < total and len(collected_non_empty) < len(old_lines):
            line = content_lines[idx]
            window_lines.append(line)
            if line.strip():
                collected_non_empty.append(line)
            idx += 1

        if len(collected_non_empty) < len(old_lines):
            # Not enough non-empty lines from this start; no more windows possible
            break

        # Compare normalized non-empty content lines to normalized OLD
        candidate_norm = _normalize_for_match("".join(collected_non_empty))
        if candidate_norm == norm_old:
            block = "".join(window_lines)
            candidates.append((start, idx, block))

    if not candidates:
        msg = (
            "Normalized OLD block not found in %s. OLD value: %r"
            % (file_path or "<unknown>", old_text)
        )
        logger.warning(msg)
        return content, msg

    if len(candidates) > 1:
        msg = (
            "Multiple candidate regions for OLD block in %s; "
            "no change applied to avoid ambiguity. OLD value: %r"
            % (file_path or "<unknown>", old_text)
        )
        logger.warning(msg)
        return content, msg

    start_idx, end_idx, candidate_block = candidates[0]
    updated = content.replace(candidate_block, new_text, 1)

    logger.info(
        "Applied tolerant OLD/NEW replacement in %s around lines %d-%d",
        file_path or "<unknown>",
        start_idx + 1,
        start_idx + len(old_lines),
    )

    return updated, None
