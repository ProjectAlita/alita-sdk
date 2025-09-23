import io

from langchain_community.document_loaders import UnstructuredPowerPointLoader
from langchain_core.tools import ToolException
from pptx import Presentation
from .utils import perform_llm_prediction_for_image_bytes, create_temp_file
from pptx.enum.shapes import MSO_SHAPE_TYPE

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

    def get_content(self):
        prs = Presentation(io.BytesIO(self.file_content))
        text_content = ''
        if self.page_number is not None:
            text_content += self.read_pptx_slide(prs.slides[self.page_number - 1], self.page_number)
        else:
            for index, slide in enumerate(prs.slides, start=1):
                text_content += self.read_pptx_slide(slide, index)
        return text_content

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
                    caption = perform_llm_prediction_for_image_bytes(shape.image.blob, self.llm)
                except:
                    caption = "unknown"
                text_content += "\n**Image Transcript:**\n" + caption + "\n--------------------\n"
        return text_content + "\n"

    def load(self):
        if not self.file_path:
            self.file_path = create_temp_file(self.file_content)
        return UnstructuredPowerPointLoader(file_path=self.file_path,
                           mode=self.mode,
                           **self.unstructured_kwargs).load()