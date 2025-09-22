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
    AirbyteJSONLoader, UnstructuredHTMLLoader,
    PythonLoader, UnstructuredXMLLoader)

from .AlitaCSVLoader import AlitaCSVLoader
from .AlitaDocxMammothLoader import AlitaDocxMammothLoader
from .AlitaExcelLoader import AlitaExcelLoader
from .AlitaImageLoader import AlitaImageLoader
from .AlitaJSONLoader import AlitaJSONLoader
from .AlitaPDFLoader import AlitaPDFLoader
from .AlitaPowerPointLoader import AlitaPowerPointLoader
from .AlitaTextLoader import AlitaTextLoader
from .AlitaMarkdownLoader import AlitaMarkdownLoader
from .AlitaPythonLoader import AlitaPythonLoader
from enum import Enum

class LoaderProperties(Enum):
    LLM = 'llm'
    PROMPT = 'prompt'
    PROMPT_DEFAULT = 'prompt_default'

loaders_map = {
    '.png': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value],
    },
    '.jpg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.jpeg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.gif': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.bmp': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.svg': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
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
        'class': AlitaMarkdownLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.csv': {
        'class': AlitaCSVLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'encoding': 'utf-8',
            'raw_content': True,
            'cleanse': False
        },
        'allowed_to_override': ['max_tokens']
    },
    '.xlsx': {
        'class': AlitaExcelLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'excel_by_sheets': True,
            'raw_content': True,
            'cleanse': False
        },
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.xls': {
        'class': AlitaExcelLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'excel_by_sheets': True,
            'raw_content': True,
            'cleanse': False
        },
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.pdf': {
        'class': AlitaPDFLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.docx': {
        'class': AlitaDocxMammothLoader,
        'is_multimodal_processing': True,
        'kwargs': {
            'extract_images': True
        },
        'allowed_to_override': ['max_tokens', 'mode', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
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
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.html': {
        'class': UnstructuredHTMLLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.xml': {
        'class': UnstructuredXMLLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.ppt': {
        'class': AlitaPowerPointLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'mode': 'paged'
        },
        'allowed_to_override': ['max_tokens', 'mode', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.pptx': {
        'class': AlitaPowerPointLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'mode': 'paged'
        },
        'allowed_to_override': ['max_tokens', 'mode', LoaderProperties.LLM.value, LoaderProperties.PROMPT.value, LoaderProperties.PROMPT_DEFAULT.value]
    },
    '.py': {
        'class': AlitaPythonLoader,
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    }
}
