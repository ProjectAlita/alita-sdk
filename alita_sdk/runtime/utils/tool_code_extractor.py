"""
Tool Code Extractor Module

Extracts tool source code and dependencies for LLM error analysis.
Uses AST parsing to locate and extract relevant code sections with LRU caching.

Example:
    from alita_sdk.runtime.middleware.tool_code_extractor import extract_tool_code

    tool_code = extract_tool_code('github_create_issue', 'github')
    if tool_code:
        print(tool_code)
"""

import ast
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# LRU cache size for tool code extraction
CACHE_SIZE = 100


@lru_cache(maxsize=CACHE_SIZE)
def extract_tool_code(tool_name: str, toolkit_type: Optional[str] = None) -> Optional[str]:
    """
    Extract tool source code and dependencies with LRU caching.

    Args:
        tool_name: Name of the tool (e.g., 'github_create_issue')
        toolkit_type: Type of toolkit (e.g., 'github')

    Returns:
        Formatted string containing tool method source code and dependencies,
        or None if extraction fails

    Example:
        >>> code = extract_tool_code('github_create_issue', 'github')
        >>> if code:
        ...     print(code)
    """
    try:
        # Infer toolkit_type from tool_name if not provided
        if not toolkit_type:
            toolkit_type = _infer_toolkit_type(tool_name)

        if not toolkit_type:
            logger.warning(f"Cannot infer toolkit type for tool '{tool_name}'")
            return None

        # Locate toolkit package
        toolkit_path = _locate_toolkit_package(toolkit_type)
        if not toolkit_path:
            logger.warning(f"Cannot locate toolkit package for type '{toolkit_type}'")
            return None

        # Extract method name from tool name
        method_name = _extract_method_name(tool_name, toolkit_type)

        # Find and extract the method code
        tool_code = _extract_method_from_toolkit(toolkit_path, method_name)

        if tool_code:
            logger.debug(f"Successfully extracted code for tool '{tool_name}' ({len(tool_code)} chars)")
            return tool_code
        else:
            logger.warning(f"Could not find method '{method_name}' in toolkit '{toolkit_type}'")
            return None

    except Exception as e:
        logger.warning(f"Failed to extract tool code for '{tool_name}': {e}", exc_info=True)
        return None


def _infer_toolkit_type(tool_name: str) -> Optional[str]:
    """
    Infer toolkit type from tool name.

    Args:
        tool_name: Tool name like 'github_create_issue'

    Returns:
        Toolkit type like 'github', or None if cannot infer
    """
    # Common pattern: toolkit_action or toolkit_noun_action
    if '_' in tool_name:
        parts = tool_name.split('_')
        # Use first part as toolkit unless it's a common verb
        common_verbs = {'get', 'set', 'create', 'update', 'delete', 'list', 'search', 'add', 'remove'}
        if parts[0].lower() not in common_verbs:
            return parts[0]

    return None


def _locate_toolkit_package(toolkit_type: str) -> Optional[Path]:
    """
    Locate toolkit package directory.

    Handles special cases like ADO sub-toolkits:
    - 'ado_repos' -> tools/ado/repos/
    - 'ado_wiki' -> tools/ado/wiki/
    - 'github' -> tools/github/

    Args:
        toolkit_type: Type of toolkit (e.g., 'github', 'ado_repos')

    Returns:
        Path to toolkit package, or None if not found
    """
    try:
        # Import the toolkit package to get its location
        import alita_sdk.tools
        tools_path = Path(alita_sdk.tools.__file__).parent

        # Check for ADO sub-toolkit pattern (ado_repos, ado_wiki, etc.)
        if toolkit_type.startswith('ado_'):
            # Extract sub-toolkit name: ado_repos -> repos
            sub_toolkit = toolkit_type[4:]  # Remove 'ado_' prefix

            # Path is tools/ado/{sub_toolkit}/
            toolkit_path = tools_path / 'ado' / sub_toolkit

            if toolkit_path.exists() and toolkit_path.is_dir():
                logger.debug(f"Found ADO sub-toolkit '{toolkit_type}' at {toolkit_path}")
                return toolkit_path

            # Fallback: try the ado root directory
            ado_root = tools_path / 'ado'
            if ado_root.exists() and ado_root.is_dir():
                logger.debug(f"Using ADO root for '{toolkit_type}': {ado_root}")
                return ado_root

        # Standard toolkit path
        toolkit_path = tools_path / toolkit_type

        if toolkit_path.exists() and toolkit_path.is_dir():
            return toolkit_path

        return None

    except Exception as e:
        logger.debug(f"Error locating toolkit package for '{toolkit_type}': {e}")
        return None


