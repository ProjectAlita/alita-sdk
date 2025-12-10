"""
Filesystem tools for CLI agents.

Provides comprehensive file system operations restricted to specific directories.
Inspired by MCP filesystem server implementation.

Also provides a FilesystemApiWrapper for integration with the inventory ingestion
pipeline, enabling local document loading and chunking.
"""

import base64
import fnmatch
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator, ClassVar
from datetime import datetime
from langchain_core.tools import BaseTool, ToolException
from langchain_core.documents import Document
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


# Maximum recommended content size for single write operations (in characters)
MAX_RECOMMENDED_CONTENT_SIZE = 5000  # ~5KB, roughly 1,200-1,500 tokens

# Helpful error message for truncated content
CONTENT_TRUNCATED_ERROR = """
⚠️  CONTENT FIELD MISSING - OUTPUT TRUNCATED

Your tool call was cut off because the content was too large for the context window.
The JSON was truncated, leaving the 'content' field incomplete or missing.

🔧 HOW TO FIX THIS:

1. **Use incremental writes** - Don't write large files in one call:
   - First: filesystem_write_file(path, "# Header\\nimport x\\n\\n")
   - Then: filesystem_append_file(path, "def func1():\\n    ...\\n\\n")
   - Then: filesystem_append_file(path, "def func2():\\n    ...\\n\\n")

2. **Keep each chunk small** - Under 2000 characters per call

3. **Structure first, details later**:
   - Write skeleton/structure first
   - Add implementations section by section

4. **For documentation/reports**:
   - Write one section at a time
   - Use append_file for each new section

❌ DON'T: Try to write the entire file content again
✅ DO: Break it into 3-5 smaller append_file calls
"""


class ReadFileInput(BaseModel):
    """Input for reading a file."""
    path: str = Field(description="Relative path to the file to read")
    head: Optional[int] = Field(None, description="If provided, read only the first N lines")
    tail: Optional[int] = Field(None, description="If provided, read only the last N lines")


class ReadFileChunkInput(BaseModel):
    """Input for reading a file in chunks."""
    path: str = Field(description="Relative path to the file to read")
    start_line: int = Field(default=1, description="Starting line number (1-indexed)")
    end_line: Optional[int] = Field(None, description="Ending line number (inclusive). If None, read to end of file")


class ApplyPatchInput(BaseModel):
    """Input for applying multiple edits to a file."""
    path: str = Field(description="Relative path to the file to edit")
    edits: List[Dict[str, str]] = Field(
        description="List of edits, each with 'old_text' and 'new_text' keys. Applied sequentially."
    )
    dry_run: bool = Field(default=False, description="If True, preview changes without applying them")


class ReadMultipleFilesInput(BaseModel):
    """Input for reading multiple files."""
    paths: List[str] = Field(
        min_length=1,
        description="Array of file paths to read. Each path must point to a valid file within allowed directories."
    )


class WriteFileInput(BaseModel):
    """Input for writing to a file."""
    path: str = Field(description="Relative path to the file to write")
    content: Optional[str] = Field(
        default=None,
        description="Content to write to the file. REQUIRED - this field cannot be empty or omitted."
    )
    
    @model_validator(mode='after')
    def validate_content_required(self):
        """Provide helpful error message when content is missing or truncated."""
        if self.content is None:
            raise ToolException(CONTENT_TRUNCATED_ERROR)
        if len(self.content) > MAX_RECOMMENDED_CONTENT_SIZE:
            logger.warning(
                f"Content is very large ({len(self.content)} chars). Consider using append_file "
                "for incremental writes to avoid truncation issues."
            )
        return self


class AppendFileInput(BaseModel):
    """Input for appending to a file."""
    path: str = Field(description="Relative path to the file to append to")
    content: Optional[str] = Field(
        default=None,
        description="Content to append to the end of the file. REQUIRED - this field cannot be empty or omitted."
    )
    
    @model_validator(mode='after')
    def validate_content_required(self):
        """Provide helpful error message when content is missing or truncated."""
        if self.content is None:
            raise ToolException(CONTENT_TRUNCATED_ERROR)
        return self


class EditFileInput(BaseModel):
    """Input for editing a file with precise replacements."""
    path: str = Field(description="Relative path to the file to edit")
    old_text: str = Field(description="Exact text to search for and replace")
    new_text: str = Field(description="Text to replace with")


class ListDirectoryInput(BaseModel):
    """Input for listing directory contents."""
    path: str = Field(default=".", description="Relative path to the directory to list")
    include_sizes: bool = Field(default=False, description="Include file sizes in the output")
    sort_by: str = Field(default="name", description="Sort by 'name' or 'size'")
    max_results: Optional[int] = Field(default=200, description="Maximum number of entries to return. Default is 200 to prevent context overflow.")


class DirectoryTreeInput(BaseModel):
    """Input for getting a directory tree."""
    path: str = Field(default=".", description="Relative path to the directory")
    max_depth: Optional[int] = Field(default=3, description="Maximum depth to traverse. Default is 3 to prevent excessive output. Use None for unlimited (caution: may exceed context limits).")
    max_items: Optional[int] = Field(default=200, description="Maximum number of files/directories to include. Default is 200 to prevent context window overflow. Use None for unlimited (caution: large directories may exceed context limits).")


class SearchFilesInput(BaseModel):
    """Input for searching files."""
    path: str = Field(default=".", description="Relative path to search from")
    pattern: str = Field(description="Glob pattern to match (e.g., '*.py', '**/*.txt')")
    max_results: Optional[int] = Field(default=100, description="Maximum number of results to return. Default is 100 to prevent context overflow. Use None for unlimited.")


class DeleteFileInput(BaseModel):
    """Input for deleting a file."""
    path: str = Field(description="Relative path to the file to delete")


class MoveFileInput(BaseModel):
    """Input for moving/renaming a file."""
    source: str = Field(description="Relative path to the source file")
    destination: str = Field(description="Relative path to the destination")


class CreateDirectoryInput(BaseModel):
    """Input for creating a directory."""
    path: str = Field(description="Relative path to the directory to create")


class GetFileInfoInput(BaseModel):
    """Input for getting file information."""
    path: str = Field(description="Relative path to the file or directory")


class EmptyInput(BaseModel):
    """Empty input schema for tools that take no arguments."""
    pass


