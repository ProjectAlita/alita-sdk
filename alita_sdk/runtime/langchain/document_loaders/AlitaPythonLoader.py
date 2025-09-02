from pathlib import Path
from typing import Union
from langchain_community.document_loaders.python import PythonLoader

class AlitaPythonLoader(PythonLoader):
    """Load `Python` files, respecting any non-default encoding if specified."""

    def __init__(self, file_path: Union[str, Path], **kwargs):
        super().__init__(file_path)
