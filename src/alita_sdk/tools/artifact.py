from langchain_core.tools import ToolException
from typing import Any
from pydantic import create_model, BaseModel, Field, model_validator
from pydantic.fields import PrivateAttr

class ArtifactWrapper(BaseModel):
    client: Any
    bucket: str
    _artifact: Any = PrivateAttr()
    
    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        if not values.get('client'):
            raise ValueError("Client is required.")
        if not values.get('bucket'):
            raise ValueError("Bucket is required.")
        cls._artifact = values['client'].artifact(values['bucket'])
        return values

    def list_files(self):
        return self._artifact.list()

    def create_file(self, filename: str, filedata: str):
        return self._artifact.create(filename, filedata)

    def read_file(self, filename: str):
        return self._artifact.get(filename)

    def delete_file(self, filename: str):
        return self._artifact.delete(filename)

    def append_data(self, filename: str, filedata: str):
        return self._artifact.append(filename, filedata)

    def overwrite_data(self, filename: str, filedata: str):
        return self._artifact.overwrite(filename, filedata)

    def get_available_tools(self):
        return [
            {
                "ref": self.list_files,
                "name": "listFiles",
                "description": "List all files in the artifact",
                "args_schema": create_model("listBucket")
            },
            {
                "ref": self.create_file,
                "name": "createFile",
                "description": "Create a file in the artifact",
                "args_schema": create_model(
                    "createFile", 
                    filename=(str, Field(description="Filename")),
                    filedata=(str, Field(description="Stringified content of the file"))
                )
            },
            {
                "ref": self.read_file,
                "name": "readFile",
                "description": "Read a file in the artifact",
                "args_schema": create_model(
                    "readFile", 
                    filename=(str, Field(description="Filename"))
                )
            },
            {
                "ref": self.delete_file,
                "name": "deleteFile",
                "description": "Delete a file in the artifact",
                "args_schema": create_model(
                    "deleteFile", 
                    filename=(str, Field(description="Filename"))
                )
            },
            {
                "ref": self.append_data,
                "name": "appendData",
                "description": "Append data to a file in the artifact",
                "args_schema": create_model(
                    "appendData", 
                    filename=(str, Field(description="Filename")),
                    filedata=(str, Field(description="Stringified content to append"))
                )
            },
            {
                "ref": self.overwrite_data,
                "name": "overwriteData",
                "description": "Overwrite data in a file in the artifact",
                "args_schema": create_model(
                    "overwriteData", 
                    filename=(str, Field(description="Filename")),
                    filedata=(str, Field(description="Stringified content to overwrite"))
                )
            }
        ]

    def run(self, name: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == name:
                return tool["ref"](*args, **kwargs)
        else:
            raise ToolException(f"Unknown tool name: {name}")