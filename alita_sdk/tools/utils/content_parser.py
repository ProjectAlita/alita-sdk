from pathlib import Path

from langchain_core.tools import ToolException
from logging import getLogger
from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map
from langchain_core.documents import Document

from ...runtime.langchain.document_loaders.utils import create_temp_file

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

IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp', 'svg']


def parse_file_content(file_name=None, file_content=None, is_capture_image: bool = False, page_number: int = None,
                       sheet_name: str = None, llm=None, file_path: str = None, excel_by_sheets: bool = False) -> str | ToolException:
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

    if (file_path and (file_name or file_content)) or (not file_path and (not file_name or file_content is None)):
        raise ToolException("Either (file_name and file_content) or file_path must be provided, but not both.")

    extension = Path(file_path if file_path else file_name).suffix

    loader_object = loaders_map.get(extension)
    loader_kwargs = loader_object['kwargs']
    loader_kwargs.update({
        "file_path": file_path,
        "file_content": file_content,
        "file_name": file_name,
        "extract_images": is_capture_image,
        "llm": llm,
        "page_number": page_number,
        "sheet_name": sheet_name,
        "excel_by_sheets": excel_by_sheets
    })
    loader = loader_object['class'](**loader_kwargs)

    if not loader:
        return ToolException(
            "Not supported type of files entered. Supported types are TXT, DOCX, PDF, PPTX, XLSX and XLS only.")

    if hasattr(loader, 'get_content'):
        return loader.get_content()
    else:
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

        loader = loader_cls(file_path, **loader_kwargs)
        documents = loader.load()

        page_contents = [doc.page_content for doc in documents]
        return "\n".join(page_contents)
    except Exception as e:
        error_message = f"Error loading attachment: {str(e)}"
        logger.warning(f"{error_message} for file {file_path}")
        return ""

def load_content_from_bytes(file_content: bytes, extension: str = None, loader_extra_config: dict = None, llm = None) -> str:
    """Loads the content of a file from bytes based on its extension using a configured loader."""
    return load_content(create_temp_file(file_content), extension, loader_extra_config, llm)

def file_to_bytes(filepath):
    """
    Reads a file and returns its content as a bytes object.

    Args:
        filepath (str): The path to the file.

    Returns:
        bytes: The content of the file as a bytes object.
    """
    try:
        with open(filepath, "rb") as f:
            file_content_bytes = f.read()
        return file_content_bytes
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {e}")
        return None