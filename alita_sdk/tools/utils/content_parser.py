from copy import deepcopy
import os
import re
import tempfile
from logging import getLogger
from pathlib import Path
from typing import Generator, List

from langchain_core.documents import Document
from langchain_core.tools import ToolException

from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map, LoaderProperties
from ...runtime.langchain.document_loaders.AlitaTextLoader import AlitaTextLoader
from ...runtime.utils.utils import IndexerKeywords

logger = getLogger(__name__)

image_processing_prompt='''
You are an AI model designed for analyzing images. Your task is to accurately describe the content of the given image. Depending on the type of image, follow these specific instructions:

If the image is a diagram (e.g., chart, table, pie chart, bar graph, etc.):

Identify the type of diagram.
Extract all numerical values, labels, axis titles, headings, legends, and any other textual elements.
Describe the relationships or trends between the data, if visible.
If the image is a screenshot:

Describe what is shown in the screenshot.
If it is a software interface, identify the program or website name (if visible).
List the key interface elements (e.g., buttons, menus, text fields, images, headers).
If there is text, extract it.
If the screenshot shows a conversation, describe the participants, the content of the messages, and timestamps (if visible).
If the image is a photograph:

Describe the main objects, people, animals, or elements visible in the photo.
Specify the setting (e.g., indoors, outdoors, nature, urban area).
If possible, identify the actions being performed by people or objects in the photo.
If the image is an illustration or drawing:

Describe the style of the illustration (e.g., realistic, cartoonish, abstract).
Identify the main elements, their colors, and the composition of the image.
If there is text, extract it.
If the image contains text:

Extract all text from the image.
Specify the format of the text (e.g., heading, paragraph, list).
If the image is a mixed type (e.g., a diagram within a screenshot):

Identify all types of content present in the image.
Perform an analysis for each type of content separately, following the relevant instructions above.
If the image does not fit into any of the above categories:

Provide a detailed description of what is shown in the image.
Highlight any visible details that could help in understanding the image.
Be as precise and thorough as possible in your responses. If something is unclear or illegible, state that explicitly.
'''


def parse_file_content(file_name=None, file_content=None, is_capture_image: bool = False, page_number: int = None,
                       sheet_name: str = None, llm=None, file_path: str = None, excel_by_sheets: bool = False, prompt=None) -> str | ToolException:
    """Parse the content of a file based on its type and return the parsed content.

    Args:
        file_name (str): The name of the file to parse.
        file_content (bytes): The content of the file as bytes.
        is_capture_image (bool): Whether to capture images from the file.
        page_number (int, optional): The specific page number to parse for PDF or PPTX files.
        sheet_name (str, optional): The specific sheet name to parse for Excel files.
        llm: The language model to use for image processing.
        file_path (str, optional): The path to the file if it needs to be read from disk.
        return_type (str, optional): Tipe of returned result. Possible values are 'str', 'docs'.
    Returns:
        str: The parsed content of the file.
    Raises:
        ToolException: If the file type is not supported or if there is an error reading the file.
        """
    if not prompt:
        prompt = image_processing_prompt
    loader = prepare_loader(
        file_name=file_name,
        file_content=file_content,
        is_capture_image=is_capture_image,
        page_number=page_number,
        sheet_name=sheet_name,
        llm=llm,
        file_path=file_path,
        excel_by_sheets=excel_by_sheets,
        prompt=prompt
    )

    if not loader:
        return ToolException(
            "Not supported type of files entered. Supported types are TXT, DOCX, PDF, PPTX, XLSX and XLS only.")

    try:
        if hasattr(loader, 'get_content'):
            return loader.get_content()
        else:
            extension = Path(file_path if file_path else file_name).suffix
            loader_kwargs = get_loader_kwargs(loaders_map.get(extension), file_name, file_content, is_capture_image, page_number, sheet_name, llm, file_path, excel_by_sheets)
            if file_content:
                return load_content_from_bytes(file_content=file_content,
                                               extension=extension,
                                               loader_extra_config=loader_kwargs,
                                               llm=llm)
            else:
                return load_content(file_path=file_path,
                                    extension=extension,
                                    loader_extra_config=loader_kwargs,
                                    llm=llm)
    except Exception as e:
        return ToolException(f"Error reading file ({file_name or file_path}) content. Make sure these types are supported: {str(e)}")

