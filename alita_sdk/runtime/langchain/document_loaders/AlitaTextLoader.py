from typing import Iterator, Generator

from langchain_core.documents import Document

from langchain_community.document_loaders.base import BaseLoader
from langchain_community.document_loaders.helpers import detect_file_encodings
from langchain_core.tools import ToolException

from alita_sdk.tools.chunkers import markdown_chunker


class AlitaTextLoader(BaseLoader):

    def __init__(self, **kwargs):
        """Initialize with file path."""
        if kwargs.get('file_path'):
            self.file_path = kwargs['file_path']
        elif  kwargs.get('file_content'):
            self.file_content = kwargs['file_content']
            self.file_name = kwargs['file_name']
        else:
            raise ToolException("'file_path' or 'file_content' parameter should be provided.")
        self.encoding = kwargs.get('encoding', 'utf-8')
        self.autodetect_encoding = kwargs.get('autodetect_encoding', False)
        self.max_tokens=kwargs.get('max_tokens', 1024)
        self.token_overlap = kwargs.get('token_overlap', 10)

    def get_content(self):
        text = ""
        try:
            if hasattr(self, 'file_path') and self.file_path:
                with open(self.file_path, encoding=self.encoding) as f:
                    text = f.read()
            elif hasattr(self, 'file_content') and self.file_content:
                text = self.file_content.decode(self.encoding)
            else:
                raise ValueError("Neither file_path nor file_content is provided.")

        except UnicodeDecodeError as e:
            if self.autodetect_encoding:
                if hasattr(self, 'file_path') and self.file_path:
                    detected_encodings = detect_file_encodings(self.file_path)
                    for encoding in detected_encodings:
                        try:
                            with open(self.file_path, encoding=encoding.encoding) as f:
                                text = f.read()
                            break
                        except UnicodeDecodeError:
                            continue
                elif hasattr(self, 'file_content') and self.file_content:
                    detected_encodings = detect_file_encodings(self.file_content)
                    for encoding in detected_encodings:
                        try:
                            text = self.file_content.decode(encoding.encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                else:
                    raise ValueError("Neither file_path nor file_content is provided for encoding detection.")
            else:
                raise RuntimeError(f"Error loading content with encoding {self.encoding}.") from e
        except Exception as e:
            raise RuntimeError(f"Error loading content.") from e

        return text

    def generate_document(self, text, metadata) -> Generator[Document, None, None]:
        yield Document(page_content=text, metadata=metadata)

    def lazy_load(self) -> Iterator[Document]:
        """Load from file path."""
        text = self.get_content()
        metadata = {"source": str(self.file_path) if hasattr(self, 'file_path') else self.file_name}
        chunks = markdown_chunker(file_content_generator=self.generate_document(text, metadata),
                                  config={
                                      "max_tokens": self.max_tokens,
                                      "token_overlap": self.token_overlap
                                  })
        yield from chunks