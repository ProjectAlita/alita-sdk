from langchain_community.document_loaders.parsers.images import BaseImageBlobParser

from alita_sdk.runtime.langchain.document_loaders.AlitaImageLoader import AlitaImageLoader

class ImageParser(BaseImageBlobParser):

    def __init__(self, **kwargs):
        self.llm = kwargs.get('llm')
        self.prompt = kwargs.get('prompt')

    def _analyze_image(self, img) -> str:
        from io import BytesIO

        byte_stream = BytesIO()
        img.save(byte_stream, format='PNG')
        image_bytes = byte_stream.getvalue()
        return AlitaImageLoader(file_content=image_bytes, file_name="image.png", prompt=self.prompt, llm=self.llm).get_content()