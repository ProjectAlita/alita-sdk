from io import BytesIO
from pathlib import Path
from typing import List

import pytesseract
from PIL import Image
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

from ..constants import DEFAULT_MULTIMODAL_PROMPT
from ..tools.utils import image_to_byte_array, bytes_to_base64

Image.MAX_IMAGE_PIXELS = 300_000_000


class AlitaImageLoader(BaseLoader):
    """Loads image files using pytesseract for OCR or optionally LLM for advanced analysis, including SVG support."""

    def __init__(self, **kwargs):
        if not kwargs.get('path'):
            raise ValueError("Path parameter 'path' is required")
        else:
            self.file_path = kwargs['path']
        self.llm = kwargs.get('llm', None)
        self.ocr_language = kwargs.get('ocr_language', None)
        self.prompt = kwargs.get('prompt') if kwargs.get(
            'prompt') is not None else DEFAULT_MULTIMODAL_PROMPT  # Use provided prompt or default

    def __perform_llm_prediction_for_image(self, image: Image, llm, prompt: str) -> str:
        """Performs LLM prediction for image content."""
        byte_array = image_to_byte_array(image)
        base64_string = bytes_to_base64(byte_array)
        result = llm.invoke([
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_string}"},
                    },
                ]
            )
        ])
        return result.content

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
        file_path = Path(self.file_path)
        try:
            if file_path.suffix.lower() == '.svg':
                if self.llm:
                    with open(self.file_path, 'rb') as f:
                        svg_content = f.read()
                    text_content = self.__process_svg_with_llm(svg_content, self.llm, self.prompt)
                else:
                    # For OCR on SVG, we first convert SVG to PNG then use OCR
                    drawing = svg2rlg(str(self.file_path))  # svglib requires path as string
                    img_data = BytesIO()
                    renderPM.drawToFile(drawing, img_data, fmt="PNG")
                    img_data.seek(0)
                    image = Image.open(img_data)
                    text_content = pytesseract.image_to_string(image, lang=self.ocr_language)
            else:  # For raster images (png, jpg, etc.)
                image = Image.open(self.file_path)
                if self.llm:
                    try:
                        text_content = self.__perform_llm_prediction_for_image(image, self.llm, self.prompt)
                    except Exception as e:
                        print(f"Warning: Error during LLM processing of image: {e}. Falling back to OCR.")
                        text_content = pytesseract.image_to_string(image,
                                                                   lang=self.ocr_language)  # Fallback to OCR if LLM fails
                else:
                    text_content = pytesseract.image_to_string(image, lang=self.ocr_language)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {self.file_path}")
        except pytesseract.TesseractError as e:
            raise ValueError(f"Error during OCR: {e}")
        except ImportError as e:  # svglib or reportlab missing
            raise ImportError(
                f"Error: SVG processing dependencies not installed. Please install svglib and reportlab: {e}")
        except Exception as e:
            raise ValueError(f"Error opening image or processing SVG: {e}")

        metadata = {"source": str(self.file_path)}  # Ensure source is always a string for metadata
        return [Document(page_content=text_content, metadata=metadata)]
