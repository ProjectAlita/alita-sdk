import base64
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
from ...runtime.utils.utils import IndexerKeywords, resolve_image_from_cache


class ArtifactWrapper(NonCodeIndexerToolkit):
    bucket: str
    artifact: Optional[Any] = None
    
    # Import file operation methods from BaseCodeToolApiWrapper
    read_file_chunk = BaseCodeToolApiWrapper.read_file_chunk
    read_multiple_files = BaseCodeToolApiWrapper.read_multiple_files
    search_file = BaseCodeToolApiWrapper.search_file
    edit_file = BaseCodeToolApiWrapper.edit_file
    
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

    def create_file(self, filename: str, filedata: str, bucket_name = None):
        # Sanitize filename to prevent regex errors during indexing
        sanitized_filename, was_modified = self._sanitize_filename(filename)
        if was_modified:
            logging.warning(f"Filename sanitized: '{filename}' -> '{sanitized_filename}'")
        
        # Auto-detect and extract base64 from image_url structures (from image_generation tool)
        # Returns tuple: (processed_data, is_from_image_generation)
        filedata, is_from_image_generation = self._extract_base64_if_needed(filedata)
        
        if sanitized_filename.endswith(".xlsx"):
            data = json.loads(filedata)
            filedata = self.create_xlsx_filedata(data)

        result = self.artifact.create(sanitized_filename, filedata, bucket_name)
        
        # Skip file_modified event for images from image_generation tool
        # These are already tracked in the tool output and don't need duplicate events
        if not is_from_image_generation:
            # Dispatch custom event for file creation
            dispatch_custom_event("file_modified", {
                "message": f"File '{filename}' created successfully",
                "filename": filename,
                "tool_name": "createFile",
                "toolkit": "artifact",
                "operation_type": "create",
                "meta": {
                    "bucket": bucket_name or self.bucket
                }
            })

        return result
    
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
    
    def _extract_base64_if_needed(self, filedata: str) -> tuple[str | bytes, bool]:
        """
        Resolve cached_image_id references from cache and decode to binary data.
        
        Requires JSON format with cached_image_id field: {"cached_image_id": "img_xxx"}
        LLM must extract specific cached_image_id from generate_image response.
        
        Returns:
            tuple: (processed_data, is_from_image_generation)
                - processed_data: Original filedata or resolved binary image data
                - is_from_image_generation: True if data came from image_generation cache
        """
        if not filedata or not isinstance(filedata, str):
            return filedata, False
        
        # Require JSON format - fail fast if not JSON
        if '{' not in filedata:
            return filedata, False
        
        try:
            data = json.loads(filedata)
        except json.JSONDecodeError:
            # Not valid JSON, return as-is (regular file content)
            return filedata, False
        
        if not isinstance(data, dict):
            return filedata, False
        
        # Only accept direct cached_image_id format: {"cached_image_id": "img_xxx"}
        # LLM must parse generate_image response and extract specific cached_image_id
        if 'cached_image_id' in data:
            binary_data = resolve_image_from_cache(self.alita, data['cached_image_id'])
            return binary_data, True  # Mark as from image_generation
        
        # If JSON doesn't have cached_image_id, treat as regular file content
        return filedata, False

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
            # Sanitize filename
            sanitized_filename, was_modified = self._sanitize_filename(file_path)
            if was_modified:
                logging.warning(f"Filename sanitized: '{file_path}' -> '{sanitized_filename}'")
            
            # Check if file exists
            try:
                self.artifact.get(artifact_name=sanitized_filename, bucket_name=bucket_name, llm=self.llm)
                # File exists, overwrite it
                result = self.artifact.overwrite(sanitized_filename, content, bucket_name)
                
                # Dispatch custom event
                dispatch_custom_event("file_modified", {
                    "message": f"File '{sanitized_filename}' updated successfully",
                    "filename": sanitized_filename,
                    "tool_name": "edit_file",
                    "toolkit": "artifact",
                    "operation_type": "modify",
                    "meta": {
                        "bucket": bucket_name or self.bucket
                    }
                })
                
                return f"Updated file {sanitized_filename}"
            except:
                # File doesn't exist, create it
                result = self.artifact.create(sanitized_filename, content, bucket_name)
                
                # Dispatch custom event
                dispatch_custom_event("file_modified", {
                    "message": f"File '{sanitized_filename}' created successfully",
                    "filename": sanitized_filename,
                    "tool_name": "edit_file",
                    "toolkit": "artifact",
                    "operation_type": "create",
                    "meta": {
                        "bucket": bucket_name or self.bucket
                    }
                })
                
                return f"Created file {sanitized_filename}"
        except Exception as e:
            raise ToolException(f"Unable to write file {file_path}: {str(e)}")

    def delete_file(self, filename: str, bucket_name = None):
        return self.artifact.delete(filename, bucket_name)

    def append_data(self, filename: str, filedata: str, bucket_name = None):
        result = self.artifact.append(filename, filedata, bucket_name)
        
        # Dispatch custom event for file append
        dispatch_custom_event("file_modified", {
            "message": f"Data appended to file '{filename}' successfully",
            "filename": filename,
            "tool_name": "appendData",
            "toolkit": "artifact",
            "operation_type": "modify",
            "meta": {
                "bucket": bucket_name or self.bucket
            }
        })
        
        return result

    def overwrite_data(self, filename: str, filedata: str, bucket_name = None):
        result = self.artifact.overwrite(filename, filedata, bucket_name)
        
        # Dispatch custom event for file overwrite
        dispatch_custom_event("file_modified", {
            "message": f"File '{filename}' overwritten successfully",
            "filename": filename,
            "tool_name": "overwriteData",
            "toolkit": "artifact",
            "operation_type": "modify",
            "meta": {
                "bucket": bucket_name or self.bucket
            }
        })
        
        return result

    def create_new_bucket(self, bucket_name: str, expiration_measure = "weeks", expiration_value = 1):
        # Sanitize bucket name: replace underscores with hyphens and ensure lowercase
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
                "description": "Create a file in the artifact",
                "args_schema": create_model(
                    "createFile", 
                    filename=(str, Field(description="Filename")),
                    filedata=(str, Field(description="""Stringified content of the file.
                    
                    Supports three input formats:
                    
                    1. CACHED IMAGE REFERENCE (for generated/cached images):
                       Pass JSON with cached_image_id field: {"cached_image_id": "img_xxx"}
                       The tool will automatically resolve and decode the image from cache.
                       This is typically used when another tool returns an image reference.
                    
                    2. EXCEL FILES (.xlsx extension):
                       Pass JSON with sheet structure: {"Sheet1": [["Name", "Age"], ["Alice", 25], ["Bob", 30]]}
                    
                    3. TEXT/OTHER FILES:
                       Pass the plain text string directly.
                    """)),
                    bucket_name=bucket_name
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
                    bucket_name=bucket_name
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
