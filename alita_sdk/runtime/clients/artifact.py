
from typing import Any
import chardet
import logging

from ...tools.utils.content_parser import parse_file_content

logger = logging.getLogger(__name__)

# Use only the first 10 KB for chardet so it doesn't scan the whole file (slow for large files).
_CHARDET_SAMPLE_SIZE = 10 * 1024

class Artifact:
    def __init__(self, client: Any, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        if not self.client.bucket_exists(bucket_name):
            self.client.create_bucket(bucket_name)

    def create(self, artifact_name: str, artifact_data: Any, bucket_name: str = None, prompt: str = None) -> dict:
        """Create a file. Returns dict with filepath or error."""
        try:
            if not bucket_name:
                bucket_name = self.bucket_name
            result = self.client.upload_artifact_s3(bucket_name, artifact_name, artifact_data)
            if 'error' in result:
                return {"error": result['error']}
            return {
                "message": f"File '{result['sanitized_name']}' created successfully",
                "filepath": result['filepath'],
                "sanitized_name": result['sanitized_name'],
                "was_sanitized": result['was_sanitized']
            }
        except Exception as e:
            logger.error(f"Error: {e}")
            return {"error": str(e)}

    def get(self,
            artifact_name: str,
            bucket_name: str = None,
            is_capture_image: bool = False,
            page_number: int = None,
            sheet_name: str = None,
            excel_by_sheets: bool = False,
            llm = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        # Use S3 API for downloading
        data = self.client.download_artifact_s3(bucket_name, artifact_name)
        if isinstance(data, dict) and 'error' in data:
            return f"{data['error']}. {data.get('content', '')}"
        if len(data) == 0:
            # empty file might be created
            return ""
        detected = chardet.detect(data[:_CHARDET_SAMPLE_SIZE])
        if detected['encoding'] is not None:
            try:
                return data.decode(detected['encoding'])
            except Exception:
                logger.error("Error while default encoding")
                return parse_file_content(file_name=artifact_name,
                                          file_content=data,
                                          is_capture_image=is_capture_image,
                                          page_number=page_number,
                                          sheet_name=sheet_name,
                                          excel_by_sheets=excel_by_sheets,
                                          llm=llm)
        else:
            return parse_file_content(file_name=artifact_name,
                                      file_content=data,
                                      is_capture_image=is_capture_image,
                                      page_number=page_number,
                                      sheet_name=sheet_name,
                                      excel_by_sheets=excel_by_sheets,
                                      llm=llm)

    def get_raw_content_by_filepath(self, filepath: str) -> tuple:
        """Get artifact content and filename by filepath.
        
        Args:
            filepath: File path in format /{bucket}/{filename}
        
        Returns:
            tuple: (file_bytes, filename) where file_bytes is the raw content
        """
        result = self.client.download_artifact_by_filepath(filepath)
        # Check if result is an error dict
        if isinstance(result, dict) and result.get('error'):
            raise Exception(f"{result['error']}. {result.get('content', '')}")
        return result

    def delete(self, artifact_name: str, bucket_name: str = None) -> dict:
        """Delete a file. Returns dict with message or error."""
        if not bucket_name:
            bucket_name = self.bucket_name
        # Use S3 API for delete
        result = self.client.delete_artifact_s3(bucket_name, artifact_name)
        if 'error' in result:
            return {"error": result['error']}
        return {"message": f"File '{artifact_name}' deleted successfully"}
    
    def list(self, bucket_name: str = None, prefix: str = '', delimiter: str = '/') -> dict:
        """List files in bucket with folder/subfolder parsing.
        
        Returns dict with 'total' and 'rows'. Each row has:
        - name: display name (relative to prefix)
        - size: file size in bytes (0 for folders)
        - modified: last modified timestamp (empty for folders)
        - type: 'file' or 'folder'
        - key: full S3 key (only for files, for download link generation)
        """
        if not bucket_name:
            bucket_name = self.bucket_name
        # Use S3 API for listing
        result = self.client.list_artifacts_s3(bucket_name, prefix=prefix, delimiter=delimiter)
        if 'error' in result:
            return {"error": result['error'], "total": 0, "rows": []}
        
        files = []
        
        # Process files at this level (contents)
        for item in result.get('contents', []):
            key = item.get('key', '')
            # Get display name by stripping the prefix
            display_name = key[len(prefix):] if prefix and key.startswith(prefix) else key
            # Skip the folder itself (prefix entry) or empty names
            if not display_name:
                continue
            files.append({
                'name': display_name,
                'size': item.get('size', 0),
                'modified': item.get('lastModified', ''),
                'type': 'file',
                'key': key  # Full key for download link generation
            })
        
        # Process subfolders (commonPrefixes)
        for prefix_entry in result.get('commonPrefixes', []):
            prefix_str = prefix_entry.get('prefix', '') if isinstance(prefix_entry, dict) else prefix_entry
            # Get display name by stripping the prefix
            subfolder_full = prefix_str.rstrip('/')
            subfolder_name = subfolder_full[len(prefix):] if prefix and subfolder_full.startswith(prefix) else subfolder_full
            if subfolder_name:
                files.append({
                    'name': subfolder_name + '/',
                    'size': 0,
                    'modified': '',
                    'type': 'folder'
                })
        
        return {"total": len(files), "rows": files}

    def append(self, artifact_name: str, additional_data: Any, bucket_name: str = None, create_if_missing: bool = True) -> dict:
        """Append data to existing file or create new. Returns dict with filepath or error."""
        if not bucket_name:
            bucket_name = self.bucket_name

        # Use S3 API to check if file exists and get content
        raw_data = self.client.download_artifact_s3(bucket_name, artifact_name)

        # If download returns an error dict, the file doesn't exist or there's an access issue
        if isinstance(raw_data, dict) and raw_data.get('error'):
            # Check if we should create the file if it doesn't exist
            if create_if_missing:
                result = self.client.upload_artifact_s3(bucket_name, artifact_name, additional_data)
                if 'error' in result:
                    return {"error": result['error']}
                return {
                    "message": "File created with initial data",
                    "filepath": result['filepath'],
                    "sanitized_name": result['sanitized_name'],
                    "was_sanitized": result['was_sanitized']
                }
            else:
                return {"error": f"Cannot append to file '{artifact_name}'. {raw_data['error']}"}

        # Get the parsed content
        data = self.get(artifact_name, bucket_name)
        if data == "Could not detect encoding":
            return {"error": data}

        # Append the new data
        data += f"\n{additional_data}" if len(data) > 0 else additional_data
        result = self.client.upload_artifact_s3(bucket_name, artifact_name, data)
        if 'error' in result:
            return {"error": result['error']}
        return {
            "message": "Data appended successfully",
            "filepath": result['filepath'],
            "sanitized_name": result['sanitized_name'],
            "was_sanitized": result['was_sanitized']
        }

    def overwrite(self, artifact_name: str, new_data: Any, bucket_name: str = None) -> dict:
        """Overwrite file content. Returns dict with filepath, operation_type, or error.
        
        Uses HEAD check to determine if file exists (for operation_type in events).
        """
        try:
            if not bucket_name:
                bucket_name = self.bucket_name
            
            # Check if file exists to determine operation type
            head_result = self.client.head_artifact_s3(bucket_name, artifact_name)
            file_exists = head_result.get('exists', False)
            operation_type = "modify" if file_exists else "create"

            result = self.client.upload_artifact_s3(bucket_name, artifact_name, new_data)
            if 'error' in result:
                return {"error": result['error']}
            sanitized_name = result['sanitized_name']
            return {
                "message": f"File '{sanitized_name}' {'overwritten' if file_exists else 'created'} successfully",
                "filepath": result['filepath'],
                "operation_type": operation_type,
                "sanitized_name": sanitized_name,
                "was_sanitized": result['was_sanitized'],
                "file_existed": file_exists
            }
        except Exception as e:
            logger.error(f"Error: {e}")
            return {"error": str(e)}
    
    def get_content_bytes(self,
            artifact_name: str,
            bucket_name: str = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        # Use S3 API for download
        return self.client.download_artifact_s3(bucket_name, artifact_name)
    