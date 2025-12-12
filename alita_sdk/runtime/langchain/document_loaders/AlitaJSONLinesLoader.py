from .AlitaJSONLoader import AlitaJSONLoader
import json
from io import StringIO
from typing import List, Iterator

from langchain_core.documents import Document
from langchain_core.tools import ToolException


class AlitaJSONLinesLoader(AlitaJSONLoader):
    """Load local JSONL files (one JSON object per line) using AlitaJSONLoader behavior.

    Behavior:
    - Supports both `file_path` and `file_content` (bytes or file-like object), same as AlitaJSONLoader.
    - Treats each non-empty line as an independent JSON object.
    - Aggregates all parsed JSON objects into a list and feeds them through the same
      RecursiveJsonSplitter-based chunking used by AlitaJSONLoader.lazy_load.
    - Returns a list of Documents with chunked JSON content.
    """

    def __init__(self, **kwargs):
        # Reuse AlitaJSONLoader initialization logic (file_path / file_content handling, encoding, etc.)
        super().__init__(**kwargs)

    def _iter_lines(self) -> Iterator[str]:
        """Yield lines from file_path or file_content, mirroring AlitaJSONLoader sources."""
        # Prefer file_path if available
        if hasattr(self, "file_path") and self.file_path:
            with open(self.file_path, "r", encoding=self.encoding) as f:
                for line in f:
                    yield line
        # Fallback to file_content if available
        elif hasattr(self, "file_content") and self.file_content:
            # file_content may be bytes or a file-like object
            if isinstance(self.file_content, (bytes, bytearray)):
                text = self.file_content.decode(self.encoding)
                for line in StringIO(text):
                    yield line
            else:
                # Assume it's a text file-like object positioned at the beginning
                self.file_content.seek(0)
                for line in self.file_content:
                    yield line
        else:
            raise ToolException("'file_path' or 'file_content' parameter should be provided.")

    def load(self) -> List[Document]:  # type: ignore[override]
        """Load JSONL content by delegating each non-empty line to AlitaJSONLoader.

        For each non-empty line in the underlying source (file_path or file_content):
        - Create a temporary AlitaJSONLoader instance with that line as file_content.
        - Call lazy_load() on that instance to apply the same RecursiveJsonSplitter logic
          as for a normal JSON file.
        - Accumulate all Documents from all lines and return them as a single list.
        """
        docs: List[Document] = []

        for raw_line in self._iter_lines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                # Instantiate a per-line AlitaJSONLoader using the same configuration
                line_loader = AlitaJSONLoader(
                    file_content=line,
                    file_name=getattr(self, "file_name", str(getattr(self, "file_path", "no_name"))),
                    encoding=self.encoding,
                    autodetect_encoding=self.autodetect_encoding,
                    max_tokens=self.max_tokens,
                )

                for doc in line_loader.lazy_load():
                    docs.append(doc)
            except Exception as e:
                raise ToolException(f"Error processing JSONL line: {line[:100]}... Error: {e}") from e

        return docs