def _extract_method_name(tool_name: str, toolkit_type: str) -> str:
    """
    Extract method name from tool name.

    Handles special cases:
    - 'ado_repos_create_pr' with toolkit 'ado_repos' -> 'create_pr'
    - 'github_create_issue' with toolkit 'github' -> 'create_issue'

    Args:
        tool_name: Full tool name like 'github_create_issue' or 'ado_repos_create_pr'
        toolkit_type: Toolkit type like 'github' or 'ado_repos'

    Returns:
        Method name like 'create_issue' or 'create_pr'
    """
    # Remove toolkit prefix if present
    if tool_name.startswith(f"{toolkit_type}_"):
        return tool_name[len(toolkit_type) + 1:]

    # For ADO sub-toolkits, also try removing just 'ado_' if toolkit_type starts with it
    if toolkit_type.startswith('ado_'):
        # Try removing the full ado_subtoolkit prefix
        # e.g., tool: ado_repos_create_pr, toolkit: ado_repos -> create_pr
        if tool_name.startswith(f"{toolkit_type}_"):
            return tool_name[len(toolkit_type) + 1:]

        # Also try if tool doesn't have the full prefix
        # e.g., tool: create_pr, toolkit: ado_repos -> create_pr (unchanged)
        sub_toolkit = toolkit_type[4:]  # ado_repos -> repos
        if tool_name.startswith(f"{sub_toolkit}_"):
            return tool_name[len(sub_toolkit) + 1:]

    return tool_name


def _extract_method_from_toolkit(toolkit_path: Path, method_name: str) -> Optional[str]:
    """
    Extract method source code and its dependencies from toolkit files.

    Handles both flat and nested toolkit structures:
    - Flat: tools/github/api_wrapper.py
    - Nested: tools/ado/repos/repos_wrapper.py (ADO-style)

    Args:
        toolkit_path: Path to toolkit package
        method_name: Name of the method to extract

    Returns:
        Formatted source code string, or None if not found
    """
    # Search ALL Python files in the toolkit directory (flat structure)
    # This handles any naming convention: api_wrapper.py, repos_wrapper.py, github_client.py, etc.
    for file_path in toolkit_path.glob('*.py'):
        # Skip __pycache__ and private files
        if file_path.name.startswith('_') and file_path.name != '__init__.py':
            continue

        if not file_path.is_file():
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # Parse the file
            tree = ast.parse(source_code, filename=str(file_path))

            # Find the method
            result = _find_method_in_ast(tree, method_name, source_code, file_path)
            if result:
                return result

        except Exception as e:
            logger.debug(f"Error parsing {file_path}: {e}")
            continue

    # Try nested structure (for toolkits like ADO with subdirectories)
    # Search ALL Python files in subdirectories
    for file_path in toolkit_path.glob('*/*.py'):
        # Skip __pycache__ and private files
        if file_path.name.startswith('_') and file_path.name != '__init__.py':
            continue

        if not file_path.is_file():
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # Parse the file
            tree = ast.parse(source_code, filename=str(file_path))

            # Find the method
            result = _find_method_in_ast(tree, method_name, source_code, file_path)
            if result:
                return result

        except Exception as e:
            logger.debug(f"Error parsing {file_path}: {e}")
            continue

    return None


def _find_method_in_ast(tree: ast.AST, method_name: str, source_code: str, file_path: Path) -> Optional[str]:
    """
    Find method in AST and extract its code with dependencies.

    Args:
        tree: AST tree
        method_name: Method name to find
        source_code: Full source code
        file_path: Path to source file

    Returns:
        Extracted code with dependencies, or None if not found
    """
    lines = source_code.split('\n')

    # Find the method definition
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            # Extract the method source code
            method_code = _extract_node_source(node, lines)

            # Find dependencies (helper methods called within this method)
            dependencies = _find_dependencies(node, tree, lines)

            # Find class context if method is inside a class
            class_info = _find_containing_class(tree, node, lines)

            # Build formatted output
            return _format_tool_code(method_name, method_code, dependencies, class_info, file_path)

    return None


