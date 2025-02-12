import base64
import logging

import mammoth.images
import pytesseract
from PIL import Image
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from mammoth import convert_to_html
from markdownify import markdownify

from ..constants import DEFAULT_MULTIMODAL_PROMPT


class AlitaDocxMammothLoader(BaseLoader):
    """
    Loader for Docx files using Mammoth to convert to HTML, with image handling,
    and then Markdownify to convert HTML to markdown.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs):
        """
        Initializes AlitaDocxMammothLoader.

        Args:
            **kwargs: Keyword arguments, including:
                path (str): Path to the Docx file. Required.
                llm (LLM, optional): Language model for processing images.
                prompt (str, optional): Prompt for the language model.
        Raises:
            ValueError: If the 'path' parameter is not provided.
        """
        self.path = kwargs.get("path")
        if not self.path:
            raise ValueError("Path parameter 'path' is required")
        self.llm = kwargs.get("llm")
        self.prompt = kwargs.get("prompt")

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
                    base64_string = base64.b64encode(image_bytes.read()).decode()
                url_path = f"data:image/{image.content_type};base64,{base64_string}"
                result = self.llm.invoke([
                    HumanMessage(
                        content=[
                            {"type": "text",
                             "text": self.prompt if self.prompt is not None else DEFAULT_MULTIMODAL_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": url_path},
                            },
                        ]
                    )
                ]).content
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
            self.logger.warning("Error processing image, falling back to default image handler.")
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

    def load(self):
        """
        Loads and converts the Docx file to markdown format.

        Returns:
            List[Document]: A list containing a single Document with the markdown content
                          and metadata including the source file path.
        """
        with open(self.path, 'rb') as docx_file:
            result = convert_to_html(docx_file, convert_image=mammoth.images.img_element(self.__handle_image))
            return [Document(page_content=markdownify(result.value, heading_style="ATX"),
                             metadata={'source': str(self.path)})]
