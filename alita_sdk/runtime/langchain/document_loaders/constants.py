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
    UnstructuredXMLLoader)

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


# Image file loaders mapping
image_loaders_map = {
    '.png': {
        'class': AlitaImageLoader,
        'mime_type': 'image/png',
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ],
    },
    '.jpg': {
        'class': AlitaImageLoader,
        'mime_type': 'image/jpeg',
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.jpeg': {
        'class': AlitaImageLoader,
        'mime_type': 'image/jpeg',
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.gif': {
        'class': AlitaImageLoader,
        'mime_type': 'image/gif',
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.bmp': {
        'class': AlitaImageLoader,
        'mime_type': 'image/bmp',
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.svg': {
        'class': AlitaImageLoader,
        'mime_type': 'image/svg+xml',
        'is_multimodal_processing': True,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    }
}

# Document file loaders mapping
document_loaders_map = {
    '.txt': {
        'class': AlitaTextLoader,
        'mime_type': 'text/plain',
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        },
        'allowed_to_override': ['max_tokens']
    },
    '.yml': {
        'class': AlitaTextLoader,
        'mime_type': 'application/x-yaml',
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        },
        'allowed_to_override': ['max_tokens']
    },
    '.yaml': {
        'class': AlitaTextLoader,
        'mime_type': 'application/x-yaml',
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        },
        'allowed_to_override': ['max_tokens']
    },
    '.groovy': {
        'class': AlitaTextLoader,
        'mime_type': 'text/x-groovy',
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        },
        'allowed_to_override': ['max_tokens']
    },
    '.md': {
        'class': AlitaMarkdownLoader,
        'mime_type': 'text/markdown',
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.csv': {
        'class': AlitaCSVLoader,
        'mime_type': 'text/csv',
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
        'mime_type': ('application/vnd.openxmlformats-officedocument.'
                      'spreadsheetml.sheet'),
        'is_multimodal_processing': False,
        'kwargs': {
            'excel_by_sheets': True,
            'raw_content': True,
            'cleanse': False
        },
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.xls': {
        'class': AlitaExcelLoader,
        'mime_type': 'application/vnd.ms-excel',
        'is_multimodal_processing': False,
        'kwargs': {
            'excel_by_sheets': True,
            'raw_content': True,
            'cleanse': False
        },
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.pdf': {
        'class': AlitaPDFLoader,
        'mime_type': 'application/pdf',
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.docx': {
        'class': AlitaDocxMammothLoader,
        'mime_type': ('application/vnd.openxmlformats-officedocument.'
                      'wordprocessingml.document'),
        'is_multimodal_processing': True,
        'kwargs': {
            'extract_images': True
        },
        'allowed_to_override': [
            'max_tokens', 'mode', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.json': {
        'class': AlitaJSONLoader,
        'mime_type': 'application/json',
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.jsonl': {
        'class': AirbyteJSONLoader,
        'mime_type': 'application/jsonl',
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    },
    '.htm': {
        'class': UnstructuredHTMLLoader,
        'mime_type': 'text/html',
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.html': {
        'class': UnstructuredHTMLLoader,
        'mime_type': 'text/html',
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.xml': {
        'class': UnstructuredXMLLoader,
        'mime_type': 'text/xml',
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': [
            'max_tokens', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.ppt': {
        'class': AlitaPowerPointLoader,
        'mime_type': 'application/vnd.ms-powerpoint',
        'is_multimodal_processing': False,
        'kwargs': {
            'mode': 'paged'
        },
        'allowed_to_override': [
            'max_tokens', 'mode', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.pptx': {
        'class': AlitaPowerPointLoader,
        'mime_type': ('application/vnd.openxmlformats-officedocument.'
                      'presentationml.presentation'),
        'is_multimodal_processing': False,
        'kwargs': {
            'mode': 'paged'
        },
        'allowed_to_override': [
            'max_tokens', 'mode', LoaderProperties.LLM.value,
            LoaderProperties.PROMPT.value,
            LoaderProperties.PROMPT_DEFAULT.value
        ]
    },
    '.py': {
        'class': AlitaPythonLoader,
        'mime_type': 'text/x-python',
        'is_multimodal_processing': False,
        'kwargs': {},
        'allowed_to_override': ['max_tokens']
    }
}

code_extensions = [
    # '.py',  # Python
    '.js',  # JavaScript
    '.ts',  # TypeScript
    '.java',  # Java
    '.cpp',  # C++
    '.c',  # C
    '.cs',  # C#
    '.rb',  # Ruby
    '.go',  # Go
    '.php',  # PHP
    '.swift',  # Swift
    '.kt',  # Kotlin
    '.rs',  # Rust
    '.m',  # Objective-C
    '.scala',  # Scala
    '.pl',  # Perl
    '.sh',  # Shell
    '.bat',  # Batch
    '.lua',  # Lua
    '.r',  # R
    '.pas',  # Pascal
    '.asm',  # Assembly
    '.dart',  # Dart
    '.groovy',  # Groovy
    '.sql',  # SQL
]

default_loader_config = {
    'class': AlitaTextLoader,
    'mime_type': 'text/plain',
    'is_multimodal_processing': False,
    'kwargs': {},
    'allowed_to_override': ['max_tokens']
}

code_loaders_map = {ext: default_loader_config for ext in code_extensions}

# Combined mapping for backward compatibility
loaders_map = {**image_loaders_map, **document_loaders_map, **code_loaders_map}
