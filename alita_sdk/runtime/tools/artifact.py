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
from ...runtime.utils.utils import IndexerKeywords


class ArtifactWrapper(NonCodeIndexerToolkit):
    bucket: str
    artifact: Optional[Any] = None
    
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
        return self.artifact.list(bucket_name, return_as_string)

    def create_file(self, filename: str, filedata: str, bucket_name = None):
        if filename.endswith(".xlsx"):
            data = json.loads(filedata)
            filedata = self.create_xlsx_filedata(data)

        result = self.artifact.create(filename, filedata, bucket_name)
        
        # Dispatch custom event for file creation
        self._log_tool_event(
            tool_name="file_modified",
            message="""
            {
                "message": f"File '{filename}' created successfully",
                "filename": filename,
                "tool_name": "createFile",
                "toolkit": "artifact",
                "operation_type": "create",
                "meta": {
                    "bucket": bucket_name or self.bucket
                }
            }""")

        return result

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
        return self.artifact.client.create_bucket(bucket_name, expiration_measure, expiration_value)

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
            if any(re.match(pattern.replace('*', '.*') + '$', file_name, re.IGNORECASE)
                   for pattern in skip_extensions):
                continue

            # Check if file should be included based on include_extensions
            # If include_extensions is empty, process all files (that weren't skipped)
            if include_extensions and not (any(re.match(pattern.replace('*', '.*') + '$', file_name, re.IGNORECASE)
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

    @extend_with_parent_available_tools
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
                    filedata=(str, Field(description="""Stringified content of the file.
                    Example for .xlsx filedata format:
                    {
                        "Sheet1":[
                            ["Name", "Age", "City"],
                            ["Alice", 25, "New York"],
                            ["Bob", 30, "San Francisco"],
                            ["Charlie", 35, "Los Angeles"]
                        ]
                    }
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
                    bucket_name=(str, Field(description="Bucket name to create. ***IMPORTANT*** Underscore `_` is prohibited in bucket name and should be replaced by `-`.")),
                    expiration_measure=(Optional[str], Field(description="Measure of expiration time for bucket configuration."
                                                                         "Possible values: `days`, `weeks`, `months`, `years`.",
                                                             default="weeks")),
                    expiration_value=(Optional[int], Field(description="Expiration time values.", default=1))
                )
            }
        ]