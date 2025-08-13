from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from .utils import file_to_bytes


class AlitaDocLoader(BaseLoader):

    def __init__(self, **kwargs):
        if kwargs.get('file_path'):
            self.file_path = kwargs['file_path']
        elif kwargs.get('file_content'):
            self.file_content = kwargs['file_content']
            self.file_name = kwargs['file_name']
        else:
            raise ValueError(
                "Path parameter is required (either as 'file_path' positional argument or 'path' keyword argument)")

    def load(self):
        result_content = self.get_content()
        return [Document(page_content=result_content, metadata={'source': str(self.file_path if hasattr(self, 'file_path') else self.file_name)})]

    def get_content(self):
        try:
            import textract
            content = textract.process(None, extension='doc', input_data=self.file_content if hasattr(self, 'file_content') else file_to_bytes(self.file_path)).decode('utf-8')
        except Exception as e:
            content = f"[Error extracting doc: {str(e)}]"
        return content