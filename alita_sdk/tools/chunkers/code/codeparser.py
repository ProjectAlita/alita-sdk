import os

from typing import Generator
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter, TokenTextSplitter

from .constants import (Language, get_langchain_language, get_file_extension, 
                        get_programming_language, image_extensions, default_skip)
from .treesitter.treesitter import Treesitter, TreesitterMethodNode

from logging import getLogger

logger = getLogger(__name__)

def parse_code_files_for_db(file_content_generator: Generator[str, None, None], *args, **kwargs) -> Generator[Document, None, None]:
    """
    Parses code files from a generator and returns a generator of Document objects for database storage.

    Args:
        file_content_generator (Generator[str, None, None]): Generator that yields file contents.

    Returns:
        Generator[Document, None, None]: Generator of Document objects containing parsed code information.
    """
    code_splitter = None
    for data in file_content_generator:
        file_name: str = data.get("file_name")
        file_content: str = data.get("file_content")
        file_bytes = file_content.encode()

        file_extension = get_file_extension(file_name)
        programming_language = get_programming_language(file_extension)
        if len(file_content.strip()) == 0 or file_name in default_skip:
            logger.debug(f"Skipping file: {file_name}")
            continue
        if file_extension in image_extensions:
            logger.debug(f"Skipping image file: {file_name} as it is image")
            continue
        if programming_language == Language.UNKNOWN:
            documents = TokenTextSplitter(encoding_name="gpt2", chunk_size=256, chunk_overlap=30).split_text(file_content)
            for document in documents:
                document = Document(
                    page_content=document,
                    metadata={
                        "filename": file_name,
                        "method_name": 'text',
                        "language": programming_language.value,
                    },
                )
                yield document
        else:
            try:
                langchain_language = get_langchain_language(programming_language)

                if langchain_language:
                    code_splitter = RecursiveCharacterTextSplitter.from_language(
                        language=langchain_language,
                        chunk_size=1024,
                        chunk_overlap=128,
                    )
                treesitter_parser = Treesitter.create_treesitter(programming_language)
                treesitterNodes: list[TreesitterMethodNode] = treesitter_parser.parse(
                    file_bytes
                )
                for node in treesitterNodes:
                    method_source_code = node.method_source_code

                    if node.doc_comment and programming_language != Language.PYTHON:
                        method_source_code = node.doc_comment + "\n" + method_source_code

                    splitted_documents = [method_source_code]
                    if code_splitter:
                        splitted_documents = code_splitter.split_text(method_source_code)

                    for splitted_document in splitted_documents:
                        document = Document(
                            page_content=splitted_document,
                            metadata={
                                "filename": file_name,
                                "method_name": node.name,
                                "language": programming_language.value,
                            },
                        )
                        yield document
            except Exception as e:
                from traceback import format_exc
                logger.error(f"Error: {format_exc()}")
                raise e