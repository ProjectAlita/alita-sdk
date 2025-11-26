import io

from langchain_core.tools import ToolException
from pptx import Presentation
from .utils import perform_llm_prediction_for_image_bytes, create_temp_file
from pptx.enum.shapes import MSO_SHAPE_TYPE
from langchain_core.documents import Document

class AlitaPowerPointLoader:

    def __init__(self, file_path=None, file_content=None, mode=None, **unstructured_kwargs):
        if file_path:
            self.file_path = file_path
        elif file_content:
            self.file_content = file_content
        else:
            raise ToolException("'file_path' or 'file_content' parameter should be provided.")

        self.mode=mode
        self.unstructured_kwargs = unstructured_kwargs
        self.page_number = unstructured_kwargs.get('page_number', None)
        self.extract_images = unstructured_kwargs.get('extract_images', False)
        self.llm = unstructured_kwargs.get('llm', None)
        self.prompt = unstructured_kwargs.get('prompt', "Describe image")
        self.pages_per_chunk = unstructured_kwargs.get('pages_per_chunk', 5)

    def get_content(self):
        if hasattr(self, 'file_path'):
            with open(self.file_path, 'rb') as f:
                prs = Presentation(f)
        elif hasattr(self, 'file_content'):
            prs = Presentation(io.BytesIO(self.file_content))
        pages = []
        if self.page_number is not None:
            pages.append(self.read_pptx_slide(prs.slides[self.page_number - 1], self.page_number))
        else:
            for index, slide in enumerate(prs.slides, start=1):
                pages.append(self.read_pptx_slide(slide, index))
        if self.mode == 'single':
            return "\n".join(pages)
        if self.mode == 'paged':
            return pages
        else:
            raise ToolException(f"Unknown mode value: {self.mode}. Only 'single', 'paged' values allowed.")

    def read_pptx_slide(self, slide, index):
        text_content = f'Slide: {index}\n'
        for shape in slide.shapes:
            if hasattr(shape, "text_frame") and shape.text_frame is not None:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.hyperlink and run.hyperlink.address:
                            link_text = run.text.strip() or "Link"
                            link_url = run.hyperlink.address
                            text_content += f" [{link_text}]({link_url}) "
                        else:
                            text_content += run.text
                text_content += "\n"
            elif self.extract_images and shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    caption = perform_llm_prediction_for_image_bytes(shape.image.blob, self.llm, self.prompt)
                except:
                    caption = "unknown"
                text_content += "\n**Image Transcript:**\n" + caption + "\n--------------------\n"
        return text_content + "\n"

    def load(self):
        content = self.get_content()
        if isinstance(content, str):
            yield Document(page_content=content, metadata={})
        elif isinstance(content, list):
            chunk = []
            chunk_count = 0
            for page_number, page in enumerate(content, start=1):
                chunk.append(page)
                if len(chunk) == self.pages_per_chunk:
                    chunk_content = "\n".join(chunk)
                    yield Document(
                        page_content=chunk_content,
                        metadata={"chunk_number": chunk_count + 1,
                                  "pages_in_chunk": list(range(page_number - len(chunk) + 1, page_number + 1))}
                    )
                    chunk = []
                    chunk_count += 1
            if chunk:
                chunk_content = "\n".join(chunk)
                yield Document(
                    page_content=chunk_content,
                    metadata={"chunk_number": chunk_count + 1,
                              "pages_in_chunk": list(range(len(content) - len(chunk) + 1, len(content) + 1))}
                )