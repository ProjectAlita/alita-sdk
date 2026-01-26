#!/usr/bin/env python3
"""
Shared pattern matching utilities for test pipeline scripts.

Provides consistent pattern matching logic across all scripts:
- seed_pipelines.py
- run_suite.py
- run_pipeline.py
- cleanup.py
- delete_pipelines.py

This ensures that patterns work consistently whether matching against:
- Test case filenames (in seed_pipelines.py)
- Pipeline names from API (in run_suite.py, cleanup.py, etc.)
"""

import fnmatch
import re
from pathlib import Path


def normalize_for_matching(s: str) -> str:
    """
    Normalize string for flexible matching.
    
    Makes matching underscore/space/hyphen agnostic and case-insensitive.
    This allows patterns like 'case_03', 'case-03', or 'case 03' to match
    'test_case_03_issue_workflow.yaml' or 'GH03 - Issue Workflow'.
    
    Args:
        s: String to normalize
        
    Returns:
        Normalized string (lowercase, spaces instead of underscores/hyphens)
        
    Examples:
        >>> normalize_for_matching("test_case_03")
        'test case 03'
        >>> normalize_for_matching("GH03 - Issue Workflow")
        'gh03   issue workflow'
        >>> normalize_for_matching("update_file")
        'update file'
    """
    return s.lower().replace("_", " ").replace("-", " ")


def matches_pattern(text: str, pattern: str, use_wildcards: bool = False) -> bool:
    """
    Check if text matches a pattern with consistent normalization.
    
    Args:
        text: Text to match against (filename, pipeline name, etc.)
        pattern: Pattern to match (can include wildcards if use_wildcards=True)
        use_wildcards: If True, use shell-style wildcards (*, ?)
        
    Returns:
        True if pattern matches, False otherwise
        
    Examples:
        >>> matches_pattern("test_case_03_issue_workflow.yaml", "case_03")
        True
        >>> matches_pattern("GH03 - Issue Workflow", "case_03")
        False
        >>> matches_pattern("GH03 - Issue Workflow", "GH03")
        True
        >>> matches_pattern("test_update_file.yaml", "update*", use_wildcards=True)
        True
    """
    if use_wildcards:
        # Use fnmatch for wildcard patterns (case-insensitive)
        return fnmatch.fnmatch(text.lower(), pattern.lower())
    
    # Normalized substring matching
    normalized_text = normalize_for_matching(text)
    normalized_pattern = normalize_for_matching(pattern)
    return normalized_pattern in normalized_text


def matches_any_pattern(text: str, patterns: list[str], use_wildcards: bool = False) -> bool:
    """
    Check if text matches any of the provided patterns (OR logic).
    
    Args:
        text: Text to match against
        patterns: List of patterns to try
        use_wildcards: If True, use shell-style wildcards (*, ?)
        
    Returns:
        True if any pattern matches, False otherwise
        
    Examples:
        >>> matches_any_pattern("test_case_03.yaml", ["case_03", "case_04"])
        True
        >>> matches_any_pattern("GH03 - Issue Workflow", ["case_03", "GH03"])
        True
        >>> matches_any_pattern("test_update.yaml", ["delete", "create"])
        False
    """
    return any(matches_pattern(text, pattern, use_wildcards) for pattern in patterns)


def filter_by_patterns(
    items: list,
    patterns: list[str],
    get_text: callable,
    use_wildcards: bool = False,
) -> list:
    """
    Filter a list of items by patterns.
    
    Args:
        items: List of items to filter
        patterns: List of patterns to match
        get_text: Function to extract text from each item (e.g., lambda x: x.name)
        use_wildcards: If True, use shell-style wildcards (*, ?)
        
    Returns:
        Filtered list of items that match any pattern
        
    Examples:
        >>> files = [Path("test_case_03.yaml"), Path("test_case_04.yaml")]
        >>> filter_by_patterns(files, ["case_03"], lambda f: f.name)
        [Path("test_case_03.yaml")]
        
        >>> pipelines = [{"name": "GH03 - Issue"}, {"name": "GH04 - Branch"}]
        >>> filter_by_patterns(pipelines, ["GH03"], lambda p: p["name"])
        [{"name": "GH03 - Issue"}]
    """
    if not patterns:
        return items
    
    filtered = []
    for item in items:
        text = get_text(item)
        if matches_any_pattern(text, patterns, use_wildcards):
            filtered.append(item)
    
    return filtered


def match_pipeline_name_to_filename(pipeline_name: str, filename: str) -> bool:
    """
    Check if a pipeline name corresponds to a test case filename.
    
    This is used to match seeded pipelines back to their source files.
    For example:
    - Pipeline "GH03 - Issue Workflow" -> filename "test_case_03_issue_workflow.yaml"
    - Pipeline "GH14 - Update File" -> filename "test_case_14_update_file.yaml"
    
    Args:
        pipeline_name: Name of the pipeline (e.g., "GH03 - Issue Workflow")
        filename: Test case filename (e.g., "test_case_03_issue_workflow.yaml")
        
    Returns:
        True if they correspond to the same test case
        
    Examples:
        >>> match_pipeline_name_to_filename("GH03 - Issue Workflow", 
        ...     "test_case_03_issue_workflow.yaml")
        True
        >>> match_pipeline_name_to_filename("GH03 - Issue Workflow",
        ...     "test_case_04_branch.yaml")
        False
    """
    # Normalize both strings
    norm_name = normalize_for_matching(pipeline_name)
    norm_file = normalize_for_matching(filename)
    
    # Extract key parts from pipeline name (e.g., "GH03" and "Issue Workflow")
    # and check if both appear in the filename
    name_parts = norm_name.split()
    
    # Check if all significant parts of the pipeline name appear in the filename
    # (ignore very short parts like articles)
    significant_parts = [p for p in name_parts if len(p) > 1]
    
    matches = sum(1 for part in significant_parts if part in norm_file)
    
    # If at least 2 significant parts match (or all parts if less than 2),
    # consider it a match
    threshold = min(2, len(significant_parts))
    return matches >= threshold


def extract_test_id_from_filename(filename: str) -> str | None:
    """
    Extract test ID from a test case filename.
    
    Args:
        filename: Test case filename (e.g., "test_case_03_issue_workflow.yaml")
        
    Returns:
        Test ID string (e.g., "03") or None if not found
        
    Examples:
        >>> extract_test_id_from_filename("test_case_03_issue_workflow.yaml")
        '03'
        >>> extract_test_id_from_filename("test_case_14_branch.yaml")
        '14'
        >>> extract_test_id_from_filename("pipeline.yaml")
        None
    """
    
    match = re.search(r'test_case_(\d+)', filename.lower())
    return match.group(1) if match else None


def extract_test_id_from_pipeline_name(pipeline_name: str) -> str | None:
    """
    Extract test ID from a pipeline name.
    
    Args:
        pipeline_name: Pipeline name (e.g., "GH03 - Issue Workflow")
        
    Returns:
        Test ID string (e.g., "03") or None if not found
        
    Examples:
        >>> extract_test_id_from_pipeline_name("GH03 - Issue Workflow")
        '03'
        >>> extract_test_id_from_pipeline_name("GH14 - Update File")
        '14'
        >>> extract_test_id_from_pipeline_name("Some Pipeline")
        None
    """

    # Look for pattern like "GH03", "TC03", etc.
    match = re.search(r'[A-Z]{2,}(\d+)', pipeline_name)
    return match.group(1) if match else None
