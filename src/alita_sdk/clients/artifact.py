
from typing import Any
from json import dumps
import chardet
import logging
logger = logging.getLogger(__name__)

class Artifact:
    def __init__(self, client: Any, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        if not self.client.bucket_exists(bucket_name):
            self.client.create_bucket(bucket_name)
    
    def create(self, artifact_name: str, artifact_data: Any):
        try:
            return dumps(self.client.create_artifact(self.bucket_name, artifact_name, artifact_data))
        except Exception as e:
            logger.error(f"Error: {e}")
            return f"Error: {e}"
    
    def get(self, artifact_name: str):
        data = self.client.download_artifact(self.bucket_name, artifact_name)
        if len(data) == 0:
            # empty file might be created
            return ""
        detected = chardet.detect(data)
        if detected['encoding'] is not None:
            return data.decode(detected['encoding'])
        else:
            return "Could not detect encoding"

    def delete(self, artifact_name: str):
        self.client.delete_artifact(self.bucket_name, artifact_name)
    
    def list(self):
        return dumps(self.client.list_artifacts(self.bucket_name))

    def append(self, artifact_name: str, additional_data: Any):
        data = self.get(artifact_name)
        if data == "Could not detect encoding":
            return data
        data += f"\n{additional_data}" if len(data) > 0 else additional_data
        self.client.create_artifact(self.bucket_name, artifact_name, data)
        return "Data appended successfully"
    
    def overwrite(self, artifact_name: str, new_data: Any):
        return self.create(artifact_name, new_data)
    