def load_file_docs(file_name=None, file_content=None, is_capture_image: bool = False, page_number: int = None,
                       sheet_name: str = None, llm=None, file_path: str = None, excel_by_sheets: bool = False) -> List[Document] | ToolException:
    loader = prepare_loader(
        file_name=file_name,
        file_content=file_content,
        is_capture_image=is_capture_image,
        page_number=page_number,
        sheet_name=sheet_name,
        llm=llm,
        file_path=file_path,
        excel_by_sheets=excel_by_sheets
    )
    if not loader:
        return ToolException(
            "Not supported type of files entered. Supported types are TXT, DOCX, PDF, PPTX, XLSX and XLS only.")
    return loader.load()

def get_loader_kwargs(loader_object, file_name=None, file_content=None, is_capture_image: bool = False, page_number: int = None,
                    sheet_name: str = None, llm=None, file_path: str = None, excel_by_sheets: bool = False, prompt=None):
    loader_kwargs = deepcopy(loader_object['kwargs'])
    loader_kwargs.update({
        "file_path": file_path,
        "file_content": file_content,
        "file_name": file_name,
        "extract_images": is_capture_image,
        "llm": llm,
        "page_number": page_number,
        "sheet_name": sheet_name,
        "excel_by_sheets": excel_by_sheets,
        "prompt": prompt,
        "row_content": True,
        "json_documents": False
    })
    return loader_kwargs

def prepare_loader(file_name=None, file_content=None, is_capture_image: bool = False, page_number: int = None,
                       sheet_name: str = None, llm=None, file_path: str = None, excel_by_sheets: bool = False,
                   prompt=None):
        if (file_path and (file_name or file_content)) or (not file_path and (not file_name or file_content is None)):
            raise ToolException("Either (file_name and file_content) or file_path must be provided, but not both.")

        extension = Path(file_path if file_path else file_name).suffix

        loader_object = loaders_map.get(extension)
        if not loader_object:
            loader_object = loaders_map.get('.txt')  # Default to text loader if no specific loader found
        loader_kwargs = get_loader_kwargs(loader_object, file_name, file_content, is_capture_image, page_number, sheet_name, llm, file_path, excel_by_sheets, prompt)
        loader = loader_object['class'](**loader_kwargs)
        return loader

# TODO: review usage of this function alongside with functions above
def load_content(file_path: str, extension: str = None, loader_extra_config: dict = None, llm = None) -> str:
    """
    Loads the content of a file based on its extension using a configured loader.
    """
    try:
        from ...runtime.langchain.document_loaders.constants import loaders_map

        if not extension:
            extension = file_path.split('.')[-1].lower()

        loader_config = loaders_map.get(extension)
        if not loader_config:
            logger.warning(f"No loader found for file extension: {extension}. File: {file_path}")
            return ""

        loader_cls = loader_config['class']
        loader_kwargs = loader_config['kwargs']

        if loader_extra_config:
            loader_kwargs.update(loader_extra_config)
        if loader_config['is_multimodal_processing'] and llm:
            loader_kwargs.update({'llm': llm})
        if "file_path" in loader_kwargs:
            del loader_kwargs["file_path"]

        loader = loader_cls(file_path=file_path, **loader_kwargs)
        documents = loader.load()

        page_contents = [doc.page_content for doc in documents]
        return "\n".join(page_contents)
    except Exception as e:
        error_message = f"Error loading attachment: {str(e)}"
        logger.warning(f"{error_message} for file {file_path}")
        return ""

def load_content_from_bytes(file_content: bytes, extension: str = None, loader_extra_config: dict = None, llm = None) -> str:
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file.flush()
            temp_file_path = temp_file.name

        # Now the file is closed and can be read
        result = load_content(temp_file_path, extension, loader_extra_config, llm)
        return result
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def process_document_by_type(content, extension_source: str, document: Document = None, llm = None, chunking_config=None) \
        -> Generator[Document, None, None]:
    """Process the content of a file based on its type using a configured loader cosidering the origin document."""
    try:
        chunks = process_content_by_type(content, extension_source, llm, chunking_config)
    except Exception as e:
        msg = f"Error during content parsing for file {extension_source}:\n{e}"
        logger.warning(msg)
        yield Document(
            page_content=msg,
            metadata={**document.metadata, 'chunk_id': 1}
        )
        return
    #
    chunks_counter = 0
    for chunk in chunks:
        chunks_counter += 1
        metadata = {**document.metadata, **chunk.metadata}
        #
        # ensure each chunk has a unique chunk_id
        metadata['chunk_id'] = chunks_counter
        #
        yield Document(
            page_content=sanitize_for_postgres(chunk.page_content),
            metadata=metadata
        )