def _extract_node_source(node: ast.AST, lines: List[str]) -> str:
    """
    Extract source code for an AST node.

    Args:
        node: AST node
        lines: Source code lines

    Returns:
        Source code string
    """
    try:
        start_line = getattr(node, 'lineno', 1) - 1
        end_line = getattr(node, 'end_lineno', start_line + 1)

        if start_line < len(lines) and end_line <= len(lines):
            return '\n'.join(lines[start_line:end_line])
    except Exception:
        pass

    return ""


def _find_dependencies(method_node: ast.FunctionDef, tree: ast.AST, lines: List[str]) -> List[Tuple[str, str]]:
    """
    Find helper methods called within the given method.

    Args:
        method_node: The method AST node
        tree: Full AST tree
        lines: Source code lines

    Returns:
        List of tuples (method_name, source_code)
    """
    dependencies = []
    called_methods = set()

    # Find all method calls within the method
    for node in ast.walk(method_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                # self.method_name or obj.method_name
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                    called_methods.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                # Direct function call
                called_methods.add(node.func.id)

    # Extract source code for called methods (limit to a few key dependencies)
    max_dependencies = 3
    for node in ast.walk(tree):
        if len(dependencies) >= max_dependencies:
            break

        if isinstance(node, ast.FunctionDef) and node.name in called_methods:
            # Skip if it's the same method or a builtin/external method
            if node.name.startswith('_') and not node.name.startswith('__'):
                dep_code = _extract_node_source(node, lines)
                if dep_code:
                    dependencies.append((node.name, dep_code))

    return dependencies


def _find_containing_class(tree: ast.AST, method_node: ast.FunctionDef, lines: List[str]) -> Optional[Tuple[str, str]]:
    """
    Find the class containing the method.

    Args:
        tree: Full AST tree
        method_node: Method AST node
        lines: Source code lines

    Returns:
        Tuple of (class_name, class_signature) or None
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if method_node is within this class
            for item in node.body:
                if item == method_node:
                    # Extract class signature (first line)
                    class_line = getattr(node, 'lineno', 1) - 1
                    if class_line < len(lines):
                        class_signature = lines[class_line].strip()

                        # Add base classes info
                        bases = []
                        for base in node.bases:
                            if isinstance(base, ast.Name):
                                bases.append(base.id)
                            elif isinstance(base, ast.Attribute):
                                bases.append(base.attr)

                        if bases:
                            class_signature += f" (inherits from: {', '.join(bases)})"

                        return (node.name, class_signature)

    return None


def _format_tool_code(
    method_name: str,
    method_code: str,
    dependencies: List[Tuple[str, str]],
    class_info: Optional[Tuple[str, str]],
    file_path: Path
) -> str:
    """
    Format extracted code into a readable string.

    Args:
        method_name: Method name
        method_code: Method source code
        dependencies: List of (dep_name, dep_code)
        class_info: Tuple of (class_name, class_signature)
        file_path: Source file path

    Returns:
        Formatted code string
    """
    parts = []

    # Header
    parts.append("=" * 80)
    parts.append(f"Tool Implementation: {method_name}")
    parts.append(f"Source: {file_path.name}")
    parts.append("=" * 80)
    parts.append("")

    # Class context
    if class_info:
        class_name, class_signature = class_info
        parts.append(f"Class Context: {class_signature}")
        parts.append("")

    # Main method
    parts.append(f"Method: {method_name}")
    parts.append("-" * 80)
    parts.append(method_code)
    parts.append("")

    # Dependencies
    if dependencies:
        parts.append("Helper Methods:")
        parts.append("-" * 80)
        for dep_name, dep_code in dependencies:
            parts.append(f"\nHelper: {dep_name}")
            parts.append(dep_code)
            parts.append("")

    parts.append("=" * 80)

    return "\n".join(parts)


def clear_cache():
    """Clear the LRU cache for tool code extraction."""
    extract_tool_code.cache_clear()
    logger.info("Tool code extraction cache cleared")


def get_cache_info():
    """Get cache statistics."""
    return extract_tool_code.cache_info()

