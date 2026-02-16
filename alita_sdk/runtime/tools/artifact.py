import hashlib
import io
import json
import logging
import re
from typing import Any, Optional, Generator, List

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.documents import Document
from langchain_core.tools import ToolException
from openpyxl.workbook.workbook import Workbook
from pydantic import create_model, Field, model_validator

from ...tools.non_code_indexer_toolkit import NonCodeIndexerToolkit
from ...tools.utils.available_tools_decorator import extend_with_parent_available_tools
from ...tools.elitea_base import extend_with_file_operations, BaseCodeToolApiWrapper
from ...tools.utils.text_operations import (
    apply_line_slice,
    is_text_editable,
    parse_filepath,
    parse_old_new_markers,
    search_in_content,
    try_apply_edit,
)
from ...runtime.utils.utils import IndexerKeywords

DEFAULT_MAX_SINGLE_READ_SIZE = 60000


class ArtifactWrapper(NonCodeIndexerToolkit):
    bucket: str
    max_single_read_size: int = DEFAULT_MAX_SINGLE_READ_SIZE
    artifact: Optional[Any] = None

    def read_multiple_files(
        self,
        file_paths: List[str],
        bucket_name: str = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> dict:
        """
        Read multiple files in batch from an artifact bucket.

        Args:
            file_paths: List of file paths to read (can be full paths like /bucket/file.txt or relative like folder/file.txt)
            bucket_name: Bucket name. If not provided, uses toolkit-configured default bucket.
            offset: Starting line number for all files (1-indexed)
            limit: Number of lines to read from offset for all files

        Returns:
            Dict mapping file paths to their content
        """
        results = {}

        # Convert offset/limit to start_line/end_line for read_file
        start_line = offset
        end_line = (offset + limit - 1) if (offset is not None and limit is not None) else None

        for path in file_paths:
            try:
                if path.startswith('/'):
                    content = self.read_file(filepath=path, bucket_name=bucket_name,
                                            start_line=start_line, end_line=end_line)
                else:
                    content = self.read_file(filename=path, bucket_name=bucket_name,
                                            start_line=start_line, end_line=end_line)
                results[path] = content
            except Exception as e:
                results[path] = f"Error reading file: {str(e)}"
        return results

    def search_file(
        self,
        file_path: str,
        pattern: str,
        bucket_name: str = None,
        is_regex: bool = True,
        context_lines: int = 2
    ) -> str:
        """
        Search for a pattern in a file from an artifact bucket.

        Args:
            file_path: Path to the file to search
            pattern: Search pattern. Treated as regex by default unless is_regex=False.
            bucket_name: Bucket name. If not provided, uses toolkit-configured default bucket.
            is_regex: Whether pattern is a regex. Default is True for flexible matching.
            context_lines: Number of lines before/after match to include for context

        Returns:
            Formatted string with match results and context
        """
        content = self._read_file(file_path, branch=None, bucket_name=bucket_name)
        matches = search_in_content(content, pattern, is_regex=is_regex, context_lines=context_lines)

        if not matches:
            return f"No matches found for pattern '{pattern}' in {file_path}"

        # Format results
        results = [f"Found {len(matches)} match(es) in {file_path}:\n"]
        for match in matches:
            results.append(f"\n--- Line {match['line_number']} ---")
            if match['context_before']:
                results.append("\n".join(f"  {l}" for l in match['context_before']))
            results.append(f"> {match['line_content']}")
            if match['context_after']:
                results.append("\n".join(f"  {l}" for l in match['context_after']))

        return "\n".join(results)

    def edit_file(
        self,
        file_path: str,
        file_query: str,
        bucket_name: str = None,
        commit_message: str = None
    ) -> str:
        """
        Edit a file in an artifact bucket using OLD/NEW markers.

        Args:
            file_path: Path to the file to edit. Must be a text file.
            file_query: Edit instructions with OLD/NEW markers.
            bucket_name: Bucket name. If not provided, uses toolkit-configured default bucket.
            commit_message: Not used for artifacts (kept for API consistency)

        Returns:
            Success message or error description
        """
        # Validate file type
        if not is_text_editable(file_path):
            raise ToolException(f"File '{file_path}' is not a text-editable file type")

        # Read current content
        content = self._read_file(file_path, branch=None, bucket_name=bucket_name)

        # Parse edit instructions
        edits = parse_old_new_markers(file_query)
        if not edits:
            raise ToolException(
                "No valid OLD/NEW marker pairs found in edit instructions. "
                "Markers must be on their own dedicated line."
            )

        # Apply edits
        updated_content = content
        applied_count = 0
        for old_text, new_text in edits:
            updated_content, used_fallback = try_apply_edit(updated_content, old_text, new_text, file_path)
            if updated_content != content or used_fallback:
                applied_count += 1
                content = updated_content

        if applied_count == 0:
            return f"No edits were applied to {file_path}. The OLD blocks may not match the file content."

        # Write updated content
        self._write_file(file_path, updated_content, branch=None, commit_message=commit_message, bucket_name=bucket_name)

        return f"Successfully applied {applied_count} edit(s) to {file_path}"

    def _get_file_operation_schemas(self):
        """
        Returns custom schemas for file operations that use bucket_name instead of branch.

        This method is called by the @extend_with_file_operations decorator to get
        toolkit-specific schemas for file operation tools.
        """
        # Artifact-specific schemas with bucket_name instead of branch
        ArtifactReadMultipleFilesInput = create_model(
            "ArtifactReadMultipleFilesInput",
            file_paths=(List[str], Field(description="List of file paths to read", min_length=1)),
            bucket_name=(Optional[str], Field(
                description="Bucket name. If not provided, uses toolkit-configured default bucket.",
                default=None
            )),
            offset=(Optional[int], Field(
                description="Starting line number for all files (1-indexed)",
                default=None,
                ge=1
            )),
            limit=(Optional[int], Field(
                description="Number of lines to read from offset for all files",
                default=None,
                ge=1
            )),
        )

        ArtifactSearchFileInput = create_model(
            "ArtifactSearchFileInput",
            file_path=(str, Field(description="Path to the file to search")),
            pattern=(str, Field(description="Search pattern. Treated as regex by default unless is_regex=False.")),
            bucket_name=(Optional[str], Field(
                description="Bucket name. If not provided, uses toolkit-configured default bucket.",
                default=None
            )),
            is_regex=(bool, Field(
                description="Whether pattern is a regex. Default is True for flexible matching.",
                default=True
            )),
            context_lines=(int, Field(
                description="Number of lines before/after match to include for context",
                default=2,
                ge=0
            )),
        )

        ArtifactEditFileInput = create_model(
            "ArtifactEditFileInput",
            file_path=(str, Field(
                description="Path to the file to edit. Must be a text file (markdown, txt, csv, json, xml, html, yaml, etc.)"
            )),
            file_query=(str, Field(description="""Edit instructions with OLD/NEW markers. Format:
OLD <<<<
old content to replace
>>>> OLD
NEW <<<<
new content
>>>> NEW

Multiple OLD/NEW pairs can be provided for multiple edits.""")),
            bucket_name=(Optional[str], Field(
                description="Bucket name. If not provided, uses toolkit-configured default bucket.",
                default=None
            )),
            commit_message=(Optional[str], Field(
                description="Not used for artifacts (kept for API consistency)",
                default=None
            )),
        )

        return {
            "read_multiple_files": ArtifactReadMultipleFilesInput,
            "search_file": ArtifactSearchFileInput,
            "edit_file": ArtifactEditFileInput,
        }

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        if not values.get('alita'):
            raise ValueError("Client is required.")
        if not values.get('bucket'):
            raise ValueError("Bucket is required.")
        values["artifact"] = values['alita'].artifact(values['bucket'])
        return super().validate_toolkit(values)

    def list_files(self, bucket_name = None, folder: str = None, recursive: bool = False, return_as_string = True):
        """List files in the artifact bucket with S3 download links.
        
        Args:
            bucket_name: Bucket name (uses default if None)
            folder: Folder/prefix to scope the listing (e.g., conversation_id for attachments)
            recursive: If True, returns all files under prefix recursively.
                      If False (default), lists only immediate children (files and subfolders).
            return_as_string: If True, returns str(result), else returns dict
        
        Returns:
            Dict with 'total' and 'rows', or empty list if folder doesn't exist.
        """
        from urllib.parse import quote
        
        bucket = bucket_name or self.bucket
        base_url = getattr(self.alita, 'base_url', '').rstrip('/')
        project_id = getattr(self.alita, 'project_id', '')
        
        # Build prefix for folder scoping
        prefix = ''
        if folder:
            prefix = folder.strip('/') + '/'
        
        # delimiter='/' for folder listing, None for recursive listing
        delimiter = None if recursive else '/'
        result = self.artifact.list(bucket_name=bucket, prefix=prefix, delimiter=delimiter)
        
        if 'error' in result:
            # Return empty list for non-existent folder/bucket
            return "[]" if return_as_string else {"total": 0, "rows": []}
        
        # Add S3 download links to files (not folders)
        for file_info in result.get('rows', []):
            if file_info.get('type') == 'file':
                # Use full key for S3 download link
                full_key = file_info.get('key', prefix + file_info['name'])
                # S3 GET URL format: /s3/{bucket}/{key}?project_id={project_id}
                encoded_key = quote(full_key, safe='/')
                file_info['link'] = f"{base_url}/s3/{bucket}/{encoded_key}?project_id={project_id}"
            elif file_info.get('type') == 'folder':
                # Folders don't have download links
                pass
            # Remove internal 'key' field from response (keep it clean)
            file_info.pop('key', None)
        
        return str(result) if return_as_string else result

    def create_file(self, filename: str, bucket_name = None, filedata: str = None, filepath: str = None):
        """Create a file in the artifact bucket from new content or by copying an existing file.

        Args:
            filename: Target filename in destination bucket
            bucket_name: Destination bucket (uses default if None)
            filedata: Content for creating new files (text, JSON, CSV, etc.)
            filepath: Path of existing file to copy (/{bucket}/{filename} format, preserves binary)

        Note: Provide EITHER filedata OR filepath, not both or neither.
        """
        # Validation: exactly one source must be provided
        if filedata is None and filepath is None:
            raise ToolException(
                "Must provide either 'filedata' (to create new content) or 'filepath' (to copy existing file). "
                "Both parameters cannot be empty."
            )

        if filedata is not None and filepath is not None:
            raise ToolException(
                "Cannot provide both 'filedata' and 'filepath'. "
                "Use 'filepath' to copy existing files preserving binary format, "
                "or 'filedata' to create new content from text/data."
            )

        target_bucket = bucket_name or self.bucket

        # Normalize filename path
        full_key = filename.lstrip('/')

        # Determine operation type and get file content
        if filepath:
            # Copy mode: get raw bytes from existing file
            operation_type = "copy"
            try:
                file_bytes, _ = self.artifact.get_raw_content_by_filepath(filepath)
                filedata = file_bytes
            except Exception as e:
                raise ToolException(f"Failed to retrieve file '{filepath}': {str(e)}")
            source_filepath = filepath
        else:
            # Create mode: use provided content
            operation_type = "create"
            if filename.endswith(".xlsx"):
                data = json.loads(filedata)
                filedata = self.create_xlsx_filedata(data)
            source_filepath = None

        target_bucket = bucket_name or self.bucket

        result = self.artifact.create(full_key, filedata, target_bucket)
        if 'error' in result:
            raise ToolException(f"Failed to create file '{filename}': {result['error']}")
        
        # Get sanitized info from client response
        new_filepath = result['filepath']
        sanitized_filename = result.get('sanitized_name', filename)

        file_size = len(filedata) if isinstance(filedata, (str, bytes)) else 0

        # Build event metadata
        event_meta = {
            "bucket": target_bucket,
            "file_size": file_size,
            "source": "generated"
        }
        if source_filepath:
            event_meta["source_filepath"] = source_filepath
            event_meta["operation"] = "copy"

        dispatch_custom_event("file_modified", {
            "message": f"File '{filename}' {'copied' if operation_type == 'copy' else 'created'} successfully",
            "filepath": new_filepath,
            "tool_name": "createFile",
            "toolkit": "artifact",
            "operation_type": operation_type,
            "meta": event_meta
        })

        return json.dumps({
            "filepath": new_filepath,
            "filename": sanitized_filename,
            "bucket": target_bucket,
            "message": f"File '{filename}' {'copied' if operation_type == 'copy' else 'created'} successfully"
        })

    def create_xlsx_filedata(self, data: dict[str, list[list]]) -> bytes:
        try:
            workbook = Workbook()

            first_sheet = True
            for sheet_name, sheet_data in data.items():
                if first_sheet:
                    sheet = workbook.active
                    sheet.title = sheet_name
                    first_sheet = False
                else:
                    sheet = workbook.create_sheet(title=sheet_name)

                for row in sheet_data:
                    sheet.append(row)

            file_buffer = io.BytesIO()
            workbook.save(file_buffer)
            file_buffer.seek(0)

            return file_buffer.read()

        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for .xlsx file data.")
        except Exception as e:
            raise ValueError(f"Error processing .xlsx file data: {e}")


    def read_file(self,
                  filename: str = None,
                  bucket_name = None,
                  is_capture_image: bool = False,
                  page_number: int = None,
                  sheet_name: str = None,
                  excel_by_sheets: bool = False,
                  filepath: str = None,
                  start_line: int = None,
                  end_line: int = None):
        """
        Read a file from the artifact bucket.
        
        Supports two ways to specify the file:
        1. filename + bucket_name: Traditional approach
        2. filepath: Full path in /{bucket}/{filename} format (extracts bucket and filename automatically)
        
        For large text files, use start_line/end_line to read specific portions.
        
        Args:
            filename: Name of the file (required if filepath not provided)
            bucket_name: Bucket name (uses default if None, ignored if filepath provided)
            is_capture_image: Whether to capture images in documents
            page_number: Specific page to read (for PDFs)
            sheet_name: Specific sheet to read (for Excel)
            excel_by_sheets: Read Excel by sheets
            filepath: Full path in /{bucket}/{filename} format (alternative to filename+bucket_name)
            start_line: Starting line number (1-indexed, inclusive) for partial read
            end_line: Ending line number (1-indexed, inclusive) for partial read
            
        Returns:
            File content or error message if content exceeds size limit
        """
        # Handle filepath parameter - extract bucket and filename
        if filepath:
            try:
                extracted_bucket, extracted_filename = parse_filepath(filepath)
                bucket_name = extracted_bucket
                filename = extracted_filename
                # filepath already contains full path, don't apply folder prefix
                full_key = filename
            except ValueError as e:
                raise ToolException(f"Invalid filepath format: {e}")
        else:
            if not filename:
                raise ToolException("Must provide either 'filename' or 'filepath' parameter")
            # Normalize filename path
            full_key = filename.lstrip('/')
        
        if not filename:
            raise ToolException("Must provide either 'filename' or 'filepath' parameter")
        
        # Determine bucket to use
        target_bucket = bucket_name or self.bucket
        
        # Use Artifact client's get() method (now uses S3 API internally)
        content = self.artifact.get(
            artifact_name=full_key,
            bucket_name=target_bucket,
            is_capture_image=is_capture_image,
            page_number=page_number,
            sheet_name=sheet_name,
            excel_by_sheets=excel_by_sheets,
            llm=self.llm
        )

        # Apply line range slicing if requested (for text content only)
        if isinstance(content, str) and (start_line is not None or end_line is not None):
            offset = start_line if start_line is not None else 1
            limit = (end_line - offset + 1) if end_line is not None else None
            content = apply_line_slice(content, offset=offset, limit=limit)

        # Check content size limit (after slicing if applicable)
        if isinstance(content, str) and len(content) > self.max_single_read_size:
            line_count = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            if start_line is not None or end_line is not None:
                return f"[Content ({line_count} lines) still exceeds size limit. Use smaller range.]"
            return f"[Content has {line_count} lines and exceeds size limit. Use partial read options.]"

        return content
    
    def _read_file(
        self,
        file_path: str,
        branch: str = None,
        bucket_name: str = None,
        **kwargs
    ) -> str:
        """
        Read a file from artifact bucket with optional partial read support.
        
        Parameters:
            file_path: Name of the file in the bucket
            branch: Not used for artifacts (kept for API consistency)
            bucket_name: Name of the bucket (uses default if None)
            **kwargs: Additional parameters (offset, limit, head, tail) - currently ignored,
                     partial read handled client-side by base class methods
        
        Returns:
            File content as string
        """
        return self.read_file(filename=file_path, bucket_name=bucket_name)
    
    def _write_file(
        self,
        file_path: str,
        content: str,
        branch: str = None,
        commit_message: str = None,
        bucket_name: str = None
    ) -> str:
        """Write content to a file (create or overwrite)."""
        try:
            target_bucket = bucket_name or self.bucket
            
            # Normalize filename path
            full_key = file_path.lstrip('/')
            
            result = self.artifact.overwrite(full_key, content, target_bucket)
            if 'error' in result:
                raise ToolException(f"Failed to write file '{file_path}': {result['error']}")
            
            new_filepath = result['filepath']
            sanitized_filename = result.get('sanitized_name', file_path)
            operation_type = result.get('operation_type', 'modify')
            file_exists = result.get('file_existed', True)
            
            message = f"File '{sanitized_filename}' {'updated' if file_exists else 'created'} successfully"
            return_msg = f"{'Updated' if file_exists else 'Created'} file {sanitized_filename}"

            dispatch_custom_event("file_modified", {
                "message": message,
                "filepath": new_filepath,
                "tool_name": "edit_file",
                "toolkit": "artifact",
                "operation_type": operation_type,
                "meta": {
                    "bucket": target_bucket,
                    "file_size": len(content),
                    "source": "generated"
                }
            })

            return return_msg
        except Exception as e:
            raise ToolException(f"Unable to write file {file_path}: {str(e)}")

    def delete_file(self, filename: str, bucket_name = None):
        """Delete a file from the artifact bucket."""
        target_bucket = bucket_name or self.bucket
        
        # Normalize filename path
        full_key = filename.lstrip('/')
        
        result = self.artifact.delete(full_key, target_bucket)
        if 'error' in result:
            raise ToolException(f'Error (deleteFile): {result["error"]}')
        
        return f'File "{filename}" deleted successfully.'

    def append_data(self, filename: str, filedata: str, bucket_name=None, create_if_missing: bool = True):
        """Append data to an existing file or create new if missing."""
        target_bucket = bucket_name or self.bucket
        
        # Normalize filename path
        full_key = filename.lstrip('/')
        
        result = self.artifact.append(full_key, filedata, target_bucket, create_if_missing)
        if 'error' in result:
            raise ToolException(f"Failed to append to file '{filename}': {result['error']}")
        
        new_filepath = result['filepath']
        sanitized_filename = result.get('sanitized_name', filename)

        # Dispatch custom event
        dispatch_custom_event("file_modified", {
            "message": f"Data appended to file successfully at {new_filepath}",
            "filepath": new_filepath,
            "tool_name": "appendData",
            "toolkit": "artifact",
            "operation_type": "modify",
            "meta": {
                "bucket": target_bucket,
                "file_size": len(filedata),
                "source": "generated"
            }
        })

        return json.dumps({
            "filepath": new_filepath,
            "filename": sanitized_filename,
            "bucket": target_bucket,
            "message": "Data appended successfully"
        })

    def overwrite_data(self, filename: str, filedata: str, bucket_name = None):
        """Overwrite file content completely."""
        target_bucket = bucket_name or self.bucket
        
        # Normalize filename path
        full_key = filename.lstrip('/')
        
        result = self.artifact.overwrite(full_key, filedata, target_bucket)
        if 'error' in result:
            raise ToolException(f"Failed to overwrite file '{filename}': {result['error']}")
        
        new_filepath = result['filepath']
        sanitized_filename = result.get('sanitized_name', filename)
        operation_type = result.get('operation_type', 'modify')

        dispatch_custom_event("file_modified", {
            "message": f"File overwritten successfully at {new_filepath}",
            "filepath": new_filepath,
            "tool_name": "overwriteData",
            "toolkit": "artifact",
            "operation_type": operation_type,
            "meta": {
                "bucket": target_bucket,
                "file_size": len(filedata) if isinstance(filedata, (str, bytes)) else 0,
                "source": "generated"
            }
        })
        
        return json.dumps({
            "filepath": new_filepath,
            "filename": sanitized_filename,
            "bucket": target_bucket,
            "message": f"File '{sanitized_filename}' overwritten successfully"
        })

    def get_file_type(self, filepath: str) -> str:
        """Detect file type of a file using file content analysis.

        Uses the `filetype` library to determine file type from magic bytes,
        which is more reliable than extension-based detection.

        Args:
            filepath: Path to the file (/{bucket}/{filename} format)

        Returns:
            JSON string with file type information:
            {
                "filepath": str,
                "extension": str,      # e.g., "jpg", "png", "pdf"
                "mime": str,          # e.g., "image/jpeg", "application/pdf"
                "status": "success" | "error",
                "message": str        # Error message if status is "error"
            }
        """
        try:
            import filetype
        except ImportError:
            return json.dumps({
                "filepath": filepath,
                "status": "error",
                "message": "filetype library not installed. Install with: pip install filetype"
            })

        try:
            # Get raw file content using Artifact client's get_raw_content_by_filepath() method
            file_content, filename = self.artifact.get_raw_content_by_filepath(filepath)

            if not file_content:
                return json.dumps({
                    "filepath": filepath,
                    "status": "error",
                    "message": "File not found or empty"
                })

            # Detect file type from content first (more reliable)
            kind = filetype.guess(file_content)

            if kind is None:
                # Fallback to extension-based detection from filename
                import mimetypes
                from pathlib import Path
                
                ext = Path(filename).suffix.lower()
                mime_type = mimetypes.guess_type(filename)[0]
                
                if mime_type:
                    return json.dumps({
                        "filepath": filepath,
                        "extension": ext.lstrip('.') if ext else "unknown",
                        "mime": mime_type,
                        "filename": filename,
                        "status": "success",
                        "message": f"File type detected from extension: {mime_type}"
                    })
                else:
                    return json.dumps({
                        "filepath": filepath,
                        "filename": filename,
                        "status": "error",
                        "message": "Cannot guess file type from content or extension"
                    })

            return json.dumps({
                "filepath": filepath,
                "extension": kind.extension,
                "mime": kind.mime,
                "filename": filename,
                "status": "success",
                "message": f"File type detected: {kind.mime}"
            })

        except Exception as e:
            return json.dumps({
                "filepath": filepath,
                "status": "error",
                "message": f"Error detecting file type: {str(e)}"
            })

    def create_new_bucket(self, bucket_name: str, expiration_measure = "weeks", expiration_value = 1):
        sanitized_name = bucket_name.replace('_', '-').lower()
        if sanitized_name != bucket_name:
            logging.warning(f"Bucket name '{bucket_name}' was sanitized to '{sanitized_name}' (underscores replaced with hyphens, converted to lowercase)")
        return self.artifact.client.create_bucket(sanitized_name, expiration_measure, expiration_value)

    def _index_tool_params(self):
        return {
            'include_extensions': (Optional[List[str]], Field(
                description="List of file extensions to include when processing: i.e. ['*.png', '*.jpg']. "
                            "If empty, all files will be processed (except skip_extensions).",
                default=[])),
            'skip_extensions': (Optional[List[str]], Field(
                description="List of file extensions to skip when processing: i.e. ['*.png', '*.jpg']",
                default=[])),
        }

    def _base_loader(self, **kwargs) -> Generator[Document, None, None]:
        self._log_tool_event(message=f"Loading the files from artifact's bucket. {kwargs=}", tool_name="loader")
        try:
            all_files = self.list_files(self.bucket, False)['rows']
        except Exception as e:
            raise ToolException(f"Unable to extract files: {e}")

        include_extensions = kwargs.get('include_extensions', [])
        skip_extensions = kwargs.get('skip_extensions', [])
        chunking_config = kwargs.get('chunking_config', {})
        
        # Auto-include extensions from chunking_config if include_extensions is specified
        # This allows chunking config to work without manually adding extensions to include_extensions
        if chunking_config and include_extensions:
            for ext_pattern in chunking_config.keys():
                # Normalize extension pattern (both ".cbl" and "*.cbl" should work)
                normalized = ext_pattern if ext_pattern.startswith('*') else f'*{ext_pattern}'
                if normalized not in include_extensions:
                    include_extensions.append(normalized)
                    self._log_tool_event(
                        message=f"Auto-included extension '{normalized}' from chunking_config",
                        tool_name="loader"
                    )
        
        self._log_tool_event(message=f"Files filtering started. Include extensions: {include_extensions}. "
                                     f"Skip extensions: {skip_extensions}", tool_name="loader")
        # show the progress of filtering
        total_files = len(all_files) if isinstance(all_files, list) else 0
        filtered_files_count = 0
        for file in all_files:
            filtered_files_count += 1
            if filtered_files_count % 10 == 0 or filtered_files_count == total_files:
                self._log_tool_event(message=f"Files filtering progress: {filtered_files_count}/{total_files}",
                                     tool_name="loader")
            file_name = file['name']

            # Check if file should be skipped based on skip_extensions
            if any(re.match(re.escape(pattern).replace(r'\*', '.*') + '$', file_name, re.IGNORECASE)
                   for pattern in skip_extensions):
                continue

            # Check if file should be included based on include_extensions
            # If include_extensions is empty, process all files (that weren't skipped)
            if include_extensions and not (any(re.match(re.escape(pattern).replace(r'\*', '.*') + '$', file_name, re.IGNORECASE)
                                               for pattern in include_extensions)):
                continue

            metadata = {
                ("updated_on" if k == "modified" else k): str(v)
                for k, v in file.items()
            }
            metadata['id'] = self.get_hash_from_bucket_and_file_name(self.bucket, file_name)
            yield Document(page_content="", metadata=metadata)

    def get_hash_from_bucket_and_file_name(self, bucket, file_name):
        hasher = hashlib.sha256()
        hasher.update(bucket.encode('utf-8'))
        hasher.update(file_name.encode('utf-8'))
        return hasher.hexdigest()

    def _extend_data(self, documents: Generator[Document, None, None]):
        for document in documents:
            try:
                page_content = self.artifact.get_content_bytes(artifact_name=document.metadata['name'])
                document.metadata[IndexerKeywords.CONTENT_IN_BYTES.value] = page_content
                document.metadata[IndexerKeywords.CONTENT_FILE_NAME.value] = document.metadata['name']
                yield document
            except Exception as e:
                logging.error(f"Failed while parsing the file '{document.metadata['name']}': {e}")
                yield document

    @extend_with_file_operations
    def get_available_tools(self):
        """Get available tools. Returns all tools for schema; filtering happens at toolkit level."""
        bucket_name = (Optional[str], Field(description="Name of the bucket to work with."
                                                        "If bucket is not specified by user directly, the name should be taken from chat history."
                                                        "If bucket never mentioned in chat, the name will be taken from tool configuration."
                                                        " ***IMPORTANT*** Underscore `_` is prohibited in bucket name and should be replaced by `-`",
                                            default=None))
        
        # Basic artifact tools (always available)
        basic_tools = [
            {
                "ref": self.list_files,
                "name": "listFiles",
                "description": "List files in the artifact bucket. By default lists immediate children (files and subfolders). Use folder parameter to scope listing to a specific prefix/path. Use recursive=True to get all files under the path.",
                "args_schema": create_model(
                    "listBucket",
                    bucket_name=bucket_name,
                    folder=(Optional[str], Field(
                        description="Folder/prefix to scope the listing to a specific path within the bucket.",
                        default=None
                    )),
                    recursive=(Optional[bool], Field(
                        description="If True, returns all files recursively under the path. If False (default), returns only immediate children (files and subfolders).",
                        default=False
                    ))
                )
            },
            {
                "ref": self.create_file,
                "name": "createFile",
                "description": """Create a file in the artifact bucket. Supports two modes:
                1. Create from content: Use 'filedata' parameter to create new files with text, JSON, CSV, or Excel data
                2. Copy existing file: Use 'filepath' parameter to copy existing files (images, PDFs, attachments) while preserving binary format
                
                IMPORTANT: Provide EITHER 'filedata' OR 'filepath', never both or neither.
                Use filepath when copying previously generated images, uploaded PDFs, or any binary files to preserve data integrity.
                The filepath can be found in previous file_modified events in the conversation history (format: /{bucket}/{filename}).""",
                "args_schema": create_model(
                    "createFile", 
                    filename=(str, Field(description="Target filename in destination bucket")),
                    bucket_name=bucket_name,
                    filedata=(Optional[str], Field(
                        description="""Content for creating new files. Use this for text, JSON, CSV, or structured data.
                        Example for .xlsx filedata format:
                        {
                            "Sheet1":[
                                ["Name", "Age", "City"],
                                ["Alice", 25, "New York"],
                                ["Bob", 30, "San Francisco"],
                                ["Charlie", 35, "Los Angeles"]
                            ]
                        }
                        Leave empty if using filepath to copy existing file.""",
                        default=None
                    )),
                    filepath=(Optional[str], Field(
                        description="""Path of existing file to copy (/{bucket}/{filename} format). Use this to copy images, PDFs, or any binary files while preserving format.
                        Find filepath in previous messages (file_modified events, generate_image responses, etc.).
                        Leave empty if using filedata to create new content.""",
                        default=None
                    ))
                )
            },
            {
                "ref": self.read_file,
                "name": "readFile",
                "description": "Read a file from the artifact bucket. Supports full filepath (/{bucket}/{filename}) from attachment descriptions or filename+bucket_name. For large text files that exceed size limits, use start_line/end_line to read specific portions.",
                "args_schema": create_model(
                    "readFile", 
                    filename=(Optional[str], Field(
                        description="Filename (required if filepath not provided)",
                        default=None)),
                    filepath=(Optional[str], Field(
                        description="Full path in /{bucket}/{filename} format. Use this when filepath is provided in attachment descriptions. Alternative to filename+bucket_name.",
                        default=None)),
                    bucket_name=bucket_name,
                    start_line=(Optional[int], Field(
                        description="Starting line number (1-indexed, inclusive) for partial read of text files. Use with end_line to read specific portions of large files.",
                        default=None,
                        ge=1)),
                    end_line=(Optional[int], Field(
                        description="Ending line number (1-indexed, inclusive) for partial read of text files. If not provided, reads to end of file.",
                        default=None,
                        ge=1)),
                    is_capture_image=(Optional[bool],
                                      Field(description="Determines if pictures in the document should be recognized.",
                                            default=False)),
                    page_number=(Optional[int], Field(
                        description="Specifies which page to read. If it is None, then full document will be read.",
                        default=None)),
                    sheet_name=(Optional[str], Field(
                        description="Specifies which sheet to read. If it is None, then full document will be read.",
                        default=None))
                )
            },
            {
                "ref": self.get_file_type,
                "name": "get_file_type",
                "description": "Detect the file type of a file using content analysis. More reliable than extension-based detection as it analyzes file magic bytes. Useful for verifying file types before processing or after generation.",
                "args_schema": create_model(
                    "getFileType",
                    filepath=(str, Field(description="Path to the file (/{bucket}/{filename} format). This filepath is returned when files are uploaded or generated."))
                )
            },
            {
                "ref": self.delete_file,
                "name": "deleteFile",
                "description": "Delete a file in the artifact",
                "args_schema": create_model(
                    "deleteFile", 
                    filename=(str, Field(description="Filename")),
                    bucket_name=bucket_name
                )
            },
            {
                "ref": self.append_data,
                "name": "appendData",
                "description": "Append data to a file in the artifact",
                "args_schema": create_model(
                    "appendData", 
                    filename=(str, Field(description="Filename")),
                    filedata=(str, Field(description="Stringified content to append")),
                    bucket_name=bucket_name,
                    create_if_missing=(Optional[bool], Field(
                        description="If True (default), creates an empty file if it doesn't exist before appending. If False, returns an error when file is not found.",
                        default=True
                    ))
                )
            },
            {
                "ref": self.overwrite_data,
                "name": "overwriteData",
                "description": "Overwrite data in a file in the artifact",
                "args_schema": create_model(
                    "overwriteData", 
                    filename=(str, Field(description="Filename")),
                    filedata=(str, Field(description="Stringified content to overwrite")),
                    bucket_name=bucket_name
                )
            },
            {
                "ref": self.create_new_bucket,
                "name": "createNewBucket",
                "description": "Creates new bucket specified by user.",
                "args_schema": create_model(
                    "createNewBucket",
                    bucket_name=(str, Field(
                        description="Bucket name to create. Must start with lowercase letter and contain only lowercase letters, numbers, and hyphens. Underscores will be automatically converted to hyphens.",
                        pattern=r'^[a-z][a-z0-9_-]*$'  # Allow underscores in input, will be sanitized
                    )),
                    expiration_measure=(Optional[str], Field(description="Measure of expiration time for bucket configuration."
                                                                         "Possible values: `days`, `weeks`, `months`, `years`.",
                                                             default="weeks")),
                    expiration_value=(Optional[int], Field(description="Expiration time values.", default=1))
                )
            }
        ]
        
        # Always include indexing tools in available tools list
        # Filtering based on vector store config happens at toolkit level via decorator
        try:
            # Get indexing tools from parent class
            indexing_tools = super(ArtifactWrapper, self).get_available_tools()
            return indexing_tools + basic_tools
        except Exception as e:
            # If getting parent tools fails, log warning and return basic tools only
            logging.warning(f"Failed to load indexing tools: {e}. Only basic artifact tools will be available.")
            return basic_tools
