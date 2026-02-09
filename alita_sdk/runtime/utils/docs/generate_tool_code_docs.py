"""
Script to pre-generate tool code documentation as markdown files.

This script extracts source code for all tools across all toolkits and saves them
as markdown files in docs/code/ directory. This eliminates runtime AST parsing
overhead and provides static code snippets for LLM error context.

Usage:
    python generate_tool_code_docs.py
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def discover_toolkits(tools_dir: Path) -> List[Tuple[str, Path]]:
    """
    Discover all toolkit directories.

    Returns:
        List of (toolkit_name, toolkit_path) tuples
    """
    toolkits = []

    # Direct toolkit directories
    for item in tools_dir.iterdir():
        if item.is_dir() and not item.name.startswith('_') and not item.name.startswith('.'):
            # Skip utility/base directories
            if item.name in ['base', 'utils', 'chunkers', 'vector_adapters', 'cloud', 'code']:
                continue
            toolkits.append((item.name, item))

    # ADO sub-toolkits (special case)
    ado_dir = tools_dir / 'ado'
    if ado_dir.exists():
        for subdir in ado_dir.iterdir():
            if subdir.is_dir() and not subdir.name.startswith('_'):
                toolkit_name = f"ado_{subdir.name}"
                toolkits.append((toolkit_name, subdir))

    return sorted(toolkits)


def find_python_files(toolkit_path: Path) -> List[Path]:
    """Find all Python files in toolkit directory."""
    python_files = []

    # Direct Python files
    for file_path in toolkit_path.glob('*.py'):
        if not file_path.name.startswith('_') or file_path.name == '__init__.py':
            python_files.append(file_path)

    # Nested Python files (one level deep)
    for file_path in toolkit_path.glob('*/*.py'):
        if not file_path.name.startswith('_') or file_path.name == '__init__.py':
            python_files.append(file_path)

    return python_files


def extract_all_methods(file_path: Path) -> List[Tuple[str, ast.FunctionDef, Optional[str]]]:
    """
    Extract all public methods from a Python file.

    Returns:
        List of (method_name, ast_node, class_name) tuples
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        tree = ast.parse(source_code, filename=str(file_path))
        methods = []

        # Find methods at module level and in classes
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private methods
                if node.name.startswith('_'):
                    continue

                # Find containing class if any
                class_name = None
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef):
                        for child in ast.walk(parent):
                            if child is node:
                                class_name = parent.name
                                break

                methods.append((node.name, node, class_name))

        return methods

    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return []


def extract_method_code(node: ast.FunctionDef, source_lines: List[str]) -> str:
    """Extract source code for a method."""
    try:
        start_line = node.lineno - 1
        end_line = node.end_lineno if node.end_lineno else start_line + 1

        # Get the method code
        method_lines = source_lines[start_line:end_line]
        return '\n'.join(method_lines)
    except Exception as e:
        logger.debug(f"Failed to extract method code: {e}")
        return ""


def find_helper_methods(node: ast.FunctionDef, all_methods: List[Tuple[str, ast.FunctionDef, Optional[str]]],
                        source_lines: List[str], max_helpers: int = 3) -> List[str]:
    """
    Find helper methods called by this method.

    Returns:
        List of helper method source code strings
    """
    helpers = []
    called_methods: Set[str] = set()

    # Find all method calls in the node
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                # self.method_name or object.method_name
                if isinstance(child.func.value, ast.Name) and child.func.value.id == 'self':
                    called_methods.add(child.func.attr)
            elif isinstance(child.func, ast.Name):
                # Direct function call
                called_methods.add(child.func.id)

    # Extract source for called helper methods (up to max_helpers)
    for method_name in list(called_methods)[:max_helpers]:
        for name, method_node, _ in all_methods:
            if name == method_name and method_node is not node:
                helper_code = extract_method_code(method_node, source_lines)
                if helper_code:
                    helpers.append(f"Helper: {method_name}\n{helper_code}")
                break

    return helpers


