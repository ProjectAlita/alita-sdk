from alita_tools.elitea_base import BaseToolApiWrapper
from typing import Any, Optional
from pydantic import create_model, Field, model_validator

class ArtifactWrapper(BaseToolApiWrapper):
    client: Any
    bucket: str
    artifact: Optional[Any] = None
    
    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        if not values.get('client'):
            raise ValueError("Client is required.")
        if not values.get('bucket'):
            raise ValueError("Bucket is required.")
        values["artifact"] = values['client'].artifact(values['bucket'])
        return values

    def list_files(self, bucket_name = None):
        return self.artifact.list(bucket_name)

    def create_file(self, filename: str, filedata: str, bucket_name = None):
        return self.artifact.create(filename, filedata, bucket_name)

    def read_file(self, filename: str, bucket_name = None):
        return self.artifact.get(filename, bucket_name)

    def delete_file(self, filename: str, bucket_name = None):
        return self.artifact.delete(filename, bucket_name)

    def append_data(self, filename: str, filedata: str, bucket_name = None):
        return self.artifact.append(filename, filedata, bucket_name)

    def overwrite_data(self, filename: str, filedata: str, bucket_name = None):
        return self.artifact.overwrite(filename, filedata, bucket_name)

    def create_new_bucket(self, bucket_name: str, expiration_measure = "weeks", expiration_value = 1):
        return self.artifact.client.create_bucket(bucket_name, expiration_measure, expiration_value)

    def get_available_tools(self):
        bucket_name = (Optional[str], Field(description="Name of the bucket to work with."
                                                        "If bucket is not specified by user directly, the name should be taken from chat history."
                                                        "If bucket never mentioned in chat, the name will be taken from tool configuration."
                                                        " ***IMPORTANT*** Underscore `_` is prohibited in bucket name and should be replaced by `-`",
                                            default=None))
        return [
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
                    filedata=(str, Field(description="Stringified content of the file")),
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
                    bucket_name=bucket_name
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
                    bucket_name=(str, Field(description="Bucket name to create. ***IMPORTANT*** Underscore `_` is prohibited in bucket name and should be replaced by `-`.")),
                    expiration_measure=(Optional[str], Field(description="Measure of expiration time for bucket configuration."
                                                                         "Possible values: `days`, `weeks`, `months`, `years`.",
                                                             default="weeks")),
                    expiration_value=(Optional[int], Field(description="Expiration time values.", default=1))
                )
            },
        ]