def process_content_by_type(content, filename: str, llm=None, chunking_config=None, fallback_extensions=None) -> \
        Generator[Document, None, None]:
    """Process the content of a file based on its type using a configured loader."""
    temp_file_path = None
    extensions = fallback_extensions if fallback_extensions else []
    match = re.search(r'\.([^.]+)$', filename)

    if match:
        extensions.insert(0, f".{match.group(1).lower()}")
    elif not extensions:
        extensions = [".txt"]

    for extension in extensions:
        try:
            with tempfile.NamedTemporaryFile(mode='w+b', suffix=extension, delete=False) as temp_file:
                temp_file_path = temp_file.name
                if content is None:
                    logger.warning(
                        f"'{IndexerKeywords.CONTENT_IN_BYTES.value}' ie expected but not found in document metadata.")
                    return []
    
                temp_file.write(content)
                temp_file.flush()
    
                loader_config = loaders_map.get(extension)
                if not loader_config:
                    logger.warning(f"No loader found for file extension: {extension}. File: {temp_file_path}")
                    return []
    
                loader_cls = loader_config['class']
                loader_kwargs = loader_config['kwargs']
                # Determine which loader configuration keys are allowed to be overridden by user input.
                # If 'allowed_to_override' is specified in the loader configuration, use it; otherwise, allow all keys in loader_kwargs.
                allowed_to_override = loader_config.get('allowed_to_override', loader_kwargs)
                # If a chunking_config is provided and contains custom configuration for the current file extension,
                # update loader_kwargs with user-supplied values, but only for keys explicitly permitted in allowed_to_override and if value differs from default.
                # This ensures that only safe and intended parameters can be customized, preventing accidental or unauthorized changes
                # to critical loader settings.
                if chunking_config and (users_config_for_extension := chunking_config.get(extension, {})):
                    for key in set(users_config_for_extension.keys()) & set(allowed_to_override.keys()):
                        if users_config_for_extension[key] != allowed_to_override[key]:
                            loader_kwargs[key] = users_config_for_extension[key]
                if LoaderProperties.LLM.value in loader_kwargs and loader_kwargs.pop(LoaderProperties.LLM.value):
                    loader_kwargs['llm'] = llm
                if LoaderProperties.PROMPT_DEFAULT.value in loader_kwargs and loader_kwargs.pop(LoaderProperties.PROMPT_DEFAULT.value):
                    loader_kwargs[LoaderProperties.PROMPT.value] = image_processing_prompt
                loader = loader_cls(file_path=temp_file_path, **loader_kwargs)
                yield from loader.load()
                break
        except Exception as e:
            if fallback_extensions:
                logger.warning(f"Error loading attachment: {str(e)} for file {temp_file_path} (extension: {extension})")
                logger.warning(f"Continuing with fallback extensions: {fallback_extensions}.")
                continue
            else:
                raise e
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

# FIXME copied from langchain_core/utils/strings.py of 0.3.74 version
# https://github.com/langchain-ai/langchain/pull/32157
# should be used from langchain_core.utils import sanitize_for_postgres once updated to newer version
def sanitize_for_postgres(text: str, replacement: str = "") -> str:
    r"""Sanitize text by removing NUL bytes that are incompatible with PostgreSQL.
    PostgreSQL text fields cannot contain NUL (0x00) bytes, which can cause
    psycopg.DataError when inserting documents. This function removes or replaces
    such characters to ensure compatibility.
    Args:
        text: The text to sanitize.
        replacement: String to replace NUL bytes with. Defaults to empty string.
    Returns:
        str: The sanitized text with NUL bytes removed or replaced.
    Example:
        >>> sanitize_for_postgres("Hello\\x00world")
        'Helloworld'
        >>> sanitize_for_postgres("Hello\\x00world", " ")
        'Hello world'
    """
    return text.replace("\x00", replacement)


def file_extension_by_chunker(chunker_name: str) -> str | None:
    if not chunker_name:
        return None
    name = chunker_name.lower()
    if name == "markdown":
        return ".md"
    if name == "json":
        return ".json"
    if name == "text" or name == "txt":
        return ".txt"
    if name == "html":
        return ".html"
    if name == "xml":
        return ".xml"
    if name == "csv":
        return ".csv"
    return None