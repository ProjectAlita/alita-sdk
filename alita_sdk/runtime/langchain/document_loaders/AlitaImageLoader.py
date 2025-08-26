from io import BytesIO
from pathlib import Path
from typing import List

import pytesseract
from PIL import Image
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

from .utils import perform_llm_prediction_for_image_bytes
from ..constants import DEFAULT_MULTIMODAL_PROMPT
from ..tools.utils import image_to_byte_array, bytes_to_base64

Image.MAX_IMAGE_PIXELS = 300_000_000


class AlitaImageLoader(BaseLoader):
    """Loads image files using pytesseract for OCR or optionally LLM for advanced analysis, including SVG support."""

    def __init__(self, file_path=None, **kwargs):
        # Handle both positional and keyword arguments for file_path
        if file_path is not None:
            self.file_path = file_path
        elif kwargs.get('path'):
            self.file_path = kwargs['path']
        elif kwargs.get('file_content'):
            self.file_content = kwargs['file_content']
            self.file_name = kwargs['file_name']
        else:
            raise ValueError(
                "Path parameter is required (either as 'file_path' positional argument or 'path' keyword argument)")
        self.llm = kwargs.get('llm', None)
        self.ocr_language = kwargs.get('ocr_language', None)
        self.prompt = kwargs.get('prompt') if kwargs.get(
            'prompt') is not None else DEFAULT_MULTIMODAL_PROMPT  # Use provided prompt or default

    def get_content(self):
        """
        Retrieves the text content from the file or in-memory content.

        Depending on the file type (SVG or raster image) and the availability of LLM,
        processes the file appropriately using OCR or LLM.

        Returns:
            str: Extracted text content from the file.
        """
        try:
            if hasattr(self, 'file_path'):
                # If file_path is provided
                file_path = Path(self.file_path)
                if not file_path.exists():
                    raise FileNotFoundError(f"File not found: {self.file_path}")

                if file_path.suffix.lower() == '.svg':
                    text_content = self._process_svg(self.file_path)
                else:
                    text_content = self._process_raster_image(self.file_path)

            elif hasattr(self, 'file_content') and hasattr(self, 'file_name'):
                # If file_content and file_name are provided
                file_name = Path(self.file_name)
                if file_name.suffix.lower() == '.svg':
                    text_content = self._process_svg(BytesIO(self.file_content))
                else:
                    text_content = self._process_raster_image(BytesIO(self.file_content))
            else:
                raise ValueError("Either 'file_path' or 'file_content' and 'file_name' must be provided.")

        except pytesseract.TesseractError as e:
            raise ValueError(f"Error during OCR: {e}")
        except ImportError as e:
            raise ImportError(
                f"Error: SVG processing dependencies not installed. Please install svglib and reportlab: {e}")
        except Exception as e:
            raise ValueError(f"Error opening image or processing SVG: {e}")

        return text_content

    def _process_svg(self, svg_source):
        """
        Processes an SVG file or in-memory SVG content.

        If an LLM is available, the SVG is processed using LLM. Otherwise, the SVG
        is converted to PNG and processed using OCR.

        Args:
            svg_source (str, Path, or BytesIO): The SVG file path or in-memory content.

        Returns:
            str: Extracted text content from the SVG.
        """
        if self.llm:
            if isinstance(svg_source, (str, Path)):
                with open(svg_source, 'rb') as f:
                    svg_content = f.read()
            else:
                svg_content = svg_source.read()
            return self.__process_svg_with_llm(svg_content, self.llm, self.prompt)
        else:
            # For OCR on SVG, convert SVG to PNG and then use OCR
            if isinstance(svg_source, (str, Path)):
                drawing = svg2rlg(str(svg_source))  # svglib requires path as a string
            else:
                drawing = svg2rlg(svg_source)  # svglib supports BytesIO
            img_data = BytesIO()
            renderPM.drawToFile(drawing, img_data, fmt="PNG")
            img_data.seek(0)
            image = Image.open(img_data)
            return pytesseract.image_to_string(image, lang=self.ocr_language)

    def _process_raster_image(self, image_source):
        """
        Processes a raster image (e.g., PNG, JPG).

        If an LLM is available, the image is processed using LLM. Otherwise, OCR is used
        to extract text content from the image.

        Args:
            image_source (str, Path, or BytesIO): The image file path or in-memory content.

        Returns:
            str: Extracted text content from the raster image.
        """
        image = Image.open(image_source)
        if self.llm:
            try:
                return self.__perform_llm_prediction_for_image(image, self.llm, self.prompt)
            except Exception as e:
                print(f"Warning: Error during LLM processing of image: {e}. Falling back to OCR.")
                return pytesseract.image_to_string(image, lang=self.ocr_language)
        else:
            return pytesseract.image_to_string(image, lang=self.ocr_language)

    def __perform_llm_prediction_for_image(self, image: Image, llm, prompt: str) -> str:
        """Performs LLM prediction for image content."""
        byte_array = image_to_byte_array(image)
        return perform_llm_prediction_for_image_bytes(byte_array, llm, prompt)

    def __process_svg_with_llm(self, svg_content: bytes, llm, prompt: str) -> str:
        """Processes SVG content using LLM."""
        drawing = svg2rlg(BytesIO(svg_content))
        img_data = BytesIO()
        renderPM.drawToFile(drawing, img_data, fmt="PNG")
        img_data.seek(0)
        image = Image.open(img_data)
        return self.__perform_llm_prediction_for_image(image, llm, prompt)

    def load(self) -> List[Document]:
        """Load text from image using OCR or LLM if llm is provided, supports SVG."""
        text_content = self.get_content()

        metadata = {"source": str(self.file_path if hasattr(self, 'file_path') else self.file_name)}  # Ensure source is always a string for metadata
        return [Document(page_content=text_content, metadata=metadata)]
