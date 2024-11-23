from io import BytesIO
from typing import Optional

from PIL import Image
from langchain_community.document_loaders import ConfluenceLoader
from langchain_community.document_loaders.confluence import ContentFormat
from langchain_core.messages import HumanMessage
from pdf2image import convert_from_bytes
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

from ..tools.utils import image_to_byte_array, bytes_to_base64

Image.MAX_IMAGE_PIXELS = 300_000_000


class AlitaConfluenceLoader(ConfluenceLoader):

    def __init__(self, **kwargs):
        self.bins_with_llm = kwargs.get('bins_with_llm', False)
        self.prompt = kwargs.get('prompt', """
## Image Type: Diagrams (e.g., Sequence Diagram, Context Diagram, Component Diagram)
**Prompt**: 
"Analyze the given diagram to identify and describe the connections and relationships between components. Provide a detailed flow of interactions, highlighting key elements and their roles within the system architecture. Provide result in functional specification format ready to be used by BA's, Developers and QA's."
## Image Type: Application Screenshots
**Prompt**: 
"Examine the application screenshot to construct a functional specification. Detail the user experience by identifying and describing all UX components, their functions, and the overall flow of the screen."
## Image Type: Free Form Screenshots (e.g., Text Documents, Excel Sheets)
**Prompt**: 
"Extract and interpret the text from the screenshot. Establish and describe the relationships between the text and any visible components, providing a comprehensive understanding of the content and context."
## Image Type: Mockup Screenshots
**Prompt**: 
"Delve into the UX specifics of the mockup screenshot. Offer a detailed description of each component, focusing on design elements, user interactions, and the overall user experience."
### Instructions:
- Ensure clarity and precision in the analysis for each image type.
- Avoid introducing information does not present in the image.
- Maintain a structured and logical flow in the output to enhance understanding and usability.
- Avoid presenting the entire prompt for user.
    """)
        self.llm = kwargs.get('llm', None)
        for key in ['bins_with_llm', 'prompt', 'llm']:
            try:
                del kwargs[key]
            except:
                pass
        super().__init__(**kwargs)

    def __perform_llm_prediction_for_image(self, image: Image) -> str:
        byte_array = image_to_byte_array(image)
        base64_string = bytes_to_base64(byte_array)
        result = self.llm.invoke([
            HumanMessage(
                content=[
                    {"type": "text", "text": self.prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_string}"},
                    },
                ]
            )
        ])
        return result.content

    def load(self, **kwargs):
        content_formant = kwargs.get('content_format', 'view').lower()
        mapping = {
            'view': ContentFormat.VIEW,
            'storage': ContentFormat.STORAGE,
            'export_view': ContentFormat.EXPORT_VIEW,
            'editor': ContentFormat.EDITOR,
            'anonymous': ContentFormat.ANONYMOUS_EXPORT_VIEW
        }
        kwargs['content_format'] = mapping.get(content_formant, ContentFormat.VIEW)
        return super().load(**kwargs)

    def process_pdf(
            self,
            link: str,
            ocr_languages: Optional[str] = None,
    ) -> str:
        if self.bins_with_llm and self.llm:
            response = self.confluence.request(path=link, absolute=True)
            text = ""

            if (
                    response.status_code != 200
                    or response.content == b""
                    or response.content is None
            ):
                return text
            try:
                images = convert_from_bytes(response.content)
            except ValueError:
                return text

            for i, image in enumerate(images):
                result = self.__perform_llm_prediction_for_image(image)
                text += f"Page {i + 1}:\n{result}\n\n"
            return text
        else:
            return super().process_pdf(link, ocr_languages)

    def process_image(
            self,
            link: str,
            ocr_languages: Optional[str] = None,
    ) -> str:
        if self.bins_with_llm and self.llm:
            response = self.confluence.request(path=link, absolute=True)
            text = ""

            if (
                    response.status_code != 200
                    or response.content == b""
                    or response.content is None
            ):
                return text
            try:
                image = Image.open(BytesIO(response.content))
            except OSError:
                return text
            result = self.__perform_llm_prediction_for_image(image)
            return result
        else:
            return super().process_image(link, ocr_languages)

    def process_svg(
            self,
            link: str,
            ocr_languages: Optional[str] = None,
    ) -> str:
        if self.bins_with_llm and self.llm:
            response = self.confluence.request(path=link, absolute=True)
            text = ""

            if (
                    response.status_code != 200
                    or response.content == b""
                    or response.content is None
            ):
                return text

            drawing = svg2rlg(BytesIO(response.content))

            img_data = BytesIO()
            renderPM.drawToFile(drawing, img_data, fmt="PNG")
            img_data.seek(0)
            image = Image.open(img_data)
            result = self.__perform_llm_prediction_for_image(image)
            return result
        else:
            return super().process_svg(link, ocr_languages)