class FileSystemTool(BaseTool):
    """Base class for filesystem tools with directory restriction."""
    base_directory: str  # Primary directory (for backward compatibility)
    allowed_directories: List[str] = []  # Additional allowed directories
    _basename_collision_detected: bool = False  # Cache for collision detection
    _basename_collision_checked: bool = False  # Whether we've checked for collisions
    
    def _get_all_allowed_directories(self) -> List[Path]:
        """Get all allowed directories as resolved Paths."""
        dirs = [Path(self.base_directory).resolve()]
        for d in self.allowed_directories:
            resolved = Path(d).resolve()
            if resolved not in dirs:
                dirs.append(resolved)
        return dirs
    
    def _check_basename_collision(self) -> bool:
        """Check if multiple allowed directories have the same basename."""
        if self._basename_collision_checked:
            return self._basename_collision_detected
        
        allowed_dirs = self._get_all_allowed_directories()
        basenames = [d.name for d in allowed_dirs]
        self._basename_collision_detected = len(basenames) != len(set(basenames))
        self._basename_collision_checked = True
        return self._basename_collision_detected
    
    def _get_relative_path_from_allowed_dirs(self, absolute_path: Path) -> tuple:
        """Get relative path and directory name for a file in allowed directories.
        
        Args:
            absolute_path: Absolute path to the file
            
        Returns:
            Tuple of (relative_path, directory_name)
            
        Raises:
            ValueError: If path is not within any allowed directory
        """
        allowed_dirs = self._get_all_allowed_directories()
        
        # Find which allowed directory contains this path
        for base in allowed_dirs:
            try:
                rel_path = absolute_path.relative_to(base)
                
                # Determine directory name for prefix
                if self._check_basename_collision():
                    # Use parent/basename format to disambiguate
                    dir_name = f"{base.parent.name}/{base.name}"
                else:
                    # Use just basename
                    dir_name = base.name
                
                return (str(rel_path), dir_name)
            except ValueError:
                continue
        
        # Path not in any allowed directory
        allowed_paths = [str(d) for d in allowed_dirs]
        raise ValueError(
            f"Path '{absolute_path}' is not within any allowed directory.\n"
            f"Allowed directories: {allowed_paths}\n"
            f"Attempted path: {absolute_path}"
        )
    
    def _resolve_path(self, relative_path: str) -> Path:
        """
        Resolve and validate a path within any of the allowed directories.
        
        Security: Ensures resolved path is within one of the allowed directories.
        """
        allowed_dirs = self._get_all_allowed_directories()
        
        # Handle absolute paths - check if within any allowed directory
        if Path(relative_path).is_absolute():
            target = Path(relative_path).resolve()
            for base in allowed_dirs:
                try:
                    target.relative_to(base)
                    return target
                except ValueError:
                    continue
            raise ValueError(f"Access denied: path '{relative_path}' is outside allowed directories")
        
        # For relative paths, try to resolve against each allowed directory
        # First check primary base_directory
        primary_base = allowed_dirs[0]
        target = (primary_base / relative_path).resolve()
        
        # Check if target is within any allowed directory
        for base in allowed_dirs:
            try:
                target.relative_to(base)
                return target
            except ValueError:
                continue
        
        # If relative path doesn't work from primary, try finding the file in other directories
        for base in allowed_dirs[1:]:
            candidate = (base / relative_path).resolve()
            if candidate.exists():
                return candidate
        
        # Default to primary base directory resolution
        raise ValueError(f"Access denied: path '{relative_path}' is outside allowed directories")
    
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


