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
from ...runtime.utils.utils import IndexerKeywords


class ArtifactWrapper(NonCodeIndexerToolkit):
    bucket: str
    artifact: Optional[Any] = None

    # Override file operation methods to support bucket_name parameter
    # (instead of importing from BaseCodeToolApiWrapper which uses 'branch')

    def read_file_chunk(
        self,
        file_path: str,
        start_line: int,
        end_line: Optional[int] = None,
        bucket_name: str = None
    ) -> str:
        """
        Read a specific range of lines from a file in an artifact bucket.

        Args:
            file_path: Path to the file to read
            start_line: Starting line number (1-indexed, inclusive)
            end_line: Ending line number (1-indexed, inclusive). If None, reads to end.
            bucket_name: Bucket name. If not provided, uses toolkit-configured default bucket.

        Returns:
            File content for the specified line range
        """
        from ...tools.utils.text_operations import apply_line_slice

        # Calculate offset and limit from start_line and end_line
        offset = start_line
        limit = (end_line - start_line + 1) if end_line is not None else None

        # Read the file with bucket_name support
        content = self._read_file(file_path, branch=None, bucket_name=bucket_name, offset=offset, limit=limit)

        # Apply client-side slicing if toolkit doesn't support partial reads
        return apply_line_slice(content, offset=offset, limit=limit)

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
            file_paths: List of file paths to read
            bucket_name: Bucket name. If not provided, uses toolkit-configured default bucket.
            offset: Starting line number for all files (1-indexed)
            limit: Number of lines to read from offset for all files

        Returns:
            Dict mapping file paths to their content
        """
        from ...tools.utils.text_operations import apply_line_slice

        results = {}
        for path in file_paths:
            try:
                content = self._read_file(path, branch=None, bucket_name=bucket_name, offset=offset, limit=limit)
                results[path] = apply_line_slice(content, offset=offset, limit=limit)
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
        from ...tools.utils.text_operations import search_in_content

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
        from ...tools.utils.text_operations import parse_old_new_markers, is_text_editable, try_apply_edit
        from langchain_core.tools import ToolException

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
        ArtifactReadFileChunkInput = create_model(
            "ArtifactReadFileChunkInput",
            file_path=(str, Field(description="Path to the file to read")),
            bucket_name=(Optional[str], Field(
                description="Bucket name. If not provided, uses toolkit-configured default bucket.",
                default=None
            )),
            start_line=(int, Field(description="Starting line number (1-indexed, inclusive)", ge=1)),
            end_line=(Optional[int], Field(
                description="Ending line number (1-indexed, inclusive). If None, reads to end.",
                default=None,
                ge=1
            )),
        )

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
            "read_file_chunk": ArtifactReadFileChunkInput,
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

    def list_files(self, bucket_name = None, return_as_string = True):
        """List all files in the artifact bucket with API download links."""
        result = self.artifact.list(bucket_name, return_as_string=False)
        
        # Add API download link to each file
        if isinstance(result, dict) and 'rows' in result:
            bucket = bucket_name or self.bucket
            
            # Get base_url and project_id from alita client
            base_url = getattr(self.alita, 'base_url', '').rstrip('/')
            project_id = getattr(self.alita, 'project_id', '')
            
            for file_info in result['rows']:
                if 'name' in file_info:
                    # Generate API download link
                    file_name = file_info['name']
                    file_info['link'] = f"{base_url}/api/v2/artifacts/artifact/default/{project_id}/{bucket}/{file_name}"
        
        return str(result) if return_as_string else result

    def create_file(self, filename: str, bucket_name = None, filedata: str = None, artifact_id: str = None):
        """Create a file in the artifact bucket from new content or by copying an existing artifact.

        Args:
            filename: Target filename in destination bucket
            bucket_name: Destination bucket (uses default if None)
            filedata: Content for creating new files (text, JSON, CSV, etc.)
            artifact_id: UUID of existing artifact to copy (preserves binary format)

        Note: Provide EITHER filedata OR artifact_id, not both or neither.
        """
        # Validation: exactly one source must be provided
        if filedata is None and artifact_id is None:
            raise ToolException(
                "Must provide either 'filedata' (to create new content) or 'artifact_id' (to copy existing file). "
                "Both parameters cannot be empty."
            )

        if filedata is not None and artifact_id is not None:
            raise ToolException(
                "Cannot provide both 'filedata' and 'artifact_id'. "
                "Use 'artifact_id' to copy existing files preserving binary format, "
                "or 'filedata' to create new content from text/data."
            )

        # Sanitize filename to prevent regex errors during indexing
        sanitized_filename, was_modified = self._sanitize_filename(filename)
        if was_modified:
            logging.warning(f"Filename sanitized: '{filename}' -> '{sanitized_filename}'")

        # Determine operation type and get file content
        if artifact_id:
            # Copy mode: get raw bytes from existing artifact
            operation_type = "copy"
            try:
                file_bytes, _ = self.artifact.get_raw_content_by_artifact_id(artifact_id)
                # Use the tuple but only need the bytes, filename comes from method parameter
                filedata = file_bytes
            except Exception as e:
                raise ToolException(f"Failed to retrieve artifact '{artifact_id}': {str(e)}")

            file_size = len(filedata) if isinstance(filedata, bytes) else 0
            source_artifact_id = artifact_id
        else:
            # Create mode: use provided content
            operation_type = "create"
            if sanitized_filename.endswith(".xlsx"):
                data = json.loads(filedata)
                filedata = self.create_xlsx_filedata(data)

            file_size = len(filedata) if isinstance(filedata, (str, bytes)) else 0
            source_artifact_id = None

        create_response = self.artifact.create(sanitized_filename, filedata, bucket_name)
        
        response_data = json.loads(create_response)
        if "error" in response_data:
            raise ToolException(f"Failed to create file '{sanitized_filename}': {response_data['error']}")

        new_artifact_id = response_data['artifact_id']

        # Build event metadata
        event_meta = {
            "bucket": bucket_name or self.bucket,
            "file_size": file_size,
            "source": "generated"
        }
        if source_artifact_id:
            event_meta["source_artifact_id"] = source_artifact_id
            event_meta["operation"] = "copy"

        dispatch_custom_event("file_modified", {
            "message": f"File '{filename}' {'copied' if operation_type == 'copy' else 'created'} successfully",
            "artifact_id": new_artifact_id,
            "filename": filename,
            "tool_name": "createFile",
            "toolkit": "artifact",
            "operation_type": operation_type,
            "meta": event_meta
        })

        return json.dumps({
            "artifact_id": new_artifact_id,
            "filename": sanitized_filename,
            "bucket": bucket_name or self.bucket,
            "message": response_data.get('message',
                f"File '{filename}' {'copied' if operation_type == 'copy' else 'created'} successfully")
        })
    
    @staticmethod
    def _sanitize_filename(filename: str) -> tuple:
        """Sanitize filename for safe storage and regex pattern matching."""
        from pathlib import Path
        
        if not filename or not filename.strip():
            return "unnamed_file", True
        
        original = filename
        path_obj = Path(filename)
        name = path_obj.stem
        extension = path_obj.suffix
        
        # Whitelist: alphanumeric, underscore, hyphen, space, Unicode letters/digits
        sanitized_name = re.sub(r'[^\w\s-]', '', name, flags=re.UNICODE)
        sanitized_name = re.sub(r'[-\s]+', '-', sanitized_name)
        sanitized_name = sanitized_name.strip('-').strip()
        
        if not sanitized_name:
            sanitized_name = "file"
        
        if extension:
            extension = re.sub(r'[^\w.-]', '', extension, flags=re.UNICODE)
        
        sanitized = sanitized_name + extension
        return sanitized, (sanitized != original)

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
                  filename: str,
                  bucket_name = None,
                  is_capture_image: bool = False,
                  page_number: int = None,
                  sheet_name: str = None,
                  excel_by_sheets: bool = False):
        return self.artifact.get(artifact_name=filename,
                                 bucket_name=bucket_name,
                                  is_capture_image=is_capture_image,
                                  page_number=page_number,
                                  sheet_name=sheet_name,
                                  excel_by_sheets=excel_by_sheets,
                                  llm=self.llm)
    
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
        """
        Write content to a file (create or overwrite).
        
        Parameters:
            file_path: Name of the file in the bucket
            content: New file content
            branch: Not used for artifacts (kept for API consistency)
            commit_message: Not used for artifacts (kept for API consistency)
            bucket_name: Name of the bucket (uses default if None)
            
        Returns:
            Success message
        """
        try:
            sanitized_filename, was_modified = self._sanitize_filename(file_path)
            if was_modified:
                logging.warning(f"Filename sanitized: '{file_path}' -> '{sanitized_filename}'")
            
            operation_type = "modify"
            try:
                self.artifact.get(artifact_name=sanitized_filename, bucket_name=bucket_name, llm=self.llm)
                result = self.artifact.overwrite(sanitized_filename, content, bucket_name)
                message = f"File '{sanitized_filename}' updated successfully"
                return_msg = f"Updated file {sanitized_filename}"
            except:
                result = self.artifact.create(sanitized_filename, content, bucket_name)
                operation_type = "create"
                message = f"File '{sanitized_filename}' created successfully"
                return_msg = f"Created file {sanitized_filename}"

            response_data = json.loads(result)
            if "error" in response_data:
                raise ToolException(f"Failed to write file '{sanitized_filename}': {response_data['error']}")

            artifact_id = response_data['artifact_id']

            dispatch_custom_event("file_modified", {
                "message": message,
                "artifact_id": artifact_id,
                "filename": sanitized_filename,
                "tool_name": "edit_file",
                "toolkit": "artifact",
                "operation_type": operation_type,
                "meta": {
                    "bucket": bucket_name or self.bucket,
                    "file_size": len(content),
                    "source": "generated"
                }
            })

            return return_msg
        except Exception as e:
            raise ToolException(f"Unable to write file {file_path}: {str(e)}")

    def delete_file(self, filename: str, bucket_name = None):
        # Check if file exists before attempting deletion
        # S3/MinIO delete is idempotent and won't fail for non-existing files
        try:
            files = self.list_files(bucket_name, return_as_string=False)
            file_names = [f['name'] for f in files.get('rows', [])]
            if filename not in file_names:
                raise ToolException(f'Error (deleteFile): ENOENT: no such file or directory: \'{filename}\'')
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f'Error (deleteFile): Unable to verify file existence for \'{filename}\': {str(e)}')

        result = self.artifact.delete(filename, bucket_name)
        if result and isinstance(result, dict) and result.get('error'):
            raise ToolException(f'Error (deleteFile): {result.get("error")} for file \'{filename}\'')
        return f'File "{filename}" deleted successfully.'

    def append_data(self, filename: str, filedata: str, bucket_name=None, create_if_missing: bool = True):
        result = self.artifact.append(filename, filedata, bucket_name, create_if_missing)
        response_data = json.loads(result)
        if 'error' in response_data:
            raise ToolException(f"Failed to append to file '{filename}': {response_data['error']}")

        # Only dispatch custom event if append succeeded (not an error message)
        artifact_id = response_data['artifact_id']
        dispatch_custom_event("file_modified", {
            "message": f"Data appended to file '{filename}' successfully",
            "artifact_id": artifact_id,
            "filename": filename,
            "tool_name": "appendData",
            "toolkit": "artifact",
            "operation_type": "modify",
            "meta": {
                "bucket": bucket_name or self.bucket,
                "file_size": response_data.get('size', 0),
                "source": "generated"
            }
        })

        return json.dumps({
            "artifact_id": artifact_id,
            "filename": filename,
            "bucket": bucket_name or self.bucket,
            "message": response_data.get('message', "Data appended successfully")
        })

    def overwrite_data(self, filename: str, filedata: str, bucket_name = None):
        result = self.artifact.overwrite(filename, filedata, bucket_name)
        
        response_data = json.loads(result)
        if "error" in response_data:
            raise ToolException(f"Failed to overwrite file '{filename}': {response_data['error']}")

        artifact_id = response_data['artifact_id']

        dispatch_custom_event("file_modified", {
            "message": f"File '{filename}' overwritten successfully",
            "artifact_id": artifact_id,
            "filename": filename,
            "tool_name": "overwriteData",
            "toolkit": "artifact",
            "operation_type": "modify",
            "meta": {
                "bucket": bucket_name or self.bucket,
                "file_size": len(filedata) if isinstance(filedata, (str, bytes)) else 0,
                "source": "generated"
            }
        })
        
        return json.dumps({
            "artifact_id": artifact_id,
            "filename": filename,
            "bucket": bucket_name or self.bucket,
            "message": response_data.get('message', f"File '{filename}' overwritten successfully")
        })

    def get_file_type(self, artifact_id: str) -> str:
        """Detect file type of an artifact using file content analysis.

        Uses the `filetype` library to determine file type from magic bytes,
        which is more reliable than extension-based detection.

        Args:
            artifact_id: UUID of the artifact to analyze

        Returns:
            JSON string with file type information:
            {
                "artifact_id": str,
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
                "artifact_id": artifact_id,
                "status": "error",
                "message": "filetype library not installed. Install with: pip install filetype"
            })

        try:
            # Get raw file content using Artifact client's get_raw_content_by_artifact_id() method
            file_content, artifact_filename = self.artifact.get_raw_content_by_artifact_id(artifact_id)

            if not file_content:
                return json.dumps({
                    "artifact_id": artifact_id,
                    "status": "error",
                    "message": "Artifact not found or empty"
                })

            # Detect file type from content first (more reliable)
            kind = filetype.guess(file_content)

            if kind is None:
                # Fallback to extension-based detection from filename
                import mimetypes
                from pathlib import Path
                
                ext = Path(artifact_filename).suffix.lower()
                mime_type = mimetypes.guess_type(artifact_filename)[0]
                
                if mime_type:
                    return json.dumps({
                        "artifact_id": artifact_id,
                        "extension": ext.lstrip('.') if ext else "unknown",
                        "mime": mime_type,
                        "filename": artifact_filename,
                        "status": "success",
                        "message": f"File type detected from extension: {mime_type}"
                    })
                else:
                    return json.dumps({
                        "artifact_id": artifact_id,
                        "filename": artifact_filename,
                        "status": "error",
                        "message": "Cannot guess file type from content or extension"
                    })

            return json.dumps({
                "artifact_id": artifact_id,
                "extension": kind.extension,
                "mime": kind.mime,
                "filename": artifact_filename,
                "status": "success",
                "message": f"File type detected: {kind.mime}"
            })

        except Exception as e:
            return json.dumps({
                "artifact_id": artifact_id,
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
                "description": "List all files in the artifact",
                "args_schema": create_model("listBucket", bucket_name=bucket_name)
            },
            {
                "ref": self.create_file,
                "name": "createFile",
                "description": """Create a file in the artifact bucket. Supports two modes:
                1. Create from content: Use 'filedata' parameter to create new files with text, JSON, CSV, or Excel data
                2. Copy existing file: Use 'artifact_id' parameter to copy existing files (images, PDFs, attachments) while preserving binary format
                
                IMPORTANT: Provide EITHER 'filedata' OR 'artifact_id', never both or neither.
                Use artifact_id when copying previously generated images, uploaded PDFs, or any binary files to preserve data integrity.
                The artifact_id can be found in previous file_modified events in the conversation history.""",
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
                        Leave empty if using artifact_id to copy existing file.""",
                        default=None
                    )),
                    artifact_id=(Optional[str], Field(
                        description="""UUID of existing artifact to copy. Use this to copy images, PDFs, or any binary files while preserving format.
                        Find artifact_id in previous messages (file_modified events, generate_image responses, etc.).
                        Leave empty if using filedata to create new content.""",
                        default=None
                    ))
                )
            },
            {
                "ref": self.read_file,
                "name": "readFile",
                "description": "Read a file in the artifact",
                "args_schema": create_model(
                    "readFile", 
                    filename=(str, Field(description="Filename")),
                    bucket_name=bucket_name,
                    is_capture_image=(Optional[bool],
                                      Field(description="Determines is pictures in the document should be recognized.",
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
                "description": "Detect the file type of an artifact using content analysis. More reliable than extension-based detection as it analyzes file magic bytes. Useful for verifying file types before processing or after generation.",
                "args_schema": create_model(
                    "getFileType",
                    artifact_id=(str, Field(description="UUID of the artifact to analyze. This is the artifact_id returned when files are uploaded or generated."))
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
