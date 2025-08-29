from pathlib import Path
from typing import Any, List, Union, Generator, Iterator
from langchain_core.documents import Document

from langchain_community.document_loaders.unstructured import (
    UnstructuredFileLoader,
    validate_unstructured_version,
)

class AlitaMarkdownLoader(UnstructuredFileLoader):

    def __init__(
        self,
        file_path: Union[str, Path],
        mode: str = "elements",
        chunker_config: dict = None,
        **unstructured_kwargs: Any,
    ):
        """
        Args:
            file_path: The path to the Markdown file to load.
            mode: The mode to use when loading the file. Can be one of "single",
                "multi", or "all". Default is "single".
            chunker_config: Configuration dictionary for the markdown chunker.
            **unstructured_kwargs: Any kwargs to pass to the unstructured.
        """
        file_path = str(file_path)
        validate_unstructured_version("0.4.16")
        self.chunker_config = chunker_config or {
            "strip_header": False,
            "return_each_line": False,
            "headers_to_split_on": [],
            "max_tokens": 512,
            "token_overlap": 10,
        }
        super().__init__(file_path=file_path, mode=mode, **unstructured_kwargs)

    def _file_content_generator(self) -> Generator[Document, None, None]:
        """
        Creates a generator that yields a single Document object
        representing the entire content of the Markdown file.
        """
        with open(self.file_path, "r", encoding="utf-8") as file:
            content = file.read()
        yield Document(page_content=content, metadata={"source": self.file_path})

    def _get_elements(self) -> List[Document]:
        """
        Processes the Markdown file using the markdown_chunker and returns the chunks.
        """
        from alita_sdk.tools.chunkers.sematic.markdown_chunker import markdown_chunker

        # Create a generator for the file content
        file_content_generator = self._file_content_generator()

        # Use the markdown_chunker to process the content
        chunks = markdown_chunker(file_content_generator, config=self.chunker_config)

        # Convert the generator to a list of Document objects
        return list(chunks)

    def lazy_load(self) -> Iterator[Document]:
        """Load file."""
        elements = self._get_elements()
        self._post_process_elements(elements)
        yield from elements