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

from typing import List, Optional, Iterator
from charset_normalizer import from_path, from_bytes
from csv import DictReader
from .AlitaTableLoader import AlitaTableLoader
from typing import Any

class AlitaCSVLoader(AlitaTableLoader):
    def __init__(self,
                 file_path: str = None,
                 file_content: bytes = None,
                 encoding: Optional[str] = 'utf-8',
                 autodetect_encoding: bool = True,
                 json_documents: bool = True,
                 raw_content: bool = False,
                 columns: Optional[List[str]] = None,
                 cleanse: bool = True,
                 **kwargs):
        super().__init__(file_path=file_path, file_content=file_content, json_documents=json_documents, columns=columns, raw_content=raw_content, cleanse=cleanse)
        self.encoding = encoding
        self.autodetect_encoding = autodetect_encoding
        if self.file_path:
            if autodetect_encoding:
                self.encoding = from_path(self.file_path).best().encoding
        else:
            self.encoding = from_bytes(self.file_content).best().encoding

    def read_lazy(self) -> Iterator[dict]:
        with open(self.file_path, 'r', encoding=self.encoding) as fd:
            if self.raw_content:
                yield fd.read()
                return
            for row in DictReader(fd):
                yield row

    def read(self) -> Any:
        if self.file_path:
            with open(self.file_path, 'r', encoding=self.encoding) as fd:
                if self.raw_content:
                    return [fd.read()]
                return list(DictReader(fd))
        else:
            super.row_content = True
            return self.file_content
