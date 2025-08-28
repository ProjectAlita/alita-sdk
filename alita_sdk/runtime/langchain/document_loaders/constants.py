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

from langchain_community.document_loaders import (
    UnstructuredMarkdownLoader,
    AirbyteJSONLoader, UnstructuredHTMLLoader,
    PythonLoader)

from .AlitaCSVLoader import AlitaCSVLoader
from .AlitaDocxMammothLoader import AlitaDocxMammothLoader
from .AlitaExcelLoader import AlitaExcelLoader
from .AlitaImageLoader import AlitaImageLoader
from .AlitaJSONLoader import AlitaJSONLoader
from .AlitaPDFLoader import AlitaPDFLoader
from .AlitaPowerPointLoader import AlitaPowerPointLoader
from .AlitaTextLoader import AlitaTextLoader

loaders_map = {
    '.png': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.jpg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.jpeg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.gif': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.bmp': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.svg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.txt': {
        'class': AlitaTextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        },
        'allowed_to_override': ['max_tokens']
    },
    '.yml': {
        'class': AlitaTextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        },
        'allowed_to_override': ['max_tokens']
    },
    '.yaml': {
        'class': AlitaTextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        },
        'allowed_to_override': ['max_tokens']
    },
    '.groovy': {
        'class': AlitaTextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        },
        'allowed_to_override': ['max_tokens']
    },
    '.md': {
        'class': UnstructuredMarkdownLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.csv': {
        'class': AlitaCSVLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'encoding': 'utf-8',
            'raw_content': False,
            'cleanse': False
        },
        'allowed_to_override': ['max_tokens']
    },
    '.xlsx': {
        'class': AlitaExcelLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'raw_content': False,
            'cleanse': False
        },
        'allowed_to_override': ['max_tokens']
    },
    '.xls': {
        'class': AlitaExcelLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'raw_content': False,
            'cleanse': False
        },
        'allowed_to_override': ['max_tokens']
    },
    '.pdf': {
        'class': AlitaPDFLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.docx': {
        'class': AlitaDocxMammothLoader,
        'is_multimodal_processing': True,
        'kwargs': {
            'extract_images': True
        },
        'allowed_to_override': ['max_tokens', 'mode']
    },
    '.json': {
        'class': AlitaJSONLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.jsonl': {
        'class': AirbyteJSONLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.htm': {
        'class': UnstructuredHTMLLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.html': {
        'class': UnstructuredHTMLLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.ppt': {
        'class': AlitaPowerPointLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'mode': 'paged'
        },
        'allowed_to_override': ['max_tokens', 'mode']
    },
    '.pptx': {
        'class': AlitaPowerPointLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'mode': 'paged'
        },
        'allowed_to_override': ['max_tokens', 'mode']
    },
    '.py': {
        'class': PythonLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    }
}