def format_tool_code_markdown(toolkit_name: str, method_name: str, method_code: str,
                               class_name: Optional[str], file_name: str,
                               helpers: List[str]) -> str:
    """
    Format tool code as markdown.

    Returns:
        Markdown formatted string
    """
    md_parts = [
        f"# {toolkit_name} - {method_name}",
        "",
        f"**Toolkit**: `{toolkit_name}`",
        f"**Method**: `{method_name}`",
        f"**Source File**: `{file_name}`",
    ]

    if class_name:
        md_parts.append(f"**Class**: `{class_name}`")

    md_parts.extend([
        "",
        "---",
        "",
        "## Method Implementation",
        "",
        "```python",
        method_code,
        "```",
        ""
    ])

    # Add helper methods if any
    if helpers:
        md_parts.extend([
            "## Helper Methods",
            "",
        ])
        for helper in helpers:
            md_parts.extend([
                "```python",
                helper,
                "```",
                ""
            ])

    return '\n'.join(md_parts)


def generate_tool_code_docs(sdk_root: Path, output_dir: Path) -> Dict[str, int]:
    """
    Generate tool code documentation for all toolkits.

    Returns:
        Statistics dictionary
    """
    # sdk_root is already alita_sdk/ directory, so tools/ is directly under it
    tools_dir = sdk_root / 'tools'

    if not tools_dir.exists():
        logger.error(f"Tools directory not found: {tools_dir}")
        return {'error': 1}

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        'toolkits': 0,
        'files_processed': 0,
        'methods_extracted': 0,
        'docs_generated': 0,
        'errors': 0
    }

    # Discover all toolkits
    toolkits = discover_toolkits(tools_dir)
    logger.info(f"Found {len(toolkits)} toolkits")

    for toolkit_name, toolkit_path in toolkits:
        logger.info(f"\nProcessing toolkit: {toolkit_name}")
        stats['toolkits'] += 1

        # Find all Python files in toolkit
        python_files = find_python_files(toolkit_path)
        logger.info(f"  Found {len(python_files)} Python files")

        for file_path in python_files:
            stats['files_processed'] += 1

            # Read source code
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                source_lines = source_code.split('\n')
            except Exception as e:
                logger.warning(f"  Failed to read {file_path.name}: {e}")
                stats['errors'] += 1
                continue

            # Extract all methods
            methods = extract_all_methods(file_path)

            if not methods:
                continue

            logger.info(f"  Processing {file_path.name}: {len(methods)} methods")

            for method_name, method_node, class_name in methods:
                try:
                    # Extract method code
                    method_code = extract_method_code(method_node, source_lines)

                    if not method_code:
                        continue

                    # Find helper methods
                    helpers = find_helper_methods(method_node, methods, source_lines)

                    # Format as markdown
                    markdown = format_tool_code_markdown(
                        toolkit_name=toolkit_name,
                        method_name=method_name,
                        method_code=method_code,
                        class_name=class_name,
                        file_name=file_path.name,
                        helpers=helpers
                    )

                    # Save to file
                    # Use toolkit_name__method_name.md to avoid conflicts
                    output_file = output_dir / f"{toolkit_name}__{method_name}.md"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(markdown)

                    stats['methods_extracted'] += 1
                    stats['docs_generated'] += 1

                except Exception as e:
                    logger.warning(f"  Failed to process method '{method_name}': {e}")
                    stats['errors'] += 1

    return stats


def main():
    """Main execution function."""

    # Use relative path from script location instead of importing alita_sdk
    # This allows the script to work during build when package isn't installed
    # Script is at: alita_sdk/runtime/utils/docs/generate_tool_code_docs.py
    # Need to go up to: alita_sdk/
    script_dir = Path(__file__).parent  # alita_sdk/runtime/utils/docs/
    sdk_root = script_dir.parent.parent.parent  # alita_sdk/

    # Output directory for generated docs
    output_dir = sdk_root / 'docs' / 'code'

    print("=" * 80)
    print("Tool Code Documentation Generator")
    print("=" * 80)
    print(f"SDK Root: {sdk_root}")
    print(f"Output Directory: {output_dir}")
    print("=" * 80)
    print()

    # Generate documentation
    stats = generate_tool_code_docs(sdk_root, output_dir)

    # Print summary
    print()
    print("=" * 80)
    print("Generation Summary")
    print("=" * 80)
    print(f"Toolkits processed:     {stats.get('toolkits', 0)}")
    print(f"Python files processed: {stats.get('files_processed', 0)}")
    print(f"Methods extracted:      {stats.get('methods_extracted', 0)}")
    print(f"Docs generated:         {stats.get('docs_generated', 0)}")
    print(f"Errors encountered:     {stats.get('errors', 0)}")
    print("=" * 80)
    print()
    print(f"✓ Documentation generated in: {output_dir}")
    print()

    return 0 if stats.get('errors', 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

