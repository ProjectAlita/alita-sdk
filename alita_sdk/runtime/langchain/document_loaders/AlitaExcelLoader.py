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
import os
from typing import Iterator
import pandas as pd
from json import loads

from openpyxl import load_workbook
from xlrd import open_workbook
from langchain_core.documents import Document
from .AlitaTableLoader import AlitaTableLoader

cell_delimiter = " | "

class AlitaExcelLoader(AlitaTableLoader):
    excel_by_sheets: bool = False
    sheet_name: str = None
    return_type: str = 'str'
    file_name: str = None

    def __init__(self, **kwargs):
        if not kwargs.get('file_path'):
            file_content = kwargs.get('file_content')
            if file_content:
                self.file_name = kwargs.get('file_name')
                kwargs['file_path'] = io.BytesIO(file_content)
        else:
            self.file_name = kwargs.get('file_path')
        super().__init__(**kwargs)
        self.excel_by_sheets = kwargs.get('excel_by_sheets')
        self.return_type = kwargs.get('return_type')
        self.sheet_name = kwargs.get('sheet_name')

    def get_content(self):
        try:
            # Determine file extension
            file_extension = os.path.splitext(self.file_name)[-1].lower()

            if file_extension == '.xlsx':
                # Use openpyxl for .xlsx files
                return self._read_xlsx()
            elif file_extension == '.xls':
                # Use xlrd for .xls files
                return self._read_xls()
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
        except Exception as e:
            return f"Error reading Excel file: {e}"

    def _read_xlsx(self):
        """
        Reads .xlsx files using openpyxl.
        """
        workbook = load_workbook(self.file_path, data_only=True)  # `data_only=True` ensures we get cell values, not formulas

        if self.sheet_name:
            # If a specific sheet name is provided, parse only that sheet
            if self.sheet_name in workbook.sheetnames:
                sheet_content = self.parse_sheet(workbook[self.sheet_name])
                return sheet_content
            else:
                raise ValueError(f"Sheet '{self.sheet_name}' does not exist in the workbook.")
        elif self.excel_by_sheets:
            # Parse each sheet individually and return as a dictionary
            result = {}
            for sheet_name in workbook.sheetnames:
                sheet_content = self.parse_sheet(workbook[sheet_name])
                result[sheet_name] = sheet_content
            return result
        else:
            # Combine all sheets into a single string result
            result = []
            for sheet_name in workbook.sheetnames:
                sheet_content = self.parse_sheet(workbook[sheet_name])
                result.append(f"====== Sheet name: {sheet_name} ======\n{sheet_content}")
            return "\n\n".join(result)

    def _read_xls(self):
        """
        Reads .xls files using xlrd.
        """
        workbook = open_workbook(filename=self.file_name, file_contents=self.file_content)

        if self.sheet_name:
            # If a specific sheet name is provided, parse only that sheet
            if self.sheet_name in workbook.sheet_names():
                sheet = workbook.sheet_by_name(self.sheet_name)
                sheet_content = self.parse_sheet_xls(sheet)
                return sheet_content
            else:
                raise ValueError(f"Sheet '{self.sheet_name}' does not exist in the workbook.")
        elif self.excel_by_sheets:
            # Parse each sheet individually and return as a dictionary
            result = {}
            for sheet_name in workbook.sheet_names():
                sheet = workbook.sheet_by_name(sheet_name)
                sheet_content = self.parse_sheet_xls(sheet)
                result[sheet_name] = sheet_content
            return result
        else:
            # Combine all sheets into a single string result
            result = []
            for sheet_name in workbook.sheet_names():
                sheet = workbook.sheet_by_name(sheet_name)
                sheet_content = self.parse_sheet_xls(sheet)
                result.append(f"====== Sheet name: {sheet_name} ======\n{sheet_content}")
            return "\n\n".join(result)

    def parse_sheet(self, sheet):
        """
        Parses a single .xlsx sheet, extracting text and hyperlinks, and formats them.
        """
        sheet_content = []

        for row in sheet.iter_rows():
            row_content = []
            for cell in row:
                if cell.hyperlink:
                    # If the cell has a hyperlink, format it as Markdown
                    hyperlink = cell.hyperlink.target
                    cell_value = cell.value or ''  # Use cell value or empty string
                    row_content.append(f"[{cell_value}]({hyperlink})")
                else:
                    # If no hyperlink, use the cell value (computed value if formula)
                    row_content.append(str(cell.value) if cell.value is not None else "")
            # Join the row content into a single line using `|` as the delimiter
            sheet_content.append(cell_delimiter.join(row_content))

        # Format the sheet content based on the return type
        return self._format_sheet_content(sheet_content)

    def parse_sheet_xls(self, sheet):
        """
        Parses a single .xls sheet using xlrd, extracting text and hyperlinks, and formats them.
        """
        sheet_content = []

        # Extract hyperlink map (if available)
        hyperlink_map = getattr(sheet, 'hyperlink_map', {})

        for row_idx in range(sheet.nrows):
            row_content = []
            for col_idx in range(sheet.ncols):
                cell = sheet.cell(row_idx, col_idx)
                cell_value = cell.value

                # Check if the cell has a hyperlink
                cell_address = (row_idx, col_idx)
                if cell_address in hyperlink_map:
                    hyperlink = hyperlink_map[cell_address].url_or_path
                    if cell_value:
                        row_content.append(f"[{cell_value}]({hyperlink})")
                else:
                    row_content.append(str(cell_value) if cell_value is not None else "")
            # Join the row content into a single line using `|` as the delimiter
            sheet_content.append(cell_delimiter.join(row_content))

        # Format the sheet content based on the return type
        return self._format_sheet_content(sheet_content)

    def _format_sheet_content(self, sheet_content):
        """
        Formats the sheet content based on the return type.
        """
        if self.return_type == 'dict':
            # Convert to a list of dictionaries (each row is a dictionary)
            headers = sheet_content[0].split(cell_delimiter) if sheet_content else []
            data_rows = sheet_content[1:] if len(sheet_content) > 1 else []
            return [dict(zip(headers, row.split(cell_delimiter))) for row in data_rows]
        elif self.return_type == 'csv':
            # Return as CSV (newline-separated rows, comma-separated values)
            return "\n".join([",".join(row.split(cell_delimiter)) for row in sheet_content])
        else:
            # Default: Return as plain text (newline-separated rows, pipe-separated values)
            return "\n".join(sheet_content)

    def load(self) -> list:
        docs = []
        content_per_sheet = self.get_content()
        for sheet_name, content in content_per_sheet.items():
            metadata = {
                "source": f'{self.file_path}:{sheet_name}',
                "sheet_name": sheet_name,
                "file_type": "excel",
                "excel_by_sheets": self.excel_by_sheets,
                "return_type": self.return_type,
            }
            docs.append(Document(page_content=f"Sheet: {sheet_name}\n {str(content)}", metadata=metadata))
        return docs

    def read(self, lazy: bool = False):
        df = pd.read_excel(self.file_path, sheet_name=None, engine='calamine')
        docs = []
        for key in df.keys():
            if self.raw_content:
                docs.append(df[key].to_string())
            else:
                for record in loads(df[key].to_json(orient='records')):
                    docs.append(record)
        return docs

    def read_lazy(self) -> Iterator[dict]:
        df = pd.read_excel(self.file_path, sheet_name=None, engine='calamine')
        for key in df.keys():
            if self.raw_content:
                yield df[key].to_string()
            else:
                for record in loads(df[key].to_json(orient='records')):
                    yield record
        return
