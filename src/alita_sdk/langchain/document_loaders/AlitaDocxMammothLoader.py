import base64
import re

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
    def __init__(self, path: str, **kwargs):
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
        self.path = path
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
            List[Document]: A list containing a single Document with the markdown content
                          and metadata including the source file path.
        """
        with open(self.path, 'rb') as docx_file:
            result = convert_to_html(docx_file, convert_image=mammoth.images.img_element(self.__handle_image))
            content = markdownify(result.value, heading_style="ATX")
            result_content = self.__postprocess_original_md(content)
            return [Document(page_content=result_content, metadata={'source': str(self.path)})]

