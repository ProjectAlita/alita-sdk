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
    """Extract pairs of old/new content lines from a file query.

    Final behavior:
    1. Find each pair of ``OLD <<< ... >>> OLD`` and the following
       ``NEW <<< ... >>> NEW`` blocks.
    2. For each such pair, split the inner OLD/NEW block content by
       **non-escaped** newlines (actual ``"\n"`` characters), excluding
       empty lines after splitting.
    3. If the number of OLD items is greater than the number of NEW items,
       pad the NEW side with empty strings (""). If the number of NEW items
       is greater than the number of OLD items, join the remaining NEW items
       and append them to the last OLD item as a single extra pair.

    Args:
        file_query: The full text containing OLD/NEW markers.

    Returns:
        list[tuple[str, str]]: A list of (old_item, new_item) pairs.
    """
    # Pattern to capture the content between OLD/NEW markers, including
    # newlines. We will then split that content by raw newlines while keeping
    # escaped newlines ("\\n") intact within a single item.
    block_pattern = re.compile(
        r"OLD <<<<\s*(.*?)\s*>>>> OLD"  # OLD block
        r"\s*"                        # optional space/newlines between OLD/NEW
        r"NEW <<<<\s*(.*?)\s*>>>> NEW",  # NEW block
        re.DOTALL,
    )

    pairs: list[tuple[str, str]] = []

    def _split_preserving_escaped_newlines(block: str) -> list[str]:
        """Split block into logical lines on non-escaped newlines.

        Escaped newlines (the two-character sequence "\\n") are preserved
        inside a single item. Empty/whitespace-only lines are excluded.
        """
        # Split on real newline characters first.
        raw_lines = block.split("\n")
        items: list[str] = []
        current: list[str] = []

        for segment in raw_lines:
            if segment.endswith("\\"):
                # Line ends with a backslash, so treat this and the next
                # physical line as a single logical line.
                current.append(segment.rstrip("\n"))
                continue

            if current:
                current.append(segment)
                logical_line = "\n".join(current)
                current = []
            else:
                logical_line = segment

            # Skip empty/whitespace-only lines.
            if logical_line.strip():
                items.append(logical_line)

        # If something remains in current, flush it as one item.
        if current:
            logical_line = "\n".join(current)
            if logical_line.strip():
                items.append(logical_line)

        return items

    for old_block, new_block in block_pattern.findall(file_query):
        old_lines = _split_preserving_escaped_newlines(old_block)
        new_lines = _split_preserving_escaped_newlines(new_block)

        if not old_lines and not new_lines:
            continue

        # If there are more OLD lines than NEW lines, pad NEW with empty strings.
        if len(old_lines) > len(new_lines):
            new_lines.extend([""] * (len(old_lines) - len(new_lines)))

        # If there are more NEW lines than OLD lines, join the remaining NEW
        # items and attach them to the last OLD as a single extra pair.
        if len(new_lines) > len(old_lines) and old_lines:
            base_count = len(old_lines)
            # First pair old[i] with new[i] for i in range(base_count - 1).
            for i in range(base_count - 1):
                pairs.append((old_lines[i], new_lines[i]))

            # Join remaining NEW lines and attach to last OLD line.
            remaining_new = "\n".join(new_lines[base_count - 1 :])
            pairs.append((old_lines[-1], remaining_new))
            continue

        # Equal lengths or NEW <= OLD after padding: simple zip.
        for o, n in zip(old_lines, new_lines):
            pairs.append((o, n))

    return pairs


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