class ReadFileTool(FileSystemTool):
    """Read file contents with optional head/tail support."""
    name: str = "filesystem_read_file"
    description: str = (
        "Read the complete contents of a file from the file system. "
        "Handles various text encodings and provides detailed error messages if the file cannot be read. "
        "Use 'head' parameter to read only the first N lines, or 'tail' parameter to read only the last N lines. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = ReadFileInput
    truncation_suggestions: ClassVar[List[str]] = [
        "Use head=100 to read only the first 100 lines",
        "Use tail=100 to read only the last 100 lines",
        "Use filesystem_read_file_chunk with start_line and end_line for specific sections",
    ]
    
    def _run(self, path: str, head: Optional[int] = None, tail: Optional[int] = None) -> str:
        """Read a file with optional head/tail."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: File '{path}' does not exist"
            
            if not target.is_file():
                return f"Error: '{path}' is not a file"
            
            if head and tail:
                return "Error: Cannot specify both head and tail parameters simultaneously"
            
            with open(target, 'r', encoding='utf-8') as f:
                if tail:
                    lines = f.readlines()
                    content = ''.join(lines[-tail:])
                elif head:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= head:
                            break
                        lines.append(line)
                    content = ''.join(lines)
                else:
                    content = f.read()
            
            char_count = len(content)
            line_count = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            
            return f"Successfully read '{path}' ({char_count} characters, {line_count} lines):\n\n{content}"
        except UnicodeDecodeError:
            return f"Error: File '{path}' appears to be binary or uses an unsupported encoding"
        except Exception as e:
            return f"Error reading file '{path}': {str(e)}"


class ReadFileChunkTool(FileSystemTool):
    """Read a file in chunks by line range."""
    name: str = "filesystem_read_file_chunk"
    description: str = (
        "Read a specific range of lines from a file. This is efficient for large files where you only need a portion. "
        "Specify start_line (1-indexed) and optionally end_line. If end_line is omitted, reads to end of file. "
        "Use this to avoid loading entire large files into memory. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = ReadFileChunkInput
    truncation_suggestions: ClassVar[List[str]] = [
        "Reduce the line range (end_line - start_line) to read fewer lines at once",
        "Read smaller chunks sequentially if you need to process the entire file",
    ]
    
    def _run(self, path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
        """Read a chunk of a file by line range."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: File '{path}' does not exist"
            
            if not target.is_file():
                return f"Error: '{path}' is not a file"
            
            if start_line < 1:
                return "Error: start_line must be >= 1"
            
            if end_line is not None and end_line < start_line:
                return "Error: end_line must be >= start_line"
            
            lines = []
            with open(target, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    if i < start_line:
                        continue
                    if end_line is not None and i > end_line:
                        break
                    lines.append(line)
            
            content = ''.join(lines)
            actual_end = end_line if end_line else start_line + len(lines) - 1
            
            if not lines:
                return f"No lines found in range {start_line}-{actual_end} in '{path}'"
            
            return f"Successfully read '{path}' lines {start_line}-{actual_end} ({len(content)} characters, {len(lines)} lines):\n\n{content}"
        except UnicodeDecodeError:
            return f"Error: File '{path}' appears to be binary or uses an unsupported encoding"
        except Exception as e:
            return f"Error reading file '{path}': {str(e)}"


class ReadMultipleFilesTool(FileSystemTool):
    """Read multiple files simultaneously."""
    name: str = "filesystem_read_multiple_files"
    description: str = (
        "Read the contents of multiple files simultaneously. This is more efficient than reading files one by one. "
        "Each file's content is returned with its path as a reference. "
        "Failed reads for individual files won't stop the entire operation. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = ReadMultipleFilesInput
    truncation_suggestions: ClassVar[List[str]] = [
        "Read fewer files at once - split into multiple smaller batches",
        "Use filesystem_read_file with head parameter on individual large files instead",
    ]
    
    def _run(self, paths: List[str]) -> str:
        """Read multiple files."""
        results = []
        
        for file_path in paths:
            try:
                target = self._resolve_path(file_path)
                with open(target, 'r', encoding='utf-8') as f:
                    content = f.read()
                results.append(f"{file_path}:\n{content}")
            except Exception as e:
                results.append(f"{file_path}: Error - {str(e)}")
        
        return "\n\n---\n\n".join(results)


class WriteFileTool(FileSystemTool):
    """Write content to a file."""
    name: str = "filesystem_write_file"
    description: str = (
        "Create a new file or completely overwrite an existing file with new content. "
        "Use with caution as it will overwrite existing files without warning. "
        "Handles text content with proper encoding. Creates parent directories if needed. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = WriteFileInput
    
    def _run(self, path: str, content: str) -> str:
        """Write to a file."""
        try:
            target = self._resolve_path(path)
            
            # Create parent directories if they don't exist
            target.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)
            
            size = len(content.encode('utf-8'))
            return f"Successfully wrote to '{path}' ({self._format_size(size)})"
        except Exception as e:
            return f"Error writing to file '{path}': {str(e)}"


class AppendFileTool(FileSystemTool):
    """Append content to the end of a file."""
    name: str = "filesystem_append_file"
    description: str = (
        "Append content to the end of an existing file. Creates the file if it doesn't exist. "
        "Use this for incremental file creation - write initial structure with write_file, "
        "then add sections progressively with append_file. This is safer than rewriting "
        "entire files and prevents context overflow. Only works within allowed directories."
    )
    args_schema: type[BaseModel] = AppendFileInput
    
    def _run(self, path: str, content: str) -> str:
        """Append to a file."""
        try:
            target = self._resolve_path(path)
            
            # Create parent directories if they don't exist
            target.parent.mkdir(parents=True, exist_ok=True)
            
            # Check current file size if it exists
            existed = target.exists()
            original_size = target.stat().st_size if existed else 0
            
            with open(target, 'a', encoding='utf-8') as f:
                f.write(content)
            
            appended_size = len(content.encode('utf-8'))
            new_size = original_size + appended_size
            
            if existed:
                return f"Successfully appended {self._format_size(appended_size)} to '{path}' (total: {self._format_size(new_size)})"
            else:
                return f"Created '{path}' and wrote {self._format_size(appended_size)}"
        except Exception as e:
            return f"Error appending to file '{path}': {str(e)}"


class EditFileTool(FileSystemTool):
    """Edit file with precise text replacement."""
    name: str = "filesystem_edit_file"
    description: str = (
        "Make precise edits to a text file by replacing exact text matches. "
        "The old_text must match exactly (including whitespace and line breaks). "
        "This is safer than rewriting entire files when making small changes. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = EditFileInput
    
    def _run(self, path: str, old_text: str, new_text: str) -> str:
        """Edit a file by replacing exact text."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: File '{path}' does not exist"
            
            if not target.is_file():
                return f"Error: '{path}' is not a file"
            
            # Read current content
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if old_text exists
            if old_text not in content:
                return f"Error: Could not find the specified text in '{path}'"
            
            # Count occurrences
            occurrences = content.count(old_text)
            if occurrences > 1:
                return f"Error: Found {occurrences} occurrences of the text. Please be more specific to ensure correct replacement."
            
            # Replace text
            new_content = content.replace(old_text, new_text)
            
            # Write back
            with open(target, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            chars_before = len(old_text)
            chars_after = len(new_text)
            diff = chars_after - chars_before
            
            return f"Successfully edited '{path}': replaced {chars_before} characters with {chars_after} characters ({diff:+d} character difference)"
        except Exception as e:
            return f"Error editing file '{path}': {str(e)}"


class ApplyPatchTool(FileSystemTool):
    """Apply multiple edits to a file like a patch."""
    name: str = "filesystem_apply_patch"
    description: str = (
        "Apply multiple precise edits to a file in a single operation, similar to applying a patch. "
        "Each edit specifies 'old_text' (exact text to find) and 'new_text' (replacement text). "
        "Edits are applied sequentially. Use dry_run=true to preview changes without applying them. "
        "This is efficient for making multiple changes to large files. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = ApplyPatchInput
    
    def _run(self, path: str, edits: List[Dict[str, str]], dry_run: bool = False) -> str:
        """Apply multiple edits to a file."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: File '{path}' does not exist"
            
            if not target.is_file():
                return f"Error: '{path}' is not a file"
            
            # Read current content
            with open(target, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            content = original_content
            changes = []
            
            # Apply edits sequentially
            for i, edit in enumerate(edits, 1):
                old_text = edit.get('old_text', '')
                new_text = edit.get('new_text', '')
                
                if not old_text:
                    return f"Error: Edit #{i} is missing 'old_text'"
                
                if old_text not in content:
                    return f"Error: Edit #{i} - could not find the specified text in current content"
                
                # Count occurrences
                occurrences = content.count(old_text)
                if occurrences > 1:
                    return f"Error: Edit #{i} - found {occurrences} occurrences. Please be more specific."
                
                # Apply the edit
                content = content.replace(old_text, new_text)
                changes.append({
                    'edit_num': i,
                    'old_len': len(old_text),
                    'new_len': len(new_text),
                    'diff': len(new_text) - len(old_text)
                })
            
            if dry_run:
                # Show preview in diff-like format
                lines = [f"Preview of changes to '{path}' ({len(edits)} edits):\n"]
                for change in changes:
                    lines.append(
                        f"Edit #{change['edit_num']}: "
                        f"{change['old_len']} → {change['new_len']} chars "
                        f"({change['diff']:+d})"
                    )
                
                total_diff = sum(c['diff'] for c in changes)
                lines.append(f"\nTotal change: {len(original_content)} → {len(content)} chars ({total_diff:+d})")
                lines.append("\n[DRY RUN - No changes written to file]")
                return "\n".join(lines)
            
            # Write the modified content
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Build success message
            lines = [f"Successfully applied {len(edits)} edits to '{path}':\n"]
            for change in changes:
                lines.append(
                    f"Edit #{change['edit_num']}: "
                    f"{change['old_len']} → {change['new_len']} chars "
                    f"({change['diff']:+d})"
                )
            
            total_diff = sum(c['diff'] for c in changes)
            lines.append(f"\nTotal change: {len(original_content)} → {len(content)} chars ({total_diff:+d})")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error applying patch to '{path}': {str(e)}"


class ListDirectoryTool(FileSystemTool):
    """List directory contents."""
    name: str = "filesystem_list_directory"
    description: str = (
        "Get a detailed listing of all files and directories in a specified path. "
        "Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. "
        "Can optionally include file sizes and sort by name or size. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = ListDirectoryInput
    truncation_suggestions: ClassVar[List[str]] = [
        "List a specific subdirectory instead of the root directory",
        "Consider using filesystem_directory_tree with max_depth=1 for hierarchical overview",
    ]
    
    def _run(self, path: str = ".", include_sizes: bool = False, sort_by: str = "name", max_results: Optional[int] = 200) -> str:
        """List directory contents."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: Directory '{path}' does not exist"
            
            if not target.is_dir():
                return f"Error: '{path}' is not a directory"
            
            entries = []
            for entry in target.iterdir():
                entry_info = {
                    'name': entry.name,
                    'is_dir': entry.is_dir(),
                    'size': entry.stat().st_size if entry.is_file() else 0,
                    'path': entry
                }
                entries.append(entry_info)
            
            # Sort entries
            if sort_by == "size":
                entries.sort(key=lambda x: x['size'], reverse=True)
            else:
                entries.sort(key=lambda x: x['name'].lower())
            
            # Apply limit
            total_count = len(entries)
            truncated = False
            if max_results is not None and total_count > max_results:
                entries = entries[:max_results]
                truncated = True
            
            # Get directory name for multi-directory configs
            allowed_dirs = self._get_all_allowed_directories()
            has_multiple_dirs = len(allowed_dirs) > 1
            _, dir_name = self._get_relative_path_from_allowed_dirs(target) if has_multiple_dirs else ("", "")
            
            # Format output
            lines = []
            total_files = 0
            total_dirs = 0
            total_size = 0
            
            for entry in entries:
                prefix = "[DIR] " if entry['is_dir'] else "[FILE]"
                
                # Add directory prefix for multi-directory configs
                if has_multiple_dirs:
                    name = f"{dir_name}/{entry['name']}"
                else:
                    name = entry['name']
                
                if include_sizes and not entry['is_dir']:
                    size_str = self._format_size(entry['size'])
                    lines.append(f"{prefix} {name:<40} {size_str:>10}")
                    total_size += entry['size']
                else:
                    lines.append(f"{prefix} {name}")
                
                if entry['is_dir']:
                    total_dirs += 1
                else:
                    total_files += 1
            
            result = "\n".join(lines)
            
            # Add header showing the listing context
            if path in (".", "", "./"):
                header = "Contents of working directory (./):\n\n"
            else:
                header = f"Contents of {path}/:\n\n"
            result = header + result
            
            if include_sizes:
                summary = f"\n\nTotal: {total_files} files, {total_dirs} directories"
                if total_files > 0:
                    summary += f"\nCombined size: {self._format_size(total_size)}"
                result += summary
            
            if truncated:
                result += f"\n\n⚠️  OUTPUT TRUNCATED: Showing {len(entries)} of {total_count} entries from '{dir_name if has_multiple_dirs else path}' (max_results={max_results})"
                result += "\n   To see more: increase max_results or list a specific subdirectory"
            
            # Add note about how to access files
            result += "\n\nNote: Access files using paths shown above (e.g., 'agents/file.md' for items in agents/ directory)"
            
            return result if lines else "Directory is empty"
        except Exception as e:
            return f"Error listing directory '{path}': {str(e)}"


class DirectoryTreeTool(FileSystemTool):
    """Get recursive directory tree."""
    name: str = "filesystem_directory_tree"
    description: str = (
        "Get a recursive tree view of files and directories. "
        "Shows the complete structure in an easy-to-read tree format. "
        "IMPORTANT: For large directories, use max_depth (default: 3) and max_items (default: 200) "
        "to prevent context window overflow. Increase these only if needed for smaller directories. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = DirectoryTreeInput
    truncation_suggestions: ClassVar[List[str]] = [
        "Use max_depth=2 to limit directory traversal depth",
        "Use max_items=50 to limit total items returned",
        "Target a specific subdirectory instead of the root",
    ]
    
    # Track item count during tree building
    _item_count: int = 0
    _max_items: Optional[int] = None
    _truncated: bool = False
    
    def _build_tree(self, directory: Path, prefix: str = "", depth: int = 0, max_depth: Optional[int] = None) -> List[str]:
        """Recursively build directory tree with item limit."""
        # Check depth limit
        if max_depth is not None and depth >= max_depth:
            return []
        
        # Check item limit
        if self._max_items is not None and self._item_count >= self._max_items:
            if not self._truncated:
                self._truncated = True
            return []
        
        lines = []
        try:
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for i, entry in enumerate(entries):
                # Check item limit before adding each entry
                if self._max_items is not None and self._item_count >= self._max_items:
                    if not self._truncated:
                        self._truncated = True
                    break
                
                is_last = i == len(entries) - 1
                current_prefix = "└── " if is_last else "├── "
                next_prefix = "    " if is_last else "│   "
                
                self._item_count += 1
                
                if entry.is_dir():
                    lines.append(f"{prefix}{current_prefix}📁 {entry.name}/")
                    lines.extend(self._build_tree(entry, prefix + next_prefix, depth + 1, max_depth))
                else:
                    size = self._format_size(entry.stat().st_size)
                    lines.append(f"{prefix}{current_prefix}📄 {entry.name} ({size})")
        except PermissionError:
            lines.append(f"{prefix}[Permission Denied]")
        
        return lines
    
    def _run(self, path: str = ".", max_depth: Optional[int] = 3, max_items: Optional[int] = 200) -> str:
        """Get directory tree with size limits to prevent context overflow."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: Directory '{path}' does not exist"
            
            if not target.is_dir():
                return f"Error: '{path}' is not a directory"
            
            # Reset counters for this run
            self._item_count = 0
            self._max_items = max_items
            self._truncated = False
            
            # Show relative path from base directory, use '.' for root
            # This prevents confusion - files should be accessed relative to working directory
            if path in (".", "", "./"):
                display_root = "."  # Root of working directory
            else:
                display_root = path.rstrip('/')
            
            lines = [f"📁 {display_root}/"]
            lines.extend(self._build_tree(target, "", 0, max_depth))
            
            # Add truncation warning if limit was reached
            if self._truncated:
                lines.append("")
                lines.append(f"⚠️  OUTPUT TRUNCATED: Showing {self._item_count} of more items (max_items={max_items}, max_depth={max_depth})")
                lines.append(f"   To see more: increase max_items or max_depth, or use filesystem_list_directory on specific subdirectories")
            
            # Add note about file paths
            lines.append("")
            lines.append("Note: Use paths relative to working directory (e.g., 'agents/file.md', not including the root directory name)")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error building directory tree for '{path}': {str(e)}"


class SearchFilesTool(FileSystemTool):
    """Search for files matching a pattern."""
    name: str = "filesystem_search_files"
    description: str = (
        "Recursively search for files and directories matching a glob pattern. "
        "Use patterns like '*.py' for Python files in current dir, or '**/*.py' for all Python files recursively. "
        "Returns paths to matching items (default limit: 100 results to prevent context overflow). "
        "Only searches within allowed directories."
    )
    args_schema: type[BaseModel] = SearchFilesInput
    truncation_suggestions: ClassVar[List[str]] = [
        "Use max_results=50 to limit number of results",
        "Use a more specific glob pattern (e.g., 'src/**/*.py' instead of '**/*.py')",
        "Search in a specific subdirectory instead of the root",
    ]
    
    def _run(self, path: str = ".", pattern: str = "*", max_results: Optional[int] = 100) -> str:
        """Search for files with result limit."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: Directory '{path}' does not exist"
            
            if not target.is_dir():
                return f"Error: '{path}' is not a directory"
            
            # Use glob to find matching files
            all_matches = list(target.glob(pattern))
            total_count = len(all_matches)
            
            if not all_matches:
                return f"No files matching '{pattern}' found in '{path}'"
            
            # Apply limit
            truncated = False
            if max_results is not None and total_count > max_results:
                matches = sorted(all_matches)[:max_results]
                truncated = True
            else:
                matches = sorted(all_matches)
            
            # Format results with directory prefixes for multi-directory configs
            allowed_dirs = self._get_all_allowed_directories()
            has_multiple_dirs = len(allowed_dirs) > 1
            results = []
            search_dir_name = None
            
            for match in matches:
                if has_multiple_dirs:
                    rel_path_str, dir_name = self._get_relative_path_from_allowed_dirs(match)
                    display_path = f"{dir_name}/{rel_path_str}"
                    if search_dir_name is None:
                        search_dir_name = dir_name
                else:
                    rel_path_str = str(match.relative_to(Path(self.base_directory).resolve()))
                    display_path = rel_path_str
                
                if match.is_dir():
                    results.append(f"📁 {display_path}/")
                else:
                    size = self._format_size(match.stat().st_size)
                    results.append(f"📄 {display_path} ({size})")
            
            header = f"Found {total_count} matches for '{pattern}':\n\n"
            output = header + "\n".join(results)
            
            if truncated:
                location_str = f"from '{search_dir_name}' " if search_dir_name else ""
                output += f"\n\n⚠️  OUTPUT TRUNCATED: Showing {max_results} of {total_count} results {location_str}(max_results={max_results})"
                output += "\n   To see more: increase max_results or use a more specific pattern"
            
            return output
        except Exception as e:
            return f"Error searching files in '{path}': {str(e)}"


class DeleteFileTool(FileSystemTool):
    """Delete a file."""
    name: str = "filesystem_delete_file"
    description: str = (
        "Delete a file. Use with caution as this operation cannot be undone. "
        "Only deletes files, not directories. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = DeleteFileInput
    
    def _run(self, path: str) -> str:
        """Delete a file."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: File '{path}' does not exist"
            
            if not target.is_file():
                return f"Error: '{path}' is not a file (directories cannot be deleted with this tool)"
            
            size = target.stat().st_size
            target.unlink()
            
            return f"Successfully deleted '{path}' ({self._format_size(size)})"
        except Exception as e:
            return f"Error deleting file '{path}': {str(e)}"


class MoveFileTool(FileSystemTool):
    """Move or rename files and directories."""
    name: str = "filesystem_move_file"
    description: str = (
        "Move or rename files and directories. Can move files between directories and rename them in a single operation. "
        "If the destination exists, the operation will fail. "
        "Works across different directories and can be used for simple renaming within the same directory. "
        "Both source and destination must be within allowed directories."
    )
    args_schema: type[BaseModel] = MoveFileInput
    
    def _run(self, source: str, destination: str) -> str:
        """Move or rename a file."""
        try:
            source_path = self._resolve_path(source)
            dest_path = self._resolve_path(destination)
            
            if not source_path.exists():
                return f"Error: Source '{source}' does not exist"
            
            if dest_path.exists():
                return f"Error: Destination '{destination}' already exists"
            
            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            source_path.rename(dest_path)
            
            return f"Successfully moved '{source}' to '{destination}'"
        except Exception as e:
            return f"Error moving '{source}' to '{destination}': {str(e)}"


class CreateDirectoryTool(FileSystemTool):
    """Create a directory."""
    name: str = "filesystem_create_directory"
    description: str = (
        "Create a new directory or ensure a directory exists. "
        "Can create multiple nested directories in one operation. "
        "If the directory already exists, this operation will succeed silently. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = CreateDirectoryInput
    
    def _run(self, path: str) -> str:
        """Create a directory."""
        try:
            target = self._resolve_path(path)
            
            if target.exists():
                if target.is_dir():
                    return f"Directory '{path}' already exists"
                else:
                    return f"Error: '{path}' exists but is not a directory"
            
            target.mkdir(parents=True, exist_ok=True)
            
            return f"Successfully created directory '{path}'"
        except Exception as e:
            return f"Error creating directory '{path}': {str(e)}"


class GetFileInfoTool(FileSystemTool):
    """Get detailed file/directory information."""
    name: str = "filesystem_get_file_info"
    description: str = (
        "Retrieve detailed metadata about a file or directory. "
        "Returns comprehensive information including size, creation time, last modified time, permissions, and type. "
        "This tool is perfect for understanding file characteristics without reading the actual content. "
        "Only works within allowed directories."
    )
    args_schema: type[BaseModel] = GetFileInfoInput
    
    def _run(self, path: str) -> str:
        """Get file information."""
        try:
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"Error: Path '{path}' does not exist"
            
            stat = target.stat()
            
            info = {
                "Path": str(path),
                "Type": "Directory" if target.is_dir() else "File",
                "Size": self._format_size(stat.st_size) if target.is_file() else "N/A",
                "Created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "Modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "Accessed": datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S"),
                "Permissions": oct(stat.st_mode)[-3:],
            }
            
            if target.is_file():
                info["Readable"] = os.access(target, os.R_OK)
                info["Writable"] = os.access(target, os.W_OK)
                info["Executable"] = os.access(target, os.X_OK)
            
            return "\n".join(f"{key}: {value}" for key, value in info.items())
        except Exception as e:
            return f"Error getting info for '{path}': {str(e)}"


class ListAllowedDirectoriesTool(FileSystemTool):
    """List allowed directories."""
    name: str = "filesystem_list_allowed_directories"
    description: str = (
        "Returns the list of directories that are accessible. "
        "Subdirectories within allowed directories are also accessible. "
        "Use this to understand which directories and their nested paths are available before trying to access files."
    )
    args_schema: type[BaseModel] = EmptyInput
    
    def _run(self) -> str:
        """List allowed directories."""
        dirs = self._get_all_allowed_directories()
        if len(dirs) == 1:
            return f"Allowed directory:\n{dirs[0]}\n\nAll subdirectories within this path are accessible."
        else:
            dir_list = "\n".join(f"  - {d}" for d in dirs)
            return f"Allowed directories:\n{dir_list}\n\nAll subdirectories within these paths are accessible."


# ========== Filesystem API Wrapper for Inventory Ingestion ==========

class FilesystemApiWrapper:
    """
    API Wrapper for filesystem operations compatible with inventory ingestion pipeline.
    
    Supports both text and non-text files:
    - Text files: .py, .md, .txt, .json, .yaml, etc.
    - Documents: .pdf, .docx, .pptx, .xlsx, .xls (converted to markdown)
    - Images: .png, .jpg, .gif, .webp (base64 encoded or described via LLM)
    
    Usage:
        # Create wrapper for a directory
        wrapper = FilesystemApiWrapper(base_directory="/path/to/docs")
        
        # Load documents (uses inherited loader())
        for doc in wrapper.loader(whitelist=["*.md", "*.pdf"]):
            print(doc.page_content[:100])
        
        # For image description, provide an LLM
        wrapper = FilesystemApiWrapper(base_directory="/path/to/docs", llm=my_llm)
        for doc in wrapper.loader(whitelist=["*.png"]):
            print(doc.page_content)  # LLM-generated description
        
        # Use with inventory ingestion
        pipeline = IngestionPipeline(llm=llm, graph_path="./graph.json")
        pipeline.register_toolkit("local_docs", wrapper)
        result = pipeline.run(source="local_docs", whitelist=["*.md", "*.pdf"])
    """
    
    # Filesystem-specific settings
    base_directory: str = ""
    recursive: bool = True
    follow_symlinks: bool = False
    llm: Any = None  # Optional LLM for image processing
    
    # File type categories
    BINARY_EXTENSIONS = {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls'}
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
    
    def __init__(
        self,
        base_directory: str,
        recursive: bool = True,
        follow_symlinks: bool = False,
        llm: Any = None,
        **kwargs
    ):
        """
        Initialize filesystem wrapper.
        
        Args:
            base_directory: Root directory for file operations
            recursive: If True, search subdirectories recursively
            follow_symlinks: If True, follow symbolic links
            llm: Optional LLM for image description (if not provided, images are base64 encoded)
            **kwargs: Additional arguments (ignored, for compatibility)
        """
        self.base_directory = str(Path(base_directory).resolve())
        self.recursive = recursive
        self.follow_symlinks = follow_symlinks
        self.llm = llm
        
        # For compatibility with BaseCodeToolApiWrapper.loader()
        self.active_branch = None
        
        # Validate directory
        if not Path(self.base_directory).exists():
            raise ValueError(f"Directory does not exist: {self.base_directory}")
        if not Path(self.base_directory).is_dir():
            raise ValueError(f"Path is not a directory: {self.base_directory}")
        
        # Optional RunnableConfig for CLI/standalone usage
        self._runnable_config = None
    
    def set_runnable_config(self, config: Optional[Dict[str, Any]]) -> None:
        """
        Set the RunnableConfig for dispatching custom events.
        
        This is required when running outside of a LangChain agent context
        (e.g., from CLI). Without a config containing a run_id, 
        dispatch_custom_event will fail with "Unable to dispatch an adhoc event 
        without a parent run id".
        
        Args:
            config: A RunnableConfig dict with at least {'run_id': uuid}
        """
        self._runnable_config = config
    
    def _log_tool_event(self, message: str, tool_name: str = None, config: Optional[Dict[str, Any]] = None):
        """Log progress events (mirrors BaseToolApiWrapper).
        
        Args:
            message: The message to log
            tool_name: Name of the tool (defaults to 'filesystem')
            config: Optional RunnableConfig. If not provided, uses self._runnable_config.
                   Required when running outside a LangChain agent context.
        """
        logger.info(f"[{tool_name or 'filesystem'}] {message}")
        try:
            from langchain_core.callbacks import dispatch_custom_event
            
            # Use provided config, fall back to instance config
            effective_config = config or getattr(self, '_runnable_config', None)
            
            dispatch_custom_event(
                name="thinking_step",
                data={
                    "message": message,
                    "tool_name": tool_name or "filesystem",
                    "toolkit": "FilesystemApiWrapper",
                },
                config=effective_config,
            )
        except Exception:
            pass
    
    def _get_files(self, path: str = "", branch: str = None) -> List[str]:
        """
        Get list of files in the directory.
        
        Implements BaseCodeToolApiWrapper._get_files() for filesystem.
        
        Args:
            path: Subdirectory path (relative to base_directory)
            branch: Ignored for filesystem (compatibility with git-based toolkits)
            
        Returns:
            List of file paths relative to base_directory
        """
        base = Path(self.base_directory)
        search_path = base / path if path else base
        
        if not search_path.exists():
            return []
        
        files = []
        
        if self.recursive:
            for root, dirs, filenames in os.walk(search_path, followlinks=self.follow_symlinks):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in filenames:
                    if filename.startswith('.'):
                        continue
                    
                    full_path = Path(root) / filename
                    try:
                        rel_path = str(full_path.relative_to(base))
                        files.append(rel_path)
                    except ValueError:
                        continue
        else:
            for entry in search_path.iterdir():
                if entry.is_file() and not entry.name.startswith('.'):
                    try:
                        rel_path = str(entry.relative_to(base))
                        files.append(rel_path)
                    except ValueError:
                        continue
        
        return sorted(files)
    
    def _is_binary_file(self, file_path: str) -> bool:
        """Check if file is a binary document (PDF, DOCX, etc.)."""
        ext = Path(file_path).suffix.lower()
        return ext in self.BINARY_EXTENSIONS
    
    def _is_image_file(self, file_path: str) -> bool:
        """Check if file is an image."""
        ext = Path(file_path).suffix.lower()
        return ext in self.IMAGE_EXTENSIONS
    
    def _read_binary_file(self, file_path: str) -> Optional[str]:
        """
        Read binary file (PDF, DOCX, PPTX, Excel) and convert to text/markdown.
        
        Uses the SDK's content_parser for document conversion.
        
        Args:
            file_path: Path relative to base_directory
            
        Returns:
            Converted text content, or None if conversion fails
        """
        full_path = Path(self.base_directory) / file_path
        
        try:
            from alita_sdk.tools.utils.content_parser import parse_file_content
            
            result = parse_file_content(
                file_path=str(full_path),
                is_capture_image=bool(self.llm),  # Capture images if LLM available
                llm=self.llm
            )
            
            if isinstance(result, Exception):
                logger.warning(f"Failed to parse {file_path}: {result}")
                return None
            
            return result
            
        except ImportError:
            logger.warning("content_parser not available, skipping binary file")
            return None
        except Exception as e:
            logger.warning(f"Error parsing {file_path}: {e}")
            return None
    
    def _read_image_file(self, file_path: str) -> Optional[str]:
        """
        Read image file and convert to text representation.
        
        If LLM is available, uses it to describe the image.
        Otherwise, returns base64-encoded data URI.
        
        Args:
            file_path: Path relative to base_directory
            
        Returns:
            Image description or base64 data URI
        """
        full_path = Path(self.base_directory) / file_path
        
        if not full_path.exists():
            return None
        
        ext = full_path.suffix.lower()
        
        try:
            # Read image bytes
            image_bytes = full_path.read_bytes()
            
            if self.llm:
                # Use content_parser with LLM for image description
                try:
                    from alita_sdk.tools.utils.content_parser import parse_file_content
                    
                    result = parse_file_content(
                        file_path=str(full_path),
                        is_capture_image=True,
                        llm=self.llm
                    )
                    
                    if isinstance(result, Exception):
                        logger.warning(f"Failed to describe image {file_path}: {result}")
                    else:
                        return f"[Image: {Path(file_path).name}]\n\n{result}"
                        
                except ImportError:
                    pass
            
            # Fallback: return base64 data URI
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp',
                '.svg': 'image/svg+xml',
            }
            mime_type = mime_types.get(ext, 'application/octet-stream')
            b64_data = base64.b64encode(image_bytes).decode('utf-8')
            
            return f"[Image: {Path(file_path).name}]\ndata:{mime_type};base64,{b64_data}"
            
        except Exception as e:
            logger.warning(f"Error reading image {file_path}: {e}")
            return None
    
    def _read_file(
        self,
        file_path: str,
        branch: str = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        head: Optional[int] = None,
        tail: Optional[int] = None,
    ) -> Optional[str]:
        """
        Read file content, handling text, binary documents, and images.
        
        Supports:
        - Text files: Read directly with encoding detection
        - Binary documents (PDF, DOCX, PPTX, Excel): Convert to markdown
        - Images: Return LLM description or base64 data URI
        
        Args:
            file_path: Path relative to base_directory
            branch: Ignored for filesystem (compatibility with git-based toolkits)
            offset: Start line number (1-indexed). If None, start from beginning.
            limit: Maximum number of lines to read. If None, read to end.
            head: Read only first N lines (alternative to offset/limit)
            tail: Read only last N lines (alternative to offset/limit)
            
        Returns:
            File content as string, or None if unreadable
        """
        full_path = Path(self.base_directory) / file_path
        
        # Security check - prevent path traversal
        try:
            full_path.resolve().relative_to(Path(self.base_directory).resolve())
        except ValueError:
            logger.warning(f"Access denied: {file_path} is outside base directory")
            return None
        
        if not full_path.exists() or not full_path.is_file():
            return None
        
        # Route to appropriate reader based on file type
        # Note: offset/limit only apply to text files
        if self._is_binary_file(file_path):
            return self._read_binary_file(file_path)
        
        if self._is_image_file(file_path):
            return self._read_image_file(file_path)
        
        # Default: read as text with encoding detection
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                content = full_path.read_text(encoding=encoding)
                
                # Apply line filtering if specified
                if offset is not None or limit is not None or head is not None or tail is not None:
                    lines = content.splitlines(keepends=True)
                    
                    if head is not None:
                        # Read first N lines
                        lines = lines[:head]
                    elif tail is not None:
                        # Read last N lines
                        lines = lines[-tail:] if tail > 0 else []
                    else:
                        # Use offset/limit
                        start_idx = (offset - 1) if offset and offset > 0 else 0
                        if limit is not None:
                            end_idx = start_idx + limit
                            lines = lines[start_idx:end_idx]
                        else:
                            lines = lines[start_idx:]
                    
                    content = ''.join(lines)
                
                return content
                
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
                return None
        
        logger.warning(f"Could not decode {file_path} with any known encoding")
        return None
    
    def read_file(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        head: Optional[int] = None,
        tail: Optional[int] = None,
    ) -> Optional[str]:
        """
        Public method to read file content with optional line range.
        
        Args:
            file_path: Path relative to base_directory
            offset: Start line number (1-indexed)
            limit: Maximum number of lines to read
            head: Read only first N lines
            tail: Read only last N lines
            
        Returns:
            File content as string
        """
        return self._read_file(file_path, offset=offset, limit=limit, head=head, tail=tail)
    
    def loader(
        self,
        branch: Optional[str] = None,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
        chunked: bool = True,
    ) -> Generator[Document, None, None]:
        """
        Load documents from the filesystem.
        
        Mirrors BaseCodeToolApiWrapper.loader() interface for compatibility.
        
        Args:
            branch: Ignored (kept for API compatibility with git-based loaders)
            whitelist: File patterns to include (e.g., ['*.py', 'src/**/*.js'])
            blacklist: File patterns to exclude (e.g., ['*test*', 'node_modules/**'])
            chunked: If True, applies universal chunker based on file type
        
        Yields:
            Document objects with page_content and metadata
        """
        import glob as glob_module
        
        base = Path(self.base_directory)
        
        def is_blacklisted(file_path: str) -> bool:
            if not blacklist:
                return False
            return (
                any(fnmatch.fnmatch(file_path, p) for p in blacklist) or
                any(fnmatch.fnmatch(Path(file_path).name, p) for p in blacklist)
            )
        
        # Optimization: Use glob directly when whitelist has path patterns
        # This avoids scanning 100K+ files in node_modules etc.
        def get_files_via_glob() -> Generator[str, None, None]:
            """Use glob patterns directly - much faster than scanning all files."""
            seen = set()
            for pattern in whitelist:
                # Handle glob patterns
                full_pattern = str(base / pattern)
                for match in glob_module.glob(full_pattern, recursive=True):
                    match_path = Path(match)
                    if match_path.is_file():
                        try:
                            rel_path = str(match_path.relative_to(base))
                            if rel_path not in seen and not is_blacklisted(rel_path):
                                seen.add(rel_path)
                                yield rel_path
                        except ValueError:
                            continue
        
        def get_files_via_scan() -> Generator[str, None, None]:
            """Fall back to scanning all files when no whitelist or simple extension patterns."""
            _files = self._get_files()
            self._log_tool_event(f"Found {len(_files)} files in {self.base_directory}", "loader")
            
            def is_whitelisted(file_path: str) -> bool:
                if not whitelist:
                    return True
                return (
                    any(fnmatch.fnmatch(file_path, p) for p in whitelist) or
                    any(fnmatch.fnmatch(Path(file_path).name, p) for p in whitelist) or
                    any(file_path.endswith(f'.{p.lstrip("*.")}') for p in whitelist if p.startswith('*.'))
                )
            
            for file_path in _files:
                if is_whitelisted(file_path) and not is_blacklisted(file_path):
                    yield file_path
        
        # Decide strategy: use glob if whitelist has path patterns (contains / or **)
        use_glob = whitelist and any('/' in p or '**' in p for p in whitelist)
        
        if use_glob:
            self._log_tool_event(f"Using glob patterns: {whitelist}", "loader")
            file_iterator = get_files_via_glob()
        else:
            file_iterator = get_files_via_scan()
        
        def raw_document_generator() -> Generator[Document, None, None]:
            self._log_tool_event("Reading files...", "loader")
            processed = 0
            
            for file_path in file_iterator:
                content = self._read_file(file_path)
                if not content:
                    continue
                
                content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                processed += 1
                
                yield Document(
                    page_content=content,
                    metadata={
                        'file_path': file_path,
                        'file_name': Path(file_path).name,
                        'source': file_path,
                        'commit_hash': content_hash,
                    }
                )
                
                # Log progress every 100 files
                if processed % 100 == 0:
                    logger.debug(f"[loader] Read {processed} files...")
            
            self._log_tool_event(f"Loaded {processed} files", "loader")
        
        if not chunked:
            return raw_document_generator()
        
        try:
            from alita_sdk.tools.chunkers.universal_chunker import universal_chunker
            return universal_chunker(raw_document_generator())
        except ImportError:
            logger.warning("Universal chunker not available, returning raw documents")
            return raw_document_generator()
    
    def chunker(self, documents: Generator[Document, None, None]) -> Generator[Document, None, None]:
        """Apply universal chunker to documents."""
        try:
            from alita_sdk.tools.chunkers.universal_chunker import universal_chunker
            return universal_chunker(documents)
        except ImportError:
            return documents
    
    def get_files_content(self, file_path: str) -> Optional[str]:
        """Get file content (compatibility alias for retrieval toolkit)."""
        return self._read_file(file_path)


# Predefined tool presets for common use cases
FILESYSTEM_TOOL_PRESETS = {
    'read_only': {
        'exclude_tools': [
            'filesystem_write_file',
            'filesystem_append_file',
            'filesystem_edit_file',
            'filesystem_apply_patch',
            'filesystem_delete_file',
            'filesystem_move_file',
            'filesystem_create_directory',
        ]
    },
    'no_delete': {
        'exclude_tools': ['filesystem_delete_file']
    },
    'basic': {
        'include_tools': [
            'filesystem_read_file',
            'filesystem_write_file',
            'filesystem_append_file',
            'filesystem_list_directory',
            'filesystem_create_directory',
        ]
    },
    'minimal': {
        'include_tools': [
            'filesystem_read_file',
            'filesystem_list_directory',
        ]
    },
}


def get_filesystem_tools(
    base_directory: str,
    include_tools: Optional[List[str]] = None,
    exclude_tools: Optional[List[str]] = None,
    preset: Optional[str] = None,
    allowed_directories: Optional[List[str]] = None
) -> List[BaseTool]:
    """
    Get filesystem tools for the specified directories.
    
    Args:
        base_directory: Absolute or relative path to the primary directory to restrict access to
        include_tools: Optional list of tool names to include. If provided, only these tools are returned.
                      If None, all tools are included (unless excluded).
        exclude_tools: Optional list of tool names to exclude. Applied after include_tools.
        preset: Optional preset name to use predefined tool sets. Presets:
                - 'read_only': Excludes all write/modify operations
                - 'no_delete': All tools except delete
                - 'basic': Read, write, append, list, create directory
                - 'minimal': Only read and list
                Note: If preset is used with include_tools or exclude_tools, 
                      preset is applied first, then custom filters.
        
    Returns:
        List of filesystem tools based on preset and/or include/exclude filters
        
    Available tool names:
        - filesystem_read_file
        - filesystem_read_file_chunk
        - filesystem_read_multiple_files
        - filesystem_write_file
        - filesystem_append_file (for incremental file creation)
        - filesystem_edit_file
        - filesystem_apply_patch
        - filesystem_list_directory
        - filesystem_directory_tree
        - filesystem_search_files
        - filesystem_delete_file
        - filesystem_move_file
        - filesystem_create_directory
        - filesystem_get_file_info
        - filesystem_list_allowed_directories
        
    Examples:
        # Get all tools
        get_filesystem_tools('/path/to/dir')
        
        # Only read operations
        get_filesystem_tools('/path/to/dir', 
                           include_tools=['filesystem_read_file', 'filesystem_list_directory'])
        
        # All tools except delete and write
        get_filesystem_tools('/path/to/dir', 
                           exclude_tools=['filesystem_delete_file', 'filesystem_write_file'])
        
        # Use preset for read-only mode
        get_filesystem_tools('/path/to/dir', preset='read_only')
        
        # Use preset and add custom exclusions
        get_filesystem_tools('/path/to/dir', preset='read_only', 
                           exclude_tools=['filesystem_search_files'])
        
        # Multiple allowed directories
        get_filesystem_tools('/path/to/primary', 
                           allowed_directories=['/path/to/other1', '/path/to/other2'])
    """
    # Apply preset if specified
    preset_include = None
    preset_exclude = None
    if preset:
        if preset not in FILESYSTEM_TOOL_PRESETS:
            raise ValueError(f"Unknown preset '{preset}'. Available: {list(FILESYSTEM_TOOL_PRESETS.keys())}")
        preset_config = FILESYSTEM_TOOL_PRESETS[preset]
        preset_include = preset_config.get('include_tools')
        preset_exclude = preset_config.get('exclude_tools')
    
    # Merge preset with custom filters
    # Priority: custom include_tools > preset include > all tools
    final_include = include_tools if include_tools is not None else preset_include
    
    # Priority: custom exclude_tools + preset exclude
    final_exclude = []
    if preset_exclude:
        final_exclude.extend(preset_exclude)
    if exclude_tools:
        final_exclude.extend(exclude_tools)
    final_exclude = list(set(final_exclude)) if final_exclude else None
    
    # Resolve to absolute paths
    base_dir = str(Path(base_directory).resolve())
    extra_dirs = [str(Path(d).resolve()) for d in (allowed_directories or [])]
    
    # Define all available tools with their names
    all_tools = {
        'filesystem_read_file': ReadFileTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_read_file_chunk': ReadFileChunkTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_read_multiple_files': ReadMultipleFilesTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_write_file': WriteFileTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_append_file': AppendFileTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_edit_file': EditFileTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_apply_patch': ApplyPatchTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_list_directory': ListDirectoryTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_directory_tree': DirectoryTreeTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_search_files': SearchFilesTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_delete_file': DeleteFileTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_move_file': MoveFileTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_create_directory': CreateDirectoryTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_get_file_info': GetFileInfoTool(base_directory=base_dir, allowed_directories=extra_dirs),
        'filesystem_list_allowed_directories': ListAllowedDirectoriesTool(base_directory=base_dir, allowed_directories=extra_dirs),
    }
    
    # Start with all tools or only included ones
    if final_include is not None:
        selected_tools = {name: tool for name, tool in all_tools.items() if name in final_include}
    else:
        selected_tools = all_tools.copy()
    
    # Remove excluded tools
    if final_exclude is not None:
        for name in final_exclude:
            selected_tools.pop(name, None)
    
    return list(selected_tools.values())
