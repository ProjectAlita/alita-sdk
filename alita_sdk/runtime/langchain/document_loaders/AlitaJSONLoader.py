import json
from typing import Iterator

from langchain_core.documents import Document

from langchain_community.document_loaders.base import BaseLoader
from langchain_community.document_loaders.helpers import detect_file_encodings
from langchain_core.tools import ToolException
from langchain_text_splitters import RecursiveJsonSplitter


class AlitaJSONLoader(BaseLoader):

    def __init__(self, **kwargs):
        """Initialize with file path."""
        if kwargs.get('file_path'):
            self.file_path = kwargs['file_path']
        elif kwargs.get('file_content'):
            self.file_content = kwargs['file_content']
            self.file_name = kwargs['file_name']
        else:
            raise ToolException("'file_path' or 'file_content' parameter should be provided.")
        self.encoding = kwargs.get('encoding', 'utf-8')
        self.autodetect_encoding = kwargs.get('autodetect_encoding', False)
        self.max_tokens = kwargs.get('max_tokens', 512)

    def get_content(self):
        try:
            if hasattr(self, 'file_path') and self.file_path:
                with open(self.file_path, encoding=self.encoding) as f:
                    return json.load(f)
            elif hasattr(self, 'file_content') and self.file_content:
                return json.load(self.file_content)
            else:
                raise ValueError("Neither file_path nor file_content is provided.")

        except UnicodeDecodeError as e:
            if self.autodetect_encoding:
                if hasattr(self, 'file_path') and self.file_path:
                    detected_encodings = detect_file_encodings(self.file_path)
                    for encoding in detected_encodings:
                        try:
                            with open(self.file_path, encoding=encoding.encoding) as f:
                                return f.read()
                            break
                        except UnicodeDecodeError:
                            continue
                elif hasattr(self, 'file_content') and self.file_content:
                    detected_encodings = detect_file_encodings(self.file_content)
                    for encoding in detected_encodings:
                        try:
                            return self.file_content.decode(encoding.encoding)
                        except UnicodeDecodeError:
                            continue
                else:
                    raise ValueError("Neither file_path nor file_content is provided for encoding detection.")
            else:
                raise RuntimeError(f"Error loading content with encoding {self.encoding}.") from e
        except Exception as e:
            raise RuntimeError(f"Error loading content.") from e

    def lazy_load(self) -> Iterator[Document]:
        """Load from file path."""
        content_json = self.get_content()

        if isinstance(content_json, list):
            data_dict = {str(i): item for i, item in enumerate(content_json)}
        else:
            data_dict = content_json
        chunks = RecursiveJsonSplitter(max_chunk_size=self.max_tokens).split_json(json_data=data_dict)
        for chunk in chunks:
            metadata = {"source": str(self.file_path) if hasattr(self, 'file_path') else self.file_name}
            yield Document(page_content=json.dumps(chunk), metadata=metadata)
