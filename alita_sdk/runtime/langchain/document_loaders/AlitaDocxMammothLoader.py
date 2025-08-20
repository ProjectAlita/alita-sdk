import re
from io import BytesIO

import mammoth.images
import pytesseract
from PIL import Image
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from mammoth import convert_to_html
from markdownify import markdownify

from alita_sdk.tools.chunkers.sematic.markdown_chunker import markdown_by_headers_chunker
from .utils import perform_llm_prediction_for_image_bytes


class AlitaDocxMammothLoader(BaseLoader):
    """
    Loader for Docx files using Mammoth to convert to HTML, with image handling,
    and then Markdownify to convert HTML to markdown.
    """
    def __init__(self, **kwargs):
        """
        Initializes AlitaDocxMammothLoader.

        Args:
            **kwargs: Keyword arguments, including:
                file_path (str): Path to the Docx file. Required.
                llm (LLM, optional): Language model for processing images.
                prompt (str, optional): Prompt for the language model.
        Raises:
            ValueError: If the 'path' parameter is not provided.
        """
        self.path =  kwargs.get('file_path')
        self.file_content = kwargs.get('file_content')
        self.file_name = kwargs.get('file_name')
        self.extract_images = kwargs.get('extract_images')
        self.llm = kwargs.get("llm")
        self.prompt = kwargs.get("prompt")
        self.max_tokens = kwargs.get('max_tokens', 512)

    def __handle_image(self, image) -> dict:
        """
        Handles image processing within the Docx file.

        Uses LLM for image captioning if available, otherwise falls back to Tesseract OCR,
        and defaults to base64 encoding if both fail.

        Args:
            image (mammoth.images.Image): Image object from Mammoth.

        Returns:
            dict: Dictionary containing the 'src' attribute for the HTML <img> tag.
        """
        output = {}
        try:
            if self.llm:
                # Use LLM for image understanding
                with image.open() as image_bytes:
                    result = perform_llm_prediction_for_image_bytes(image_bytes, self.llm, self.prompt)
                output['src'] = result  # LLM image transcript in src
                return output
            else:
                # Use Tesseract OCR if LLM is not available
                with image.open() as image_bytes:
                    img = Image.open(image_bytes)
                    output['src'] = pytesseract.image_to_string(image=img)  # Tesseract transcript in src
                return output
        except Exception as e:
            # Fallback to default image handling for any exceptions during image processing
            # This ensures robustness against various image format issues, OCR failures,
            # or LLM invocation problems. It prevents the loader from crashing due to
            # a single image processing failure and provides a default image representation.
            return self.__default_image_handler(image)

    def __default_image_handler(self, image) -> dict:
        """
        Default image handler: encodes image to base64 data URL.

        Args:
            image (mammoth.images.Image): Image object from Mammoth.

        Returns:
            dict: Dictionary with base64 encoded 'src' for HTML <img> tag.
        """
        return {"src": "Transcript is not available"}


    def __postprocess_original_md(self, original_md: str) -> str:
        # Pattern to match placeholders like[image_1_1.png] or similar
        pattern = re.compile(r'!\[([^\]]*)\]\(([^)]*)(\s\"([^"]*)\")?\)')

        def replace_placeholder(match):
            transcript = match.group(2)
            # Return a markdown formatted transcript section.
            return f"\n**Image Transcript:**\n{transcript}\n"

        new_md = pattern.sub(replace_placeholder, original_md)
        return new_md

    def load(self):
        """
        Loads and converts the Docx file to markdown format.

        Returns:
            List[Document]: A list containing a Documents with the markdown content
                          and metadata including the source file path.
        """
        result_content = self.get_content()
        return list(markdown_by_headers_chunker(iter([Document(page_content=result_content, metadata={'source': str(self.path)})]), config={'max_tokens':self.max_tokens}))

    def get_content(self):
        """
        Extracts and converts the content of the Docx file to markdown format.

        Handles both file paths and in-memory file content.

        Returns:
            str: The markdown content extracted from the Docx file.
        """
        if self.path:
            # If path is provided, read from file system
            with open(self.path, 'rb') as docx_file:
                return self._convert_docx_to_markdown(docx_file)
        elif self.file_content and self.file_name:
            # If file_content and file_name are provided, read from memory
            docx_file = BytesIO(self.file_content)
            return self._convert_docx_to_markdown(docx_file)
        else:
            raise ValueError("Either 'path' or 'file_content' and 'file_name' must be provided.")

    def _convert_docx_to_markdown(self, docx_file):
        """
        Converts the content of a Docx file to markdown format.

        Args:
            docx_file (BinaryIO): The Docx file object.

        Returns:
            str: The markdown content extracted from the Docx file.
        """
        if self.extract_images:
            # Extract images using the provided image handler
            result = convert_to_html(docx_file, convert_image=mammoth.images.img_element(self.__handle_image))
        else:
            # Ignore images
            result = convert_to_html(docx_file, convert_image=lambda image: "")
        content = markdownify(result.value, heading_style="ATX")
        return self.__postprocess_original_md(content)
