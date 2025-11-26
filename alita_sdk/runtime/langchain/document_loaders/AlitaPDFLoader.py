import pymupdf
import fitz
from langchain_community.document_loaders import PyPDFium2Loader

from .ImageParser import ImageParser
from .utils import perform_llm_prediction_for_image_bytes, create_temp_file
from langchain_core.tools import ToolException

class AlitaPDFLoader:

    def __init__(self, **kwargs):
        if kwargs.get('file_path'):
            self.file_path = kwargs.get('file_path')
        elif kwargs.get('file_content'):
            self.file_content = kwargs.get('file_content')
        else:
            raise ToolException("'file_path' or 'file_content' parameter should be provided.")
        self.password = kwargs.get('password', None)
        self.page_number = kwargs.get('page_number', None)
        self.extract_images = kwargs.get('extract_images', False)
        self.llm = kwargs.get('llm', None)
        self.prompt = kwargs.get('prompt', "Describe image")
        self.headers = kwargs.get('headers', None)
        self.extraction_mode = kwargs.get('extraction_mode', "plain")
        self.extraction_kwargs = kwargs.get('extraction_kwargs', None)
        self.images_parser=ImageParser(llm=self.llm, prompt=self.prompt)

    def get_content(self):
        if hasattr(self, 'file_path'):
            with pymupdf.open(filename=self.file_path, filetype="pdf") as report:
                return self.parse_report(report)
        else:
            with pymupdf.open(stream=self.file_content, filetype="pdf") as report:
                return self.parse_report(report)

    def parse_report(self, report):
        text_content = ''
        if self.page_number is not None:
            page = report.load_page(self.page_number - 1)
            text_content += self.read_pdf_page(report, page, self.page_number)
        else:
            for index, page in enumerate(report, start=1):
                text_content += self.read_pdf_page(report, page, index)

        return text_content

    def read_pdf_page(self, report, page, index):
        # Extract text in block format (to more accurately match hyperlinks to text)
        text_blocks = page.get_text("blocks")  # Returns a list of text blocks
        words = page.get_text("words")  # Returns words with their coordinates

        # Extract hyperlinks
        links = page.get_links()

        # Create a list to store the modified text
        modified_text = []

        for block in text_blocks:
            block_rect = fitz.Rect(block[:4])  # Coordinates of the text block
            block_text = block[4]  # The actual text of the block

            # Check if there are hyperlinks intersecting with this text block
            for link in links:
                if "uri" in link:  # Ensure this is a hyperlink
                    link_rect = link["from"]  # Coordinates of the hyperlink area
                    link_uri = link["uri"]  # The URL of the hyperlink

                    # Expand the hyperlink area slightly to account for inaccuracies
                    link_rect = fitz.Rect(
                        link_rect.x0 - 1, link_rect.y0 - 1, link_rect.x1 + 1, link_rect.y1 + 1
                    )

                    # Find words that are inside the hyperlink area
                    link_text = []
                    for word in words:
                        word_rect = fitz.Rect(word[:4])  # Coordinates of the word
                        word_text = word[4]

                        # Check if the word rectangle is fully inside the hyperlink rectangle
                        if link_rect.contains(word_rect):
                            link_text.append(word_text)
                        # If the word partially intersects, check vertical alignment
                        elif link_rect.intersects(word_rect):
                            # Condition: The word must be on the same line as the hyperlink
                            if abs(link_rect.y0 - word_rect.y0) < 2 and abs(link_rect.y1 - word_rect.y1) < 2:
                                link_text.append(word_text)

                    # Format the hyperlink in Markdown
                    full_text = " ".join(link_text) if link_text else "No text"
                    hyperlink = f"[{full_text}]({link_uri})"

                    # Replace the hyperlink text in the block with the formatted hyperlink
                    block_text = block_text.replace(full_text, hyperlink)

            # Add the processed text block to the result
            modified_text.append(block_text)

        # Combine all text blocks into the final text for the page
        text_content = f'Page: {index}\n' + "\n".join(modified_text)

        if self.extract_images:
            images = page.get_images(full=True)
            for i, img in enumerate(images):
                xref = img[0]
                base_image = report.extract_image(xref)
                img_bytes = base_image["image"]
                text_content += "\n**Image Transcript:**\n" + perform_llm_prediction_for_image_bytes(img_bytes, self.llm, self.prompt)  + "\n--------------------\n"
        return text_content

    def load(self):
        if not hasattr(self, 'file_path'):
            import tempfile

            with tempfile.NamedTemporaryFile(mode='w+b', delete=True, suffix=".pdf") as temp_file:
                temp_file.write(self.file_content)
                temp_file.flush()
                self.file_path = temp_file.name
                return self._load_docs()
        else:
            return self._load_docs()

    def _load_docs(self):
        docs = PyPDFium2Loader(
                file_path = self.file_path,
                password=self.password,
                headers=self.headers,
                extract_images = self.extract_images,
                images_parser = ImageParser(llm=self.llm, prompt=self.prompt),
            ).load()
        for doc in docs:
            doc.metadata['chunk_id'] = doc.metadata['page']
        return docs