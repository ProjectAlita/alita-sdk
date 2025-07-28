import json

from alita_sdk.tools.chunkers import markdown_chunker
from alita_sdk.tools.elitea_base import BaseToolApiWrapper, BaseVectorStoreToolApiWrapper, extend_with_vector_tools, \
    BaseIndexParams
from langchain_core.tools import ToolException
from typing import Any, Optional, Generator, Dict, List
from pydantic import SecretStr, create_model, Field, model_validator
from langchain_core.documents import Document
try:
    from alita_sdk.runtime.langchain.interfaces.llm_processor import get_embeddings
except ImportError:
    from alita_sdk.langchain.interfaces.llm_processor import get_embeddings

class ArtifactWrapper(BaseVectorStoreToolApiWrapper):
    client: Any
    bucket: str
    artifact: Optional[Any] = None

    llm: Any = None
    connection_string: Optional[SecretStr] = None
    collection_name: Optional[str] = None
    embedding_model: Optional[str] = "HuggingFaceEmbeddings"
    embedding_model_params: Optional[Dict[str, Any]] = {"model_name": "sentence-transformers/all-MiniLM-L6-v2"}
    vectorstore_type: Optional[str] = "PGVector"
    
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

    def read_file(self,
                  filename: str,
                  bucket_name = None,
                  is_capture_image: bool = False,
                  page_number: int = None,
                  sheet_name: str = None,
                  excel_by_sheets: bool = False):
        return self.artifact.get(file_name=filename,
                                 bucket_name=bucket_name,
                                  is_capture_image=is_capture_image,
                                  page_number=page_number,
                                  sheet_name=sheet_name,
                                  excel_by_sheets=excel_by_sheets,
                                  llm=self.llm)

    def delete_file(self, filename: str, bucket_name = None):
        return self.artifact.delete(filename, bucket_name)

    def append_data(self, filename: str, filedata: str, bucket_name = None):
        return self.artifact.append(filename, filedata, bucket_name)

    def overwrite_data(self, filename: str, filedata: str, bucket_name = None):
        return self.artifact.overwrite(filename, filedata, bucket_name)

    def create_new_bucket(self, bucket_name: str, expiration_measure = "weeks", expiration_value = 1):
        return self.artifact.client.create_bucket(bucket_name, expiration_measure, expiration_value)

    def index_data(self,
                   collection_suffix: str = '',
                   progress_step: int = None,
                   clean_index: bool = False):
        """Load files content into the vector store."""
        docs = self._base_loader()
        embedding = get_embeddings(self.embedding_model, self.embedding_model_params)
        vs = self._init_vector_store(collection_suffix, embeddings=embedding)
        return vs.index_documents(docs, progress_step=progress_step, clean_index=clean_index)

    def _base_loader(self) -> List[Document]:
        try:
            all_files = self.list_files(self.bucket)
        except Exception as e:
            raise ToolException(f"Unable to extract files: {e}")

        docs: List[Document] = []
        for file in all_files:
            metadata = {
                ("updated_on" if k == "Modified" else k): str(v)
                for k, v in file.items()
            }
            docs.append(Document(page_content="", metadata=metadata))
        return docs

    def _process_document(self, document: Document) -> Generator[Document, None, None]:
        config = {
            "max_tokens": self.llm.model_config.get('max_tokens', 512),
            "token_overlap": self.llm.model_config.get('token_overlap',
                                                       int(self.llm.model_config.get('max_tokens', 512) * 0.05))
        }
        chunks = markdown_chunker(file_content_generator=self._generate_file_content(document), config=config)
        yield from chunks

    def _generate_file_content(self, document: Document) -> Generator[Document, None, None]:
        page_content = self.read_file(document.metadata['Path'], is_capture_image=True, excel_by_sheets=True)
        if isinstance(page_content, dict):
            for key, value in page_content.items():
                metadata = document.metadata
                metadata['page'] = key
                yield Document(page_content=str(value), metadata=metadata)
        else:
            document.page_content = json.dumps(str(page_content))
            yield document

    @extend_with_vector_tools
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
            },
            {
                "name": "index_data",
                "ref": self.index_data,
                "description": "Load files content into the vector store.",
                "args_schema": create_model(
                    "indexData",
                    __base__=BaseIndexParams,
                    progress_step=(Optional[int], Field(default=None, ge=0, le=100,
                         description="Optional step size for progress reporting during indexing")),
                    clean_index=(Optional[bool], Field(default=False,
                       description="Optional flag to enforce clean existing index before indexing new data")),
                )
            }
        ]