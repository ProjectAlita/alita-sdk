# Copyright (c) 2023 Artem Rozumenko
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from langchain_community.document_loaders import (TextLoader,
        UnstructuredMarkdownLoader,
        PyPDFLoader,
        UnstructuredPDFLoader,UnstructuredWordDocumentLoader,
        JSONLoader, AirbyteJSONLoader, UnstructuredHTMLLoader,
        UnstructuredPowerPointLoader, PythonLoader)

from langchain_community.document_loaders import (TextLoader,
        UnstructuredMarkdownLoader,
        PyPDFLoader,
        UnstructuredPDFLoader,UnstructuredWordDocumentLoader,
        JSONLoader, AirbyteJSONLoader, UnstructuredHTMLLoader,
        UnstructuredPowerPointLoader, PythonLoader)

from .AlitaCSVLoader import AlitaCSVLoader
from .AlitaDocxMammothLoader import AlitaDocxMammothLoader
from .AlitaExcelLoader import AlitaExcelLoader
from .AlitaImageLoader import AlitaImageLoader

loaders_map = {
    '.png': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    '.jpg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    '.jpeg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    '.gif': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    '.bmp': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    '.svg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    '.txt': {
        'class': TextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        }
    },
    '.yml': {
        'class': TextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        }
    },
    '.yaml': {
        'class': TextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        }
    },
    '.groovy': {
        'class': TextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        }
    },
    '.md': {
        'class': UnstructuredMarkdownLoader,
        'is_multimodal_processing': False,
        'kwargs': {}
    },
    '.csv': {
        'class': AlitaCSVLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'encoding': 'utf-8',
            'raw_content': False,
            'cleanse': False
        }
    },
    '.xlsx': {
        'class': AlitaExcelLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'raw_content': False,
            'cleanse': False
        }
    },
    '.xls': {
        'class': AlitaExcelLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'raw_content': False,
            'cleanse': False
        }
    },
    '.pdf': {
        'class': PyPDFLoader,
        'is_multimodal_processing': False,
        'kwargs': {}
    },
    '.docx': {
        'class': AlitaDocxMammothLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    '.json': {
        'class': TextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        }
    },
    '.jsonl': {
        'class': AirbyteJSONLoader,
        'is_multimodal_processing': False,
        'kwargs': {}
    },
    '.htm': {
        'class': UnstructuredHTMLLoader,
        'is_multimodal_processing': False,
        'kwargs': {}
    },
    '.html': {
        'class': UnstructuredHTMLLoader,
        'is_multimodal_processing': False,
        'kwargs': {}
    },
    '.ppt': {
        'class': UnstructuredPowerPointLoader,
        'is_multimodal_processing': False,
        'kwargs': {}
    },
    '.pptx': {
        'class': UnstructuredPowerPointLoader,
        'is_multimodal_processing': False,
        'kwargs': {}
    },
    '.py': {
        'class': PythonLoader,
        'is_multimodal_processing': False,
        'kwargs': {}
    }
}
