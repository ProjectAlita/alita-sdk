
from typing import Any
from json import dumps
import chardet
import logging

from ...tools.utils.content_parser import parse_file_content

logger = logging.getLogger(__name__)

class Artifact:
    def __init__(self, client: Any, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        if not self.client.bucket_exists(bucket_name):
            self.client.create_bucket(bucket_name)

    def create(self, artifact_name: str, artifact_data: Any, bucket_name: str = None, prompt: str = None):
        try:
            if not bucket_name:
                bucket_name = self.bucket_name
            response = self.client.create_artifact(bucket_name, artifact_name, artifact_data, prompt=prompt)
            response['message'] = f"File '{artifact_name}' created successfully"
            return dumps(response)
        except Exception as e:
            logger.error(f"Error: {e}")
            return dumps({"error": str(e)})

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
        data = self.client.download_artifact(bucket_name, artifact_name)
        if len(data) == 0:
            # empty file might be created
            return ""
        if isinstance(data, dict) and data.get('error'):
            return f"{data['error']}. {data.get('content', '')}"
        detected = chardet.detect(data)
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

    def get_raw_content_by_artifact_id(self, artifact_id: str) -> tuple:
        """Get artifact content and filename by artifact ID.
        
        Returns:
            tuple: (file_bytes, filename) where file_bytes is the raw content
                   and filename is extracted from Content-Disposition header
        """
        result = self.client.download_artifact_by_id(artifact_id)
        # Check if result is an error dict (backward compatibility)
        if isinstance(result, dict) and result.get('error'):
            raise Exception(f"{result['error']}. {result.get('content', '')}")
        return result

    def delete(self, artifact_name: str, bucket_name = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        return self.client.delete_artifact(bucket_name, artifact_name)
    
    def list(self, bucket_name: str = None, return_as_string = True) -> str|dict:
        if not bucket_name:
            bucket_name = self.bucket_name
        artifacts = self.client.list_artifacts(bucket_name)
        return str(artifacts) if return_as_string else artifacts

    def append(self, artifact_name: str, additional_data: Any, bucket_name: str = None, create_if_missing: bool = True):
        if not bucket_name:
            bucket_name = self.bucket_name

        # First check if file exists by getting raw response
        raw_data = self.client.download_artifact(bucket_name, artifact_name)

        # If download returns an error dict, the file doesn't exist or there's an access issue
        if isinstance(raw_data, dict) and raw_data.get('error'):
            # Check if we should create the file if it doesn't exist
            if create_if_missing:
                # Create empty file and append data (no leading newline for first content)
                response = self.client.create_artifact(bucket_name, artifact_name, additional_data)
                response['message'] = "Data appended successfully"
                return dumps(response)
            else:
                # Return error as before
                return dumps({"error": f"Cannot append to file '{artifact_name}'. {raw_data['error']}"})

        # Get the parsed content
        data = self.get(artifact_name, bucket_name)
        if data == "Could not detect encoding":
            return dumps({"error": data})

        # Append the new data
        data += f"\n{additional_data}" if len(data) > 0 else additional_data
        response = self.client.create_artifact(bucket_name, artifact_name, data)
        response['message'] = "Data appended successfully"
        return dumps(response)

    def overwrite(self, artifact_name: str, new_data: Any, bucket_name: str = None):
        try:
            if not bucket_name:
                bucket_name = self.bucket_name
            response = self.client.create_artifact(bucket_name, artifact_name, new_data)
            response['message'] = f"File '{artifact_name}' overwritten successfully"
            return dumps(response)
        except Exception as e:
            logger.error(f"Error: {e}")
            return dumps({"error": str(e)})
    
    def get_content_bytes(self,
            artifact_name: str,
            bucket_name: str = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        return self.client.download_artifact(bucket_name, artifact_name)
    