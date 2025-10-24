from io import BytesIO
from typing import Optional, List
from logging import getLogger

import requests
from langchain_core.documents import Document

logger = getLogger(__name__)
from PIL import Image
from langchain_community.document_loaders import ConfluenceLoader
from langchain_community.document_loaders.confluence import ContentFormat
from langchain_core.messages import HumanMessage
from pdf2image import convert_from_bytes
# from reportlab.graphics import renderPM
# from svglib.svglib import svg2rlg

from .utils import image_to_byte_array, bytes_to_base64

Image.MAX_IMAGE_PIXELS = 300_000_000


class AlitaConfluenceLoader(ConfluenceLoader):

    def __init__(self, confluence_client, llm, bins_with_llm=False, **kwargs):
        self.bins_with_llm = bins_with_llm
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
        self.llm = llm
        for key in ['bins_with_llm', 'prompt', 'llm']:
            try:
                del kwargs[key]
            except:
                pass
        self.base_url = kwargs.get('url')
        self.space_key = kwargs.get('space_key')
        self.page_ids = kwargs.get('page_ids')
        self.label = kwargs.get('label')
        self.cql = kwargs.get('cql')
        self.include_restricted_content = kwargs.get('include_restricted_content', False)
        self.include_archived_content = kwargs.get('include_archived_content', False)
        self.include_attachments = kwargs.get('include_attachments', False)
        self.include_comments = kwargs.get('include_comments', False)
        self.include_labels = kwargs.get('include_labels', False)
        self.content_format: ContentFormat = kwargs.get('content_format', ContentFormat.VIEW)
        self.limit = kwargs.get('limit', 10)
        self.max_pages = kwargs.get('max_pages', 1000)
        self.ocr_languages = kwargs.get('ocr_languages')
        self.keep_markdown_format = kwargs.get('keep_markdown_format', True)
        self.keep_newlines = kwargs.get('keep_newlines', True)
        self.number_of_retries: int = kwargs.get('number_of_retries', 3)
        self.min_retry_seconds: int = kwargs.get('min_retry_seconds', 5)
        self.max_retry_seconds: int = kwargs.get('max_retry_seconds', 60)
        if self.label or self.cql or self.page_ids:
            self.space_key = None
        self.confluence = confluence_client

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

    def process_attachment(
        self,
        page_id: str,
        ocr_languages: Optional[str] = None,
    ) -> List[str]:
        """
        Process attachments from a Confluence page and extract text from them.
        Note: if the attachment is corrupted, it will be skipped and an error will be logged.
        """

        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            raise ImportError(
                "`Pillow` package not found, " "please run `pip install Pillow`"
            )

        attachments = self.confluence.get_attachments_from_content(page_id)["results"]
        texts = []
        for attachment in attachments:
            media_type = attachment["metadata"]["mediaType"]
            absolute_url = self.base_url + attachment["_links"]["download"]
            title = attachment["title"]
            try:
                if media_type == "application/pdf":
                    text = title + self.process_pdf(absolute_url, ocr_languages)
                elif (
                    media_type == "image/png"
                    or media_type == "image/jpg"
                    or media_type == "image/jpeg"
                ):
                    text = title + self.process_image(absolute_url, ocr_languages)
                elif (
                    media_type == "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ):
                    text = title + self.process_doc(absolute_url)
                elif media_type == "application/vnd.ms-excel":
                    text = title + self.process_xls(absolute_url)
                # TODO review usage
                # elif media_type == "image/svg+xml":
                #     text = title + self.process_svg(absolute_url, ocr_languages)
                else:
                    continue
                texts.append(text)
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    print(f"Attachment not found at {absolute_url}")  # noqa: T201
                    continue
                else:
                    raise
            except Exception as e:
                print(f"Error processing attachment {absolute_url}: {e}")
                continue
        return texts

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

    def process_page(self, page: dict, include_attachments: bool, include_comments: bool, include_labels: bool,
                     content_format: ContentFormat, ocr_languages: Optional[str] = None,
                     keep_markdown_format: Optional[bool] = False, keep_newlines: bool = False) -> Document:
        if not page.get("title"):
            # if 'include_restricted_content' set to True, draft pages are loaded and can have no title
            page["title"] = "Untitled"
        return super().process_page(page, include_attachments, include_comments, include_labels, content_format,
                                    ocr_languages, keep_markdown_format, keep_newlines)

    # TODO review usage
    # def process_svg(
    #         self,
    #         link: str,
    #         ocr_languages: Optional[str] = None,
    # ) -> str:
    #     if self.bins_with_llm and self.llm:
    #         response = self.confluence.request(path=link, absolute=True)
    #         text = ""
    # 
    #         if (
    #                 response.status_code != 200
    #                 or response.content == b""
    #                 or response.content is None
    #         ):
    #             return text
    # 
    #         drawing = svg2rlg(BytesIO(response.content))
    # 
    #         img_data = BytesIO()
    #         renderPM.drawToFile(drawing, img_data, fmt="PNG")
    #         img_data.seek(0)
    #         image = Image.open(img_data)
    #         result = self.__perform_llm_prediction_for_image(image)
    #         return result
    #     else:
    #         return super().process_svg(link, ocr_languages)
