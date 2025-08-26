import pymupdf
from langchain_community.document_loaders import PyPDFLoader

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
        text_content = f'Page: {index}\n'
        text_content += page.get_text()
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
        return PyPDFLoader(file_path=self.file_path,
                        password=self.password,
                        headers=self.headers,
                        extract_images=self.extract_images,
                        extraction_mode=self.extraction_mode,
                        images_parser=ImageParser(llm=self.llm, prompt=self.prompt),
                        extraction_kwargs=self.extraction_kwargs).load()