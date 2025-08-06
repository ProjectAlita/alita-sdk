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
import io
from typing import Iterator
import pandas as pd
from json import loads

from langchain_core.tools import ToolException
from .AlitaTableLoader import AlitaTableLoader
    

class AlitaExcelLoader(AlitaTableLoader):

    excel_by_sheets: bool = False
    sheet_name: str = None
    return_type: str = 'str'

    def __init__(self, **kwargs):
        if not kwargs.get('file_path'):
            file_content = kwargs.get('file_content')
            if file_content:
                kwargs['file_path'] = io.BytesIO(file_content)
        super().__init__(**kwargs)
        self.excel_by_sheets = kwargs.get('excel_by_sheets')
        self.return_type = kwargs.get('return_type')
        self.sheet_name = kwargs.get('sheet_name')

    def get_content(self):
        try:
            dfs = pd.read_excel(self.file_path, sheet_name=self.sheet_name)

            if self.excel_by_sheets:
                result = {}
                for sheet_name, df in dfs.items():
                    df.fillna('', inplace=True)
                    result[sheet_name] = self.parse_sheet(df)
                return result
            else:
                result = []
                for sheet_name, df in dfs.items():
                    string_content = self.parse_sheet(df)
                    result.append(f"====== Sheet name: {sheet_name} ======\n{string_content}")
                return "\n\n".join(result)
        except Exception as e:
            return ToolException(f"Error reading Excel file: {e}")

    def parse_sheet(self, df):
        df.fillna('', inplace=True)

        if self.return_type == 'dict':
            return df.to_dict(orient='records')
        elif self.return_type == 'csv':
            return df.to_csv()
        else:
            return df.to_string(index=False)

    def read(self):
        df = pd.read_excel(self.file_path, sheet_name=None)
        docs = []
        for key in df.keys():
            if self.raw_content:
                docs.append(df[key].to_string())
            else:
                for record in loads(df[key].to_json(orient='records')):
                    docs.append(record)
        return docs

    def read_lazy(self) -> Iterator[dict]:
        df = pd.read_excel(self.file_path, sheet_name=None)
        for key in df.keys():
            if self.raw_content:
                yield df[key].to_string()
            else:
                for record in loads(df[key].to_json(orient='records')):
                    yield record
        